"""Search-mode ablations (semantic / BM25 / RRF hybrid ± diversification)."""

from __future__ import annotations

import logging
from typing import Any

from src.evals.assessment.retrieval_eval import evaluate_retrieval

logger = logging.getLogger(__name__)


def retrieval_ablation_configs(
    base_options: dict[str, Any] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    base = dict(base_options or {})
    return [
        ("rrf_hybrid", {**base, "search_mode": "rrf_hybrid", "enable_diversification": False}),
        ("rrf_hybrid_mmr", {**base, "search_mode": "rrf_hybrid", "enable_diversification": True}),
        (
            "semantic_only_diversified",
            {**base, "search_mode": "semantic_only", "enable_diversification": True},
        ),
        (
            "bm25_only_diversified",
            {**base, "search_mode": "bm25_only", "enable_diversification": True},
        ),
    ]


def run_retrieval_ablations(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for name, options in retrieval_ablation_configs(base_options):
        _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=options)
        outputs[name] = metrics
    return outputs
