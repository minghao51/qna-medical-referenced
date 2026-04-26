"""LLM-based chunk enrichment: keyword extraction and summarization.

This module generates medical entity keywords and chunk summaries at ingestion
time, storing them in chunk metadata for enhanced retrieval:

- **Keywords**: 5-10 medical entities (conditions, drugs, procedures, specialties)
  indexed by BM25 and used for query-time keyword boosting.
- **Summaries**: 1-2 sentence summaries prepended to chunk content before embedding
  to improve semantic match for overview queries.

Both are generated in a single LLM call per chunk to minimize API cost.

Usage:
    from src.ingestion.steps.enrich_chunks import enrich_chunks
    results = await enrich_chunks(
        chunks=chunks,
        client=client,
        enable_keywords=True,
        enable_summaries=True,
        sample_rate=1.0,
        max_chunks=500,
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.infra.llm.qwen_client import QwenClient

logger = logging.getLogger(__name__)

ENRICH_BATCH_SIZE = 10

ENRICH_PROMPT_TEMPLATE = """Given this medical document chunk, do TWO things:

1. EXTRACT KEYWORDS: List 5-10 key medical entities found in the text. Include:
   - Conditions/diseases (e.g., hypertension, myocardial infarction, diabetes)
   - Medications (brand and generic names, e.g., atorvastatin, Lipitor)
   - Procedures and tests (e.g., ECG, HbA1c, coronary angiography)
   - Medical specialties and body systems (e.g., cardiology, endocrine)

2. SUMMARIZE: Write a 1-2 sentence summary of the key information in this chunk.

Document chunk:
{chunk}

Return ONLY valid JSON with this exact structure (no markdown, no explanation):
{{"keywords": ["keyword1", "keyword2", ...], "summary": "summary text"}}

Rules:
- Keywords must be actual terms present in or directly implied by the text
- Do NOT hallucinate entities not supported by the text
- Summary should capture the main clinical recommendation or finding
- If the chunk is too short or lacks medical content, return empty keywords and a brief summary"""


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
        selected = random.choices(population, weights=weights, k=1)[0]  # nosec B311
        sampled.append(selected)
        population = [chunk for chunk in population if chunk["id"] != selected["id"]]

    logger.info(
        f"Enrichment sampling: selected {len(sampled)} chunks from {len(chunks)} total"
    )
    return sampled


def _parse_enrich_result(response: str) -> dict[str, Any]:
    """Parse LLM response into keywords and summary.

    Args:
        response: Raw LLM response string

    Returns:
        Dict with 'keywords' (list[str]) and 'summary' (str)
    """
    result: dict[str, Any] = {"keywords": [], "summary": ""}

    # Try to extract JSON from the response
    text = response.strip()

    # Remove markdown code blocks if present
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break

    # Find JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        logger.warning(f"No JSON found in enrichment response: {text[:200]}")
        return result

    json_str = text[start : end + 1]

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse JSON from enrichment response: {json_str[:200]}")
        return result

    if not isinstance(parsed, dict):
        return result

    # Extract keywords
    keywords = parsed.get("keywords", [])
    if isinstance(keywords, list):
        result["keywords"] = [
            str(k).strip().lower()
            for k in keywords
            if isinstance(k, str) and k.strip()
        ][:15]  # Cap at 15 to prevent bloat

    # Extract summary
    summary = parsed.get("summary", "")
    if isinstance(summary, str):
        result["summary"] = summary.strip()

    return result


async def _enrich_chunk_batch(
    chunks_batch: list[dict],
    client: QwenClient,
    enable_keywords: bool,
    enable_summaries: bool,
) -> dict[str, dict[str, Any]]:
    """Enrich a batch of chunks with keywords and/or summaries.

    Args:
        chunks_batch: List of chunk dicts to enrich
        client: QwenClient for LLM generation
        enable_keywords: Whether to extract keywords
        enable_summaries: Whether to generate summaries

    Returns:
        Dict mapping chunk_id -> {"keywords": [...], "summary": "..."}
    """
    results: dict[str, dict[str, Any]] = {}

    # Run synchronous generate in executor threads for concurrency
    loop = asyncio.get_event_loop()
    tasks = []
    for chunk in chunks_batch:
        prompt = ENRICH_PROMPT_TEMPLATE.format(chunk=chunk["content"])
        chunk_id = chunk["id"]

        async def generate_with_timeout(prompt=prompt, chunk_id=chunk_id) -> str:
            try:
                async with asyncio.timeout(30):  # 30s timeout per chunk
                    return await loop.run_in_executor(None, client.generate, prompt, "")
            except TimeoutError:
                logger.warning("Enrichment timeout for chunk %s", chunk_id)
                return ""
            except Exception as e:
                logger.exception("Enrichment failed for chunk %s: %s", chunk_id, e)
                return ""

        tasks.append((chunk["id"], generate_with_timeout()))

    gathered = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)

    for (chunk_id, _), response in zip(tasks, gathered, strict=False):
        if isinstance(response, Exception):
            logger.warning("Enrichment failed for chunk %s: %s", chunk_id, response)
            continue

        parsed = _parse_enrich_result(str(response))

        # Only store what was requested
        entry: dict[str, Any] = {}
        if enable_keywords and parsed["keywords"]:
            entry["keywords"] = parsed["keywords"]
        if enable_summaries and parsed["summary"]:
            entry["summary"] = parsed["summary"]

        if entry:
            results[chunk_id] = entry

    return results


async def enrich_chunks(
    chunks: list[dict],
    client: QwenClient,
    *,
    enable_keywords: bool = True,
    enable_summaries: bool = True,
    sample_rate: float = 1.0,
    max_chunks: int = 500,
) -> dict[str, dict[str, Any]]:
    """Enrich document chunks with LLM-extracted keywords and/or summaries.

    Args:
        chunks: All document chunks from the pipeline
        client: QwenClient for LLM generation
        enable_keywords: Whether to extract medical entity keywords
        enable_summaries: Whether to generate chunk summaries
        sample_rate: Fraction of chunks to process (0.0-1.0), weighted by quality_score
        max_chunks: Maximum number of chunks to process

    Returns:
        Dict mapping chunk_id -> {"keywords": [...], "summary": "..."}
        Only includes keys for the enabled features.
    """
    if not enable_keywords and not enable_summaries:
        logger.info("Enrichment skipped: both keywords and summaries are disabled")
        return {}

    sampled_chunks = _weighted_sample_chunks(chunks, sample_rate, max_chunks)
    if not sampled_chunks:
        return {}

    feature_label = []
    if enable_keywords:
        feature_label.append("keywords")
    if enable_summaries:
        feature_label.append("summaries")
    logger.info(
        f"Enriching {len(sampled_chunks)} chunks with {', '.join(feature_label)}..."
    )

    enrichment_results: dict[str, dict[str, Any]] = {}
    errors = 0

    for i in range(0, len(sampled_chunks), ENRICH_BATCH_SIZE):
        batch = sampled_chunks[i : i + ENRICH_BATCH_SIZE]
        batch_results = await _enrich_chunk_batch(
            batch, client, enable_keywords, enable_summaries
        )
        enrichment_results.update(batch_results)
        errors += len(batch) - len(batch_results)

    logger.info(
        f"Enrichment complete: {len(enrichment_results)} chunks enriched, "
        f"{errors} errors out of {len(sampled_chunks)} sampled"
    )
    return enrichment_results


def apply_enrichment_to_chunks(
    chunks: list[dict],
    enrichment_results: dict[str, dict[str, Any]],
    *,
    enable_keywords: bool = True,
    enable_summaries: bool = True,
) -> int:
    """Apply enrichment results back to the chunk list in-place.

    Args:
        chunks: List of chunk dicts (modified in-place)
        enrichment_results: Output from enrich_chunks()
        enable_keywords: Whether to apply keywords
        enable_summaries: Whether to apply summaries

    Returns:
        Number of chunks that were enriched
    """
    enriched_count = 0

    for chunk in chunks:
        chunk_id = chunk["id"]
        if chunk_id not in enrichment_results:
            continue

        result = enrichment_results[chunk_id]
        metadata = chunk.setdefault("metadata", {})

        if enable_keywords and "keywords" in result:
            metadata["extracted_keywords"] = result["keywords"]

        if enable_summaries and "summary" in result:
            metadata["chunk_summary"] = result["summary"]

        enriched_count += 1

    logger.info(f"Applied enrichment to {enriched_count} chunks")
    return enriched_count
