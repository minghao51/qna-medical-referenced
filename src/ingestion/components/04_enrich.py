"""Hamilton components for data ingestion pipeline.

Gold: enrich chunks with HyPE questions, keywords, and summaries.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def hype_questions_path(gold_data_path: str) -> str:
    return str(Path(gold_data_path) / "hype_questions.parquet")


def keyword_extractions_path(gold_data_path: str) -> str:
    return str(Path(gold_data_path) / "keyword_extractions.parquet")


def summaries_path(gold_data_path: str) -> str:
    return str(Path(gold_data_path) / "summaries.parquet")


def generate_hype_for_chunks(
    all_chunks: list[dict[str, Any]],
    hype_config: dict[str, Any],
) -> dict[str, Any]:
    from src.infra.llm.qwen_client import get_client
    from src.ingestion.steps.hype import generate_hype_questions_for_chunks

    if not all_chunks:
        return {}

    client = get_client()
    hype_questions = asyncio.run(
        generate_hype_questions_for_chunks(
            chunks=all_chunks,
            client=client,
            sample_rate=hype_config.get("sample_rate", 0.1),
            max_chunks=hype_config.get("max_chunks", 500),
            questions_per_chunk=hype_config.get("questions_per_chunk", 2),
        )
    )
    return hype_questions


def apply_hype_questions(
    all_chunks: list[dict[str, Any]],
    hype_questions: dict[str, Any],
) -> list[dict[str, Any]]:
    if not all_chunks or not hype_questions:
        return all_chunks

    hype_ids = set(hype_questions.keys())
    for chunk in all_chunks:
        if chunk["id"] in hype_ids:
            chunk.setdefault("metadata", {})["hypothetical_questions"] = hype_questions[chunk["id"]]
    return all_chunks


def extract_keywords_for_chunks(
    all_chunks: list[dict[str, Any]],
    enrichment_config: dict[str, Any],
) -> dict[str, Any]:
    from src.infra.llm.qwen_client import get_client
    from src.ingestion.steps.enrich_chunks import enrich_chunks

    if not all_chunks:
        return {}

    client = get_client()
    results = asyncio.run(
        enrich_chunks(
            chunks=all_chunks,
            client=client,
            enable_keywords=True,
            enable_summaries=False,
            sample_rate=enrichment_config.get("sample_rate", 1.0),
            max_chunks=enrichment_config.get("max_chunks", 500),
        )
    )
    return results


def apply_keyword_extractions(
    all_chunks: list[dict[str, Any]],
    keyword_extractions: dict[str, Any],
) -> list[dict[str, Any]]:
    if not all_chunks or not keyword_extractions:
        return all_chunks

    for chunk in all_chunks:
        if chunk["id"] in keyword_extractions:
            chunk.setdefault("metadata", {})["extracted_keywords"] = keyword_extractions[chunk["id"]].get("keywords", [])
    return all_chunks


def generate_summaries_for_chunks(
    all_chunks: list[dict[str, Any]],
    enrichment_config: dict[str, Any],
) -> dict[str, Any]:
    from src.infra.llm.qwen_client import get_client
    from src.ingestion.steps.enrich_chunks import enrich_chunks

    if not all_chunks:
        return {}

    client = get_client()
    results = asyncio.run(
        enrich_chunks(
            chunks=all_chunks,
            client=client,
            enable_keywords=False,
            enable_summaries=True,
            sample_rate=enrichment_config.get("sample_rate", 1.0),
            max_chunks=enrichment_config.get("max_chunks", 500),
        )
    )
    return results


def apply_summaries(
    all_chunks: list[dict[str, Any]],
    summaries: dict[str, Any],
) -> list[dict[str, Any]]:
    if not all_chunks or not summaries:
        return all_chunks

    for chunk in all_chunks:
        if chunk["id"] in summaries:
            chunk.setdefault("metadata", {})["summary"] = summaries[chunk["id"]].get("summary", "")
    return all_chunks


def write_enriched_chunks(
    enriched_chunks: list[dict[str, Any]],
    gold_chunks_dir: str,
) -> dict[str, Any]:
    import polars as pl

    Path(gold_chunks_dir).mkdir(parents=True, exist_ok=True)
    path = Path(gold_chunks_dir) / "enriched_chunks.parquet"
    df = pl.DataFrame(enriched_chunks)
    df.write_parquet(path)
    return {
        "enriched_count": len(enriched_chunks),
        "path": str(path),
    }
