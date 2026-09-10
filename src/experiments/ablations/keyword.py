"""Ingestion-time keyword-extraction and chunk-summary ablations."""

from __future__ import annotations

import logging
from typing import Any

from src.evals.assessment.retrieval_eval import evaluate_retrieval

logger = logging.getLogger(__name__)


def keyword_ablation_configs(
    base_options: dict[str, Any] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Ablation configs for LLM-extracted keyword and chunk summary evaluation.

    Tests the impact of keyword extraction and chunk summarization at ingestion time
    on retrieval quality. Variants:
    - baseline: Neither keywords nor summaries
    - keywords_only: LLM-extracted keywords for BM25 boosting
    - summaries_only: Chunk summaries prepended to content
    - both: Keywords + summaries combined
    """
    base = dict(base_options or {})
    return [
        (
            "baseline",
            {**base, "enable_keyword_extraction": False, "enable_chunk_summaries": False},
        ),
        (
            "keywords_only",
            {**base, "enable_keyword_extraction": True, "enable_chunk_summaries": False},
        ),
        (
            "summaries_only",
            {**base, "enable_keyword_extraction": False, "enable_chunk_summaries": True},
        ),
        (
            "both",
            {**base, "enable_keyword_extraction": True, "enable_chunk_summaries": True},
        ),
    ]


def run_keyword_ablations(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run keyword extraction and chunk summary ablation study.

    Evaluates the impact of LLM-extracted keywords and chunk summaries
    on retrieval quality across four variants: baseline, keywords_only,
    summaries_only, and both.
    """
    outputs: dict[str, Any] = {}
    for name, options in keyword_ablation_configs(base_options):
        _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=options)
        outputs[name] = metrics
    return outputs


def run_keyword_ablations_with_reingest(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
    base_collection_name: str | None = None,
    reconfigure_and_rebuild_fn=None,
) -> dict[str, Any]:
    """Run keyword/summaries ablation with automatic re-ingestion for each variant."""
    from src.config import settings

    collection_base = base_collection_name or settings.storage.collection_name
    outputs: dict[str, Any] = {}

    for name, options in keyword_ablation_configs(base_options):
        enrichment_config = {
            "enable_keyword_extraction": bool(options.get("enable_keyword_extraction", False)),
            "enable_chunk_summaries": bool(options.get("enable_chunk_summaries", False)),
            "keyword_extraction_sample_rate": options.get(
                "keyword_extraction_sample_rate", settings.enrichment.keyword_extraction_sample_rate
            ),
            "keyword_extraction_max_chunks": options.get(
                "keyword_extraction_max_chunks", settings.enrichment.keyword_extraction_max_chunks
            ),
        }
        variant_collection = f"{collection_base}_{name}"

        if reconfigure_and_rebuild_fn:
            logger.info(
                "Rebuilding index for keyword variant: %s (collection: %s)",
                name,
                variant_collection,
            )
            reconfigure_and_rebuild_fn(
                enrichment_config=enrichment_config,
                collection_name=variant_collection,
            )

        _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=options)
        metrics["collection_name"] = variant_collection
        metrics["enrichment_config"] = enrichment_config
        outputs[name] = metrics

    return outputs
