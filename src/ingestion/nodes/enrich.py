"""Hamilton components for data ingestion pipeline.

Gold: enrich chunks with HyPE questions, keywords, and summaries.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.ingestion.steps._utils import run_async

logger = logging.getLogger(__name__)


def hype_questions(
    all_chunks: list[dict[str, Any]],
    hype_config: dict[str, Any],
    enable_hype: bool,
) -> dict[str, Any]:
    from src.infra.llm.qwen_client import get_client
    from src.ingestion.steps.hype import generate_hype_questions_for_chunks

    if not enable_hype or not all_chunks:
        return {}

    client = get_client()
    return run_async(
        generate_hype_questions_for_chunks(
            chunks=all_chunks,
            client=client,
            sample_rate=hype_config.get("sample_rate", 0.1),
            max_chunks=hype_config.get("max_chunks", 500),
            questions_per_chunk=hype_config.get("questions_per_chunk", 2),
        )
    )


def enrichment_results(
    all_chunks: list[dict[str, Any]],
    enrichment_config: dict[str, Any],
    enable_keyword_extraction: bool,
    enable_chunk_summaries: bool,
) -> dict[str, Any]:
    from src.infra.llm.qwen_client import get_client
    from src.ingestion.steps.enrich_chunks import enrich_chunks

    if (not enable_keyword_extraction and not enable_chunk_summaries) or not all_chunks:
        return {}

    client = get_client()
    return run_async(
        enrich_chunks(
            chunks=all_chunks,
            client=client,
            enable_keywords=enable_keyword_extraction,
            enable_summaries=enable_chunk_summaries,
            sample_rate=enrichment_config.get("sample_rate", 1.0),
            max_chunks=enrichment_config.get("max_chunks", 500),
        )
    )


def enriched_chunks(
    all_chunks: list[dict[str, Any]],
    hype_questions: dict[str, Any],
    enrichment_results: dict[str, Any],
    enable_keyword_extraction: bool,
    enable_chunk_summaries: bool,
) -> list[dict[str, Any]]:
    from src.ingestion.steps.enrich_chunks import apply_enrichment_to_chunks

    if not all_chunks:
        return []

    if hype_questions:
        hype_ids = set(hype_questions.keys())
        for chunk in all_chunks:
            if chunk["id"] in hype_ids:
                chunk.setdefault("metadata", {})["hypothetical_questions"] = hype_questions[
                    chunk["id"]
                ]

    if enrichment_results:
        apply_enrichment_to_chunks(
            all_chunks,
            enrichment_results,
            enable_keywords=enable_keyword_extraction,
            enable_summaries=enable_chunk_summaries,
        )

    return all_chunks


def write_enriched_chunks(
    enriched_chunks: list[dict[str, Any]],
    gold_chunks_dir: str,
) -> dict[str, Any]:
    import polars as pl

    Path(gold_chunks_dir).mkdir(parents=True, exist_ok=True)
    path = Path(gold_chunks_dir) / "enriched_chunks.parquet"
    if not enriched_chunks:
        logger.warning("No enriched chunks to write; skipping %s", path)
        return {
            "enriched_count": 0,
            "path": str(path),
        }
    # An empty dict infers a field-less struct that parquet cannot store.
    rows = [{**c, "metadata": c.get("metadata") or None} for c in enriched_chunks]
    df = pl.DataFrame(rows)
    df.write_parquet(path)
    return {
        "enriched_count": len(enriched_chunks),
        "path": str(path),
    }
