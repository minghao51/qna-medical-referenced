"""Quality checks for ingestion and indexing pipeline stages."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from pypdf import PdfReader

from src.config import DATA_RAW_DIR, VECTOR_DIR, settings
from src.ingestion.artifacts import load_source_artifact
from src.ingestion.steps.chunk_text import TextChunker
from src.ingestion.steps.download_web import _load_manifest, get_manifest_alias_filenames
from src.ingestion.steps.load_pdfs import get_documents
from src.ingestion.steps.load_reference_data import REQUIRED_CSV_COLUMNS


def _safe_median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _safe_mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _source_type_from_name(name: str) -> str:
    lowered = name.lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if "reference_ranges.csv" in lowered:
        return "csv"
    if lowered.endswith(".md") or lowered.endswith(".html"):
        return "html"
    return "other"


def audit_l0_download(data_raw_dir: Path | None = None) -> dict[str, Any]:
    data_dir = Path(data_raw_dir or DATA_RAW_DIR)
    html_files = sorted(data_dir.glob("*.html"))
    records: list[dict[str, Any]] = []
    duplicate_hashes: Counter[str] = Counter()
    small_count = 0
    parse_failures = 0

    for html_path in html_files:
        raw = html_path.read_text(encoding="utf-8", errors="ignore")
        size_bytes = html_path.stat().st_size
        text_chars = 0
        parse_ok = True
        try:
            soup = BeautifulSoup(raw, "html.parser")
            text_chars = len(soup.get_text(" ", strip=True))
        except Exception:
            parse_ok = False
            parse_failures += 1
        content_hash = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()
        duplicate_hashes[content_hash] += 1
        if size_bytes < 2048:
            small_count += 1
        records.append(
            {
                "file": html_path.name,
                "size_bytes": size_bytes,
                "parse_ok": parse_ok,
                "visible_text_chars": text_chars,
                "has_html_tag": "<html" in raw.lower(),
                "has_body_tag": "<body" in raw.lower(),
            }
        )

    duplicate_files = sum(count - 1 for count in duplicate_hashes.values() if count > 1)
    manifest = _load_manifest()
    alias_filenames = get_manifest_alias_filenames(manifest)
    alias_files_on_disk = [r for r in records if str(r.get("file")) in alias_filenames]
    alias_duplicate_count = len(alias_files_on_disk)
    true_duplicate_files = max(0, duplicate_files - alias_duplicate_count)
    aggregate = {
        "html_file_count": len(html_files),
        "small_file_rate": (small_count / len(html_files)) if html_files else 0.0,
        "duplicate_file_rate": (duplicate_files / len(html_files)) if html_files else 0.0,
        "duplicate_alias_file_rate": (alias_duplicate_count / len(html_files))
        if html_files
        else 0.0,
        "true_duplicate_file_rate": (true_duplicate_files / len(html_files)) if html_files else 0.0,
        "html_parse_success_rate": ((len(html_files) - parse_failures) / len(html_files))
        if html_files
        else 0.0,
        "manifest_inventory_record_count": sum(
            1 for r in manifest.get("records", []) if r.get("record_type") == "file_inventory"
        ),
    }
    findings = []
    if aggregate["small_file_rate"] > 0.2:
        findings.append(
            {"severity": "warning", "message": "High small HTML file rate", "stage": "L0"}
        )
    return {"aggregate": aggregate, "records": records, "findings": findings}


def assess_l1_html_markdown_quality(data_raw_dir: Path | None = None) -> dict[str, Any]:
    data_dir = Path(data_raw_dir or DATA_RAW_DIR)
    html_files = sorted(data_dir.glob("*.html"))
    records: list[dict[str, Any]] = []
    retention_ratios: list[float] = []
    empty_md = 0
    boilerplate_terms = ["cookie", "privacy", "menu", "navigation", "subscribe", "footer"]

    for html_path in html_files:
        md_path = html_path.with_suffix(".md")
        html_raw = html_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html_raw, "html.parser")
        html_visible = soup.get_text("\n", strip=True)
        html_chars = len(html_visible)
        md_text = md_path.read_text(encoding="utf-8", errors="ignore") if md_path.exists() else ""
        artifact = load_source_artifact("html", html_path.stem) or {}
        artifact_meta = artifact.get("metadata", {})
        structured_blocks = artifact.get("structured_blocks", [])
        md_chars = len(md_text.strip())
        retention = (md_chars / html_chars) if html_chars > 0 else 0.0
        retention_ratios.append(retention)
        if md_chars < 40:
            empty_md += 1
        lowered = md_text.lower()
        boilerplate_hits = sum(lowered.count(term) for term in boilerplate_terms)
        records.append(
            {
                "file": html_path.name,
                "md_exists": md_path.exists(),
                "html_visible_chars": html_chars,
                "md_chars": md_chars,
                "retention_ratio": retention,
                "markdown_heading_count": len(
                    re.findall(r"^#{1,6}\s", md_text, flags=re.MULTILINE)
                ),
                "markdown_list_lines": len(re.findall(r"^\s*[-*]\s", md_text, flags=re.MULTILINE)),
                "markdown_link_count": md_text.count("]("),
                "boilerplate_hits": boilerplate_hits,
                "boilerplate_suspicion": (boilerplate_hits / max(1, md_chars)),
                "content_density": artifact_meta.get("text_density", 0.0),
                "page_type": artifact_meta.get("page_type"),
                "heading_preservation_rate": (
                    len(re.findall(r"^#{1,6}\s", md_text, flags=re.MULTILINE))
                    / max(
                        1,
                        sum(
                            1 for block in structured_blocks if block.get("block_type") == "heading"
                        ),
                    )
                ),
                "table_preservation_rate": (
                    md_text.count("| --- |")
                    / max(
                        1,
                        sum(1 for block in structured_blocks if block.get("block_type") == "table"),
                    )
                ),
            }
        )

    aggregate = {
        "pairs_evaluated": len(records),
        "markdown_missing_rate": (_count_false(records, "md_exists") / len(records))
        if records
        else 0.0,
        "markdown_empty_rate": (empty_md / len(records)) if records else 0.0,
        "retention_ratio_median": _safe_median(retention_ratios),
        "retention_ratio_mean": _safe_mean(retention_ratios),
        "low_retention_rate": (sum(1 for r in retention_ratios if r < 0.05) / len(retention_ratios))
        if retention_ratios
        else 0.0,
        "content_density_mean": _safe_mean([float(r.get("content_density", 0.0)) for r in records]),
        "boilerplate_ratio_mean": _safe_mean(
            [float(r.get("boilerplate_suspicion", 0.0)) for r in records]
        ),
        "heading_preservation_rate_mean": _safe_mean(
            [float(r.get("heading_preservation_rate", 0.0)) for r in records]
        ),
        "table_preservation_rate_mean": _safe_mean(
            [float(r.get("table_preservation_rate", 0.0)) for r in records]
        ),
        "page_classification_distribution": dict(
            Counter(str(r.get("page_type", "unknown")) for r in records)
        ),
    }
    findings = []
    if aggregate["markdown_empty_rate"] > 0.1:
        findings.append(
            {"severity": "warning", "message": "High empty markdown rate", "stage": "L1"}
        )
    return {"aggregate": aggregate, "records": records, "findings": findings}


def _count_false(records: list[dict[str, Any]], key: str) -> int:
    return sum(1 for r in records if not r.get(key))


def assess_l2_pdf_quality(data_raw_dir: Path | None = None) -> dict[str, Any]:
    data_dir = Path(data_raw_dir or DATA_RAW_DIR)
    pdf_files = sorted(data_dir.glob("*.pdf"))
    records: list[dict[str, Any]] = []
    total_pages = 0
    extracted_pages = 0
    empty_pages = 0
    findings = []

    for pdf_path in pdf_files:
        try:
            reader = PdfReader(str(pdf_path))
        except Exception as exc:
            findings.append(
                {"severity": "error", "stage": "L2", "file": pdf_path.name, "message": str(exc)}
            )
            continue
        artifact = load_source_artifact("pdf", pdf_path.stem) or {}
        artifact_meta = artifact.get("metadata", {})

        per_page_chars: list[int] = []
        replacement_chars = 0
        fallback_pages = 0
        low_conf_pages = 0
        ocr_required_pages = 0
        suspected_tables = 0
        for page in reader.pages:
            total_pages += 1
            text = page.extract_text() or ""
            replacement_chars += text.count("\ufffd")
            chars = len(text.strip())
            per_page_chars.append(chars)
            if chars > 0:
                extracted_pages += 1
            else:
                empty_pages += 1
        for page_data in artifact.get("best_output", {}).get("pages", []):
            if page_data.get("extractor") == "pdfplumber":
                fallback_pages += 1
        for page_data in artifact.get("best_output", {}).get("pages", []):
            if page_data.get("confidence") == "low":
                low_conf_pages += 1
            if page_data.get("ocr_required"):
                ocr_required_pages += 1
            suspected_tables += int(page_data.get("suspected_table_count", 0))
        records.append(
            {
                "file": pdf_path.name,
                "page_count": len(reader.pages),
                "extracted_page_count": sum(1 for c in per_page_chars if c > 0),
                "empty_page_count": sum(1 for c in per_page_chars if c == 0),
                "chars_per_page_median": _safe_median([float(c) for c in per_page_chars]),
                "chars_per_page_min": min(per_page_chars) if per_page_chars else 0,
                "chars_per_page_max": max(per_page_chars) if per_page_chars else 0,
                "replacement_char_count": replacement_chars,
                "fallback_page_count": artifact_meta.get("fallback_used_pages", fallback_pages),
                "low_confidence_page_count": artifact_meta.get(
                    "low_confidence_pages", low_conf_pages
                ),
                "ocr_required_page_count": artifact_meta.get(
                    "ocr_required_pages", ocr_required_pages
                ),
                "suspected_table_count": suspected_tables,
            }
        )

    aggregate = {
        "pdf_file_count": len(pdf_files),
        "total_pages": total_pages,
        "extracted_pages": extracted_pages,
        "page_extraction_coverage": (extracted_pages / total_pages) if total_pages else 0.0,
        "empty_page_rate": (empty_pages / total_pages) if total_pages else 0.0,
        "extractor_fallback_rate": (
            sum(int(r.get("fallback_page_count", 0)) for r in records) / total_pages
        )
        if total_pages
        else 0.0,
        "low_confidence_page_rate": (
            sum(int(r.get("low_confidence_page_count", 0)) for r in records) / total_pages
        )
        if total_pages
        else 0.0,
        "ocr_required_rate": (
            sum(int(r.get("ocr_required_page_count", 0)) for r in records) / total_pages
        )
        if total_pages
        else 0.0,
        "table_extraction_success_proxy": (
            sum(1 for r in records if int(r.get("suspected_table_count", 0)) > 0) / len(records)
        )
        if records
        else 0.0,
    }
    if aggregate["empty_page_rate"] > 0.2:
        findings.append(
            {
                "severity": "warning",
                "message": "High empty page rate in PDF extraction",
                "stage": "L2",
            }
        )
    return {"aggregate": aggregate, "records": records, "findings": findings}


def _longest_suffix_prefix_overlap(a: str, b: str, max_len: int) -> int:
    limit = min(max_len, len(a), len(b))
    for size in range(limit, 0, -1):
        if a[-size:] == b[:size]:
            return size
    return 0


def assess_l3_chunking_quality(
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> dict[str, Any]:
    docs = get_documents()
    chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = chunker.chunk_documents(docs)
    records: list[dict[str, Any]] = []
    duplicate_hashes: Counter[str] = Counter()
    boundary_cut_count = 0
    overlap_values: list[int] = []
    groups: dict[tuple[str, int | None], list[dict[str, Any]]] = defaultdict(list)

    for chunk in chunks:
        content = chunk.get("content", "")
        chunk_hash = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
        duplicate_hashes[chunk_hash] += 1
        if content and content[-1].isalnum():
            boundary_cut_count += 1
        key = (str(chunk.get("source", "")), chunk.get("page"))
        groups[key].append(chunk)
        records.append(
            {
                "id": chunk.get("id"),
                "source": chunk.get("source"),
                "page": chunk.get("page"),
                "length_chars": len(content),
                "has_page": "page" in chunk,
                "content_hash": chunk_hash[:16],
                "ends_mid_token": bool(content and content[-1].isalnum()),
            }
        )

    for _, group in groups.items():
        for first, second in zip(group, group[1:]):
            a = first.get("content", "")
            b = second.get("content", "")
            overlap_values.append(_longest_suffix_prefix_overlap(a, b, chunk_overlap))

    lengths = [r["length_chars"] for r in records]
    duplicate_chunks = sum(count - 1 for count in duplicate_hashes.values() if count > 1)
    low_quality_excluded = 0
    aggregate = {
        "document_count": len(docs),
        "chunk_count": len(chunks),
        "chunk_size_config": chunk_size,
        "chunk_overlap_config": chunk_overlap,
        "chunk_length_median": _safe_median([float(x) for x in lengths]),
        "chunk_length_mean": _safe_mean([float(x) for x in lengths]),
        "duplicate_chunk_rate": (duplicate_chunks / len(chunks)) if chunks else 0.0,
        "boundary_cut_rate": (boundary_cut_count / len(chunks)) if chunks else 0.0,
        "observed_overlap_mean": _safe_mean([float(x) for x in overlap_values]),
        "section_integrity_rate": (sum(1 for c in chunks if c.get("section_path")) / len(chunks))
        if chunks
        else 0.0,
        "table_row_split_violations": sum(
            1
            for c in chunks
            if c.get("content_type") == "table" and len(str(c.get("content", "")).splitlines()) == 1
        ),
        "low_quality_chunk_exclusion_rate": (
            low_quality_excluded / max(1, len(chunks) + low_quality_excluded)
        ),
        "chunk_quality_histogram": {
            "high": sum(1 for c in chunks if float(c.get("quality_score", 1.0)) >= 0.8),
            "medium": sum(1 for c in chunks if 0.55 <= float(c.get("quality_score", 1.0)) < 0.8),
            "low": sum(1 for c in chunks if float(c.get("quality_score", 1.0)) < 0.55),
        },
    }
    findings = []
    if aggregate["duplicate_chunk_rate"] > 0.05:
        findings.append(
            {"severity": "warning", "message": "Duplicate chunk rate exceeds 5%", "stage": "L3"}
        )
    return {"aggregate": aggregate, "records": records, "findings": findings}


def assess_l4_reference_quality(data_raw_dir: Path | None = None) -> dict[str, Any]:
    data_dir = Path(data_raw_dir or DATA_RAW_DIR)
    csv_path = data_dir / "LabQAR" / "reference_ranges.csv"
    if not csv_path.exists():
        return {
            "aggregate": {"csv_exists": False, "row_count": 0},
            "records": [],
            "findings": [
                {"severity": "warning", "message": "Reference CSV missing", "stage": "L4"}
            ],
        }

    records: list[dict[str, Any]] = []
    duplicate_names: Counter[str] = Counter()
    complete_rows = 0
    parseable_ranges = 0
    findings = []

    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing_cols = sorted(REQUIRED_CSV_COLUMNS - set(fieldnames))
        if missing_cols:
            findings.append(
                {"severity": "error", "message": f"Missing columns: {missing_cols}", "stage": "L4"}
            )
        for idx, row in enumerate(reader):
            test_name = (row.get("test_name") or "").strip()
            duplicate_names[test_name.lower()] += 1
            values = {k: (row.get(k) or "").strip() for k in REQUIRED_CSV_COLUMNS}
            is_complete = all(values.values())
            complete_rows += int(is_complete)
            range_value = values.get("normal_range", "")
            parseable = bool(re.search(r"\d", range_value))
            parseable_ranges += int(parseable)
            records.append(
                {
                    "row_index": idx,
                    "test_name": test_name,
                    "is_complete": is_complete,
                    "normal_range_parseable": parseable,
                    "notes_empty": not bool(values.get("notes")),
                }
            )

    row_count = len(records)
    duplicate_entries = sum(
        count - 1 for name, count in duplicate_names.items() if name and count > 1
    )
    aggregate = {
        "csv_exists": True,
        "row_count": row_count,
        "schema_valid": not any(f["severity"] == "error" for f in findings),
        "required_columns_present": not any(f["severity"] == "error" for f in findings),
        "row_completeness_rate": (complete_rows / row_count) if row_count else 0.0,
        "duplicate_test_name_rate": (duplicate_entries / row_count) if row_count else 0.0,
        "normal_range_parseable_rate": (parseable_ranges / row_count) if row_count else 0.0,
    }
    return {"aggregate": aggregate, "records": records, "findings": findings}


def assess_l5_index_quality(
    vector_dir: Path | None = None,
    collection_name: str | None = None,
) -> dict[str, Any]:
    vdir = Path(vector_dir or VECTOR_DIR)
    coll = collection_name or settings.collection_name
    vector_path = vdir / f"{coll}.json"
    if not vector_path.exists():
        return {
            "aggregate": {"index_exists": False, "vector_path": str(vector_path)},
            "records": [],
            "findings": [
                {"severity": "warning", "message": "Vector index file missing", "stage": "L5"}
            ],
        }

    data = json.loads(vector_path.read_text(encoding="utf-8"))
    ids = data.get("ids", [])
    contents = data.get("contents", [])
    embeddings = data.get("embeddings", [])
    metadatas = data.get("metadatas", [])
    content_hashes = data.get("content_hashes", [])
    lengths = [len(e) for e in embeddings if isinstance(e, list)]
    source_counter = Counter((m or {}).get("source", "unknown") for m in metadatas)
    records = [
        {
            "id": ids[i] if i < len(ids) else None,
            "source": (metadatas[i] or {}).get("source", "unknown")
            if i < len(metadatas)
            else "unknown",
            "content_chars": len(contents[i])
            if i < len(contents) and isinstance(contents[i], str)
            else 0,
            "embedding_dim": len(embeddings[i])
            if i < len(embeddings) and isinstance(embeddings[i], list)
            else 0,
        }
        for i in range(min(len(ids), len(contents), len(embeddings), len(metadatas)))
    ]
    findings = []
    lengths_equal = len(ids) == len(contents) == len(embeddings) == len(metadatas)
    if not lengths_equal:
        findings.append(
            {"severity": "error", "message": "Vector arrays have mismatched lengths", "stage": "L5"}
        )
    unique_dims = sorted(set(lengths))
    index_metadata = data.get("index_metadata", {})
    if len(unique_dims) > 1:
        findings.append(
            {"severity": "error", "message": "Embedding dimensions are inconsistent", "stage": "L5"}
        )

    aggregate = {
        "index_exists": True,
        "vector_path": str(vector_path),
        "ids_count": len(ids),
        "contents_count": len(contents),
        "embeddings_count": len(embeddings),
        "metadatas_count": len(metadatas),
        "content_hashes_count": len(content_hashes),
        "lengths_consistent": lengths_equal,
        "embedding_dim_consistent": len(unique_dims) <= 1,
        "embedding_dim": unique_dims[0] if len(unique_dims) == 1 else None,
        "embedding_model": index_metadata.get("embedding_model"),
        "embedding_batch_size": index_metadata.get("embedding_batch_size"),
        "index_config_hash": index_metadata.get("index_config_hash"),
        "short_content_rate": (
            sum(1 for c in contents if isinstance(c, str) and len(c.strip()) < 20) / len(contents)
        )
        if contents
        else 0.0,
        "source_distribution": dict(source_counter),
        "dedupe_effect_estimate": max(0, len(content_hashes) - len(contents)),
        "index_file_size_bytes": vector_path.stat().st_size,
    }
    return {"aggregate": aggregate, "records": records, "findings": findings}
