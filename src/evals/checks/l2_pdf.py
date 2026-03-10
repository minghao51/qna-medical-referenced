"""L2 PDF quality checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from src.config import DATA_RAW_DIR
from src.evals.checks.shared import safe_median
from src.ingestion.artifacts import load_source_artifact


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
                "chars_per_page_median": safe_median([float(c) for c in per_page_chars]),
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
