"""Diversity parameter sweep (MMR lambda, overfetch, per-source caps)."""

from __future__ import annotations

import logging
from typing import Any

from src.evals.assessment.retrieval_eval import evaluate_retrieval

logger = logging.getLogger(__name__)


def run_diversity_sweep(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
    mmr_lambda_values: list[float] | None = None,
    overfetch_multipliers: list[int] | None = None,
    max_chunks_per_source_page_values: list[int] | None = None,
    max_chunks_per_source_values: list[int] | None = None,
) -> list[dict[str, Any]]:
    lambdas = mmr_lambda_values or [0.5, 0.75, 0.9]
    overfetches = overfetch_multipliers or [2, 4]
    per_page_caps = max_chunks_per_source_page_values or [1, 2]
    per_source_caps = max_chunks_per_source_values or [2, 3]
    rows: list[dict[str, Any]] = []
    base = dict(base_options or {})
    for mmr_lambda in lambdas:
        for overfetch in overfetches:
            for per_page in per_page_caps:
                for per_source in per_source_caps:
                    opts = {
                        **base,
                        "search_mode": "rrf_hybrid",
                        "enable_diversification": True,
                        "mmr_lambda": mmr_lambda,
                        "overfetch_multiplier": overfetch,
                        "max_chunks_per_source_page": per_page,
                        "max_chunks_per_source": per_source,
                    }
                    _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=opts)
                    rows.append(
                        {
                            "retrieval_options": opts,
                            "query_count": metrics.get("query_count", 0),
                            "exact_chunk_hit_rate": metrics.get("exact_chunk_hit_rate", 0.0),
                            "evidence_hit_rate": metrics.get("evidence_hit_rate", 0.0),
                            "mrr": metrics.get("mrr", 0.0),
                            "duplicate_source_ratio_mean": metrics.get(
                                "duplicate_source_ratio_mean", 0.0
                            ),
                            "tradeoff_score": (
                                float(metrics.get("exact_chunk_hit_rate", 0.0))
                                + float(metrics.get("evidence_hit_rate", 0.0))
                                - float(metrics.get("duplicate_source_ratio_mean", 0.0))
                            ),
                        }
                    )
    rows.sort(
        key=lambda r: (r["tradeoff_score"], r["exact_chunk_hit_rate"], r["evidence_hit_rate"]),
        reverse=True,
    )
    return rows
