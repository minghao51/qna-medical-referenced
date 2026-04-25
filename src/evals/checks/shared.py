"""Shared helpers for step quality checks."""

from __future__ import annotations

import statistics


def safe_median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def safe_mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def source_type_from_name(name: str) -> str:
    lowered = name.lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if "reference_ranges.csv" in lowered:
        return "csv"
    if lowered.endswith((".md", ".html")):
        return "html"
    return "other"


def count_false(records: list[dict[str, object]], key: str) -> int:
    return sum(1 for r in records if not r.get(key))


def longest_suffix_prefix_overlap(a: str, b: str, max_len: int) -> int:
    limit = min(max_len, len(a), len(b))
    for size in range(limit, 0, -1):
        if a[-size:] == b[:size]:
            return size
    return 0
