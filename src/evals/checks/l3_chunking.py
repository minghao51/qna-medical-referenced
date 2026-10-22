"""L3 chunking quality checks over the chunks emitted by the selected run."""

from __future__ import annotations

import hashlib
import itertools
from collections import Counter, defaultdict
from typing import Any

from src.evals.checks.shared import longest_suffix_prefix_overlap, safe_mean, safe_median


def _float_metric(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def assess_l3_chunking_quality(
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    *,
    chunks: list[dict[str, Any]] | None = None,
    document_count: int | None = None,
) -> dict[str, Any]:
    """Assess supplied emitted chunks; without them the check is explicitly incomplete."""
    config = {"chunk_size_config": chunk_size, "chunk_overlap_config": chunk_overlap}
    if chunks is None:
        aggregate: dict[str, Any] = {
            **config,
            "measurement_status": "incomplete",
            "measurement_reason": "actual_emitted_chunks_not_supplied",
            "document_count": document_count,
            "chunk_count": None,
            "chunk_length_median": None,
            "chunk_length_mean": None,
            "duplicate_chunk_rate": None,
            "boundary_cut_rate": None,
            "observed_overlap_mean": None,
            "section_integrity_rate": None,
            "table_row_split_violations": None,
            "low_quality_chunk_exclusion_rate": None,
            "chunk_quality_histogram": None,
        }
        return {
            "aggregate": aggregate,
            "records": [],
            "findings": [
                {
                    "severity": "warning",
                    "message": "L3 measurements unavailable without actual emitted chunks",
                    "stage": "L3",
                }
            ],
        }

    if document_count is not None and (
        isinstance(document_count, bool)
        or not isinstance(document_count, int)
        or document_count < 0
    ):
        raise ValueError("document_count must be a non-negative integer or None")

    records: list[dict[str, Any]] = []
    duplicate_hashes: Counter[str] = Counter()
    boundary_cut_count = 0
    overlap_values: list[int] = []
    groups: dict[tuple[str, int | None], list[dict[str, Any]]] = defaultdict(list)

    for chunk in chunks:
        content = str(chunk.get("content", ""))
        chunk_hash = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
        duplicate_hashes[chunk_hash] += 1
        if content and content[-1].isalnum():
            boundary_cut_count += 1
        source = str(chunk.get("source", ""))
        page_value = chunk.get("page")
        page = (
            page_value if isinstance(page_value, int) and not isinstance(page_value, bool) else None
        )
        groups[(source, page)].append({**chunk, "content": content})
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

    for group in groups.values():
        for first, second in itertools.pairwise(group):
            first_content = str(first.get("content", ""))
            second_content = str(second.get("content", ""))
            overlap_limit = (
                chunk_overlap
                if chunk_overlap is not None
                else min(len(first_content), len(second_content))
            )
            overlap_values.append(
                longest_suffix_prefix_overlap(first_content, second_content, overlap_limit)
            )

    lengths = [record["length_chars"] for record in records]
    duplicate_chunks = sum(count - 1 for count in duplicate_hashes.values() if count > 1)
    chunk_count = len(chunks)
    observed_document_count = (
        document_count
        if document_count is not None
        else len({str(chunk.get("source", "")) for chunk in chunks if chunk.get("source")})
    )
    low_quality_excluded = 0
    aggregate = {
        **config,
        "measurement_status": "measured",
        "measurement_reason": None,
        "document_count": observed_document_count,
        "chunk_count": chunk_count,
        "chunk_length_median": safe_median([float(value) for value in lengths])
        if lengths
        else None,
        "chunk_length_mean": safe_mean([float(value) for value in lengths]) if lengths else None,
        "duplicate_chunk_rate": duplicate_chunks / chunk_count if chunk_count else None,
        "boundary_cut_rate": boundary_cut_count / chunk_count if chunk_count else None,
        "observed_overlap_mean": safe_mean([float(value) for value in overlap_values])
        if overlap_values
        else None,
        "section_integrity_rate": (
            sum(1 for chunk in chunks if chunk.get("section_path")) / chunk_count
            if chunk_count
            else None
        ),
        "table_row_split_violations": sum(
            1
            for chunk in chunks
            if chunk.get("content_type") == "table"
            and len(str(chunk.get("content", "")).splitlines()) == 1
        ),
        "low_quality_chunk_exclusion_rate": (
            low_quality_excluded / max(1, chunk_count + low_quality_excluded)
            if chunk_count
            else None
        ),
        "chunk_quality_histogram": {
            "high": sum(
                1 for chunk in chunks if _float_metric(chunk.get("quality_score", 1.0), 1.0) >= 0.8
            ),
            "medium": sum(
                1
                for chunk in chunks
                if 0.55 <= _float_metric(chunk.get("quality_score", 1.0), 1.0) < 0.8
            ),
            "low": sum(
                1 for chunk in chunks if _float_metric(chunk.get("quality_score", 1.0), 1.0) < 0.55
            ),
        },
    }
    findings = []
    if _float_metric(aggregate.get("duplicate_chunk_rate")) > 0.05:
        findings.append(
            {"severity": "warning", "message": "Duplicate chunk rate exceeds 5%", "stage": "L3"}
        )
    return {"aggregate": aggregate, "records": records, "findings": findings}
