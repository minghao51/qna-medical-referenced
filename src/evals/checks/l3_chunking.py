"""L3 chunking quality checks."""

from __future__ import annotations

import hashlib
import itertools
from collections import Counter, defaultdict
from typing import Any

from src.evals.checks.shared import longest_suffix_prefix_overlap, safe_mean, safe_median
from src.ingestion.steps.chunk_text import TextChunker
from src.ingestion.steps.load_pdfs import get_documents


def _float_metric(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


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
        for first, second in itertools.pairwise(group):
            a = first.get("content", "")
            b = second.get("content", "")
            overlap_values.append(longest_suffix_prefix_overlap(a, b, chunk_overlap))

    lengths = [r["length_chars"] for r in records]
    duplicate_chunks = sum(count - 1 for count in duplicate_hashes.values() if count > 1)
    low_quality_excluded = 0
    aggregate = {
        "document_count": len(docs),
        "chunk_count": len(chunks),
        "chunk_size_config": chunk_size,
        "chunk_overlap_config": chunk_overlap,
        "chunk_length_median": safe_median([float(x) for x in lengths]),
        "chunk_length_mean": safe_mean([float(x) for x in lengths]),
        "duplicate_chunk_rate": (duplicate_chunks / len(chunks)) if chunks else 0.0,
        "boundary_cut_rate": (boundary_cut_count / len(chunks)) if chunks else 0.0,
        "observed_overlap_mean": safe_mean([float(x) for x in overlap_values]),
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
            "high": sum(
                1 for c in chunks if _float_metric(c.get("quality_score", 1.0), 1.0) >= 0.8
            ),
            "medium": sum(
                1 for c in chunks if 0.55 <= _float_metric(c.get("quality_score", 1.0), 1.0) < 0.8
            ),
            "low": sum(1 for c in chunks if _float_metric(c.get("quality_score", 1.0), 1.0) < 0.55),
        },
    }
    findings = []
    if _float_metric(aggregate.get("duplicate_chunk_rate")) > 0.05:
        findings.append(
            {"severity": "warning", "message": "Duplicate chunk rate exceeds 5%", "stage": "L3"}
        )
    return {"aggregate": aggregate, "records": records, "findings": findings}
