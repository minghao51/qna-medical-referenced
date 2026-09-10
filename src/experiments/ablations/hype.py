"""HyPE (index-time hypothetical questions) ablations, with optional re-ingestion."""

from __future__ import annotations

import logging
from typing import Any

from src.evals.assessment.retrieval_eval import evaluate_retrieval

logger = logging.getLogger(__name__)


def hype_ablation_configs(
    base_options: dict[str, Any] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Ablation configs for HyPE (Hypothetical Prompt Embedding) evaluation.

    Tests the impact of HyPE at different sample rates and in combination with HyDE.
    HyPE generates hypothetical questions at index time, storing them in chunk metadata
    for zero-LLM-cost query expansion at retrieval time.
    """
    base = dict(base_options or {})
    return [
        ("hype_disabled", {**base, "enable_hype": False, "enable_hyde": False}),
        ("hype_10pct", {**base, "enable_hype": True, "enable_hyde": False}),
        (
            "hype_50pct",
            {**base, "enable_hype": True, "enable_hyde": False, "hype_sample_rate": 0.5},
        ),
        (
            "hype_100pct",
            {**base, "enable_hype": True, "enable_hyde": False, "hype_sample_rate": 1.0},
        ),
        ("hyde_only", {**base, "enable_hype": False, "enable_hyde": True}),
        ("hype_plus_hyde", {**base, "enable_hype": True, "enable_hyde": True}),
    ]


def run_hype_ablations(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run HyPE ablation study to evaluate HyPE impact on retrieval quality.

    Note: This version assumes the index already has HyPE questions stored.
    For full ablation with re-ingestion, use run_hype_ablations_with_reingest.
    """
    outputs: dict[str, Any] = {}
    for name, options in hype_ablation_configs(base_options):
        _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=options)
        outputs[name] = metrics
    return outputs


def run_hype_ablations_with_reingest(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
    base_collection_name: str | None = None,
    reconfigure_and_rebuild_fn=None,
) -> dict[str, Any]:
    """Run HyPE ablation with automatic re-ingestion for each variant.

    HyPE is an index-time feature, so each variant requires rebuilding the index
    with different HyPE settings (sample rate, questions per chunk, etc.).

    Args:
        dataset: Evaluation dataset
        top_k: Retrieval top-k
        base_options: Base retrieval options
        base_collection_name: Base name for ChromaDB collections (default: settings.storage.collection_name)
        reconfigure_and_rebuild_fn: Callback that accepts hype_config dict and rebuilds the index.
            The hype_config dict contains: enable_hype, hype_sample_rate, hype_questions_per_chunk

    Returns:
        Dict mapping variant name to metrics dict
    """
    from src.config import settings

    collection_base = base_collection_name or settings.storage.collection_name
    outputs: dict[str, Any] = {}
    configs = hype_ablation_configs(base_options)

    for name, options in configs:
        hype_config = {
            "enable_hype": options.get("enable_hype", False),
            "hype_sample_rate": options.get("hype_sample_rate", settings.hype.sample_rate),
            "hype_questions_per_chunk": options.get(
                "hype_questions_per_chunk", settings.hype.questions_per_chunk
            ),
        }
        variant_collection = f"{collection_base}_{name}"

        if reconfigure_and_rebuild_fn:
            logger.info(
                "Rebuilding index for HyPE variant: %s (collection: %s)", name, variant_collection
            )
            reconfigure_and_rebuild_fn(
                hype_config=hype_config,
                collection_name=variant_collection,
            )

        _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=options)
        metrics["collection_name"] = variant_collection
        metrics["hype_config"] = hype_config
        outputs[name] = metrics

    return outputs
