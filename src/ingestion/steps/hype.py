"""HyPE (Hypothetical Prompt Embedding) question generation at index time.

This module generates hypothetical questions for document chunks at ingestion time,
storing them in chunk metadata for zero-LLM-cost query expansion at retrieval time.

Reference:
    HyPE shifts HyDE-style computation from query time to index time, generating
    "what questions does this chunk answer?" at ingestion rather than "what answer
    would this query get?" at retrieval.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import cast

if False:
    from src.infra.llm.qwen_client import QwenClient

logger = logging.getLogger(__name__)

HYPE_BATCH_SIZE = 10


def _weighted_sample_chunks(
    chunks: list[dict],
    sample_rate: float,
    max_chunks: int,
) -> list[dict]:
    """Select chunks using weighted random sampling by quality_score.

    Args:
        chunks: List of chunk dicts with 'id' and 'quality_score'
        sample_rate: Fraction of chunks to select (0.0-1.0)
        max_chunks: Maximum number of chunks to return

    Returns:
        List of sampled chunk dicts
    """
    if not chunks:
        return []

    target_count = min(max_chunks, max(1, int(len(chunks) * sample_rate)))
    population = list(chunks)
    sampled: list[dict] = []

    while population and len(sampled) < target_count:
        weights = [max(0.01, float(c.get("quality_score", 0.5)) ** 2) for c in population]
        selected = random.choices(population, weights=weights, k=1)[0]
        sampled.append(selected)
        population = [chunk for chunk in population if chunk["id"] != selected["id"]]

    logger.info(f"HyPE sampling: selected {len(sampled)} chunks from {len(chunks)} total")
    return sampled


async def generate_hype_questions_for_chunks(
    chunks: list[dict],
    client: "QwenClient",
    sample_rate: float,
    max_chunks: int,
    questions_per_chunk: int,
) -> dict[str, list[str]]:
    """Generate hypothetical questions for a sample of chunks.

    Args:
        chunks: All document chunks
        client: QwenClient for LLM generation
        sample_rate: Fraction of chunks to sample (0.0-1.0)
        max_chunks: Maximum number of chunks to process
        questions_per_chunk: Number of questions per chunk (1-2)

    Returns:
        Dict mapping chunk_id -> list of hypothetical question strings
    """
    from src.rag.hyde import generate_hypothetical_questions

    sampled_chunks = _weighted_sample_chunks(chunks, sample_rate, max_chunks)
    if not sampled_chunks:
        return {}

    hype_questions: dict[str, list[str]] = {}
    errors = 0

    for i in range(0, len(sampled_chunks), HYPE_BATCH_SIZE):
        batch = sampled_chunks[i : i + HYPE_BATCH_SIZE]
        tasks = [
            generate_hypothetical_questions(
                chunk=chunk["content"],
                client=client,
                count=questions_per_chunk,
            )
            for chunk in batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for chunk, result in zip(batch, results):
            if isinstance(result, Exception):
                logger.warning(f"HyPE generation failed for chunk {chunk['id']}: {result}")
                errors += 1
                continue
            questions: list[str] = cast(list[str], result)
            if questions:
                hype_questions[chunk["id"]] = questions

    logger.info(
        f"HyPE generation complete: {len(hype_questions)} chunks with questions, "
        f"{errors} errors out of {len(sampled_chunks)} sampled"
    )
    return hype_questions
