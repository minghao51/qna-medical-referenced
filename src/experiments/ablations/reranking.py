"""Cross-encoder reranking and MMR diversification ablations."""

from __future__ import annotations

import logging
from typing import Any

from src.evals.assessment.retrieval_eval import evaluate_retrieval

logger = logging.getLogger(__name__)


def reranking_ablation_configs(
    base_options: dict[str, Any] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Ablation configs for cross-encoder reranking evaluation."""
    base = dict(base_options or {})
    return [
        (
            "no_reranking",
            {
                **base,
                "enable_diversification": False,
                "enable_reranking": False,
                "reranking_mode": "cross_encoder",
            },
        ),
        (
            "cross_encoder_only",
            {
                **base,
                "enable_diversification": False,
                "enable_reranking": True,
                "reranking_mode": "cross_encoder",
            },
        ),
        (
            "mmr_only",
            {
                **base,
                "enable_diversification": True,
                "enable_reranking": False,
                "reranking_mode": "mmr",
            },
        ),
        (
            "both_reranking",
            {
                **base,
                "enable_diversification": True,
                "enable_reranking": True,
                "reranking_mode": "both",
            },
        ),
    ]


def run_reranking_ablations(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run cross-encoder reranking ablation study."""
    outputs: dict[str, Any] = {}
    for name, options in reranking_ablation_configs(base_options):
        _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=options)
        outputs[name] = metrics
    if "no_reranking" in outputs:
        baseline = outputs["no_reranking"]
        for name in outputs:
            if name != "no_reranking":
                variant = outputs[name]
                variant["rerank_improvement_delta"] = variant.get(
                    "hit_rate_at_k", 0
                ) - baseline.get("hit_rate_at_k", 0)
                variant["rerank_mrr_delta"] = variant.get("mrr", 0) - baseline.get("mrr", 0)
                variant["rerank_exact_chunk_delta"] = variant.get(
                    "exact_chunk_hit_rate", 0
                ) - baseline.get("exact_chunk_hit_rate", 0)
                variant["rerank_evidence_delta"] = variant.get(
                    "evidence_hit_rate", 0
                ) - baseline.get("evidence_hit_rate", 0)
                variant["rerank_latency_delta_ms"] = variant.get(
                    "rerank_latency_p50_ms", 0
                ) - baseline.get("rerank_latency_p50_ms", 0)
    return outputs
