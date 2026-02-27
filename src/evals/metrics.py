"""Retrieval and aggregate metric helpers."""

from __future__ import annotations

import math
from typing import Iterable


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def percentile(values: Iterable[float], pct: float) -> float:
    vals = sorted(float(v) for v in values)
    if not vals:
        return 0.0
    if pct <= 0:
        return vals[0]
    if pct >= 100:
        return vals[-1]
    idx = (len(vals) - 1) * (pct / 100.0)
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    frac = idx - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def hit_rate_at_k(binary_relevance: list[int]) -> float:
    return 1.0 if any(binary_relevance) else 0.0


def precision_at_k(binary_relevance: list[int], k: int | None = None) -> float:
    if k is None:
        k = len(binary_relevance)
    if k <= 0:
        return 0.0
    rel = binary_relevance[:k]
    return sum(rel) / len(rel) if rel else 0.0


def recall_at_k(binary_relevance: list[int], total_relevant: int) -> float:
    if total_relevant <= 0:
        return 0.0
    return min(sum(binary_relevance), total_relevant) / total_relevant


def reciprocal_rank(binary_relevance: list[int]) -> float:
    for idx, val in enumerate(binary_relevance, start=1):
        if val:
            return 1.0 / idx
    return 0.0


def ndcg_at_k(binary_relevance: list[int], k: int | None = None) -> float:
    rel = binary_relevance[:k] if k else list(binary_relevance)
    if not rel:
        return 0.0
    dcg = 0.0
    for i, r in enumerate(rel, start=1):
        if r:
            dcg += 1.0 / math.log2(i + 1)
    ideal_count = sum(rel)
    if ideal_count == 0:
        return 0.0
    idcg = 0.0
    for i in range(1, ideal_count + 1):
        idcg += 1.0 / math.log2(i + 1)
    return dcg / idcg if idcg else 0.0

