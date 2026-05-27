from __future__ import annotations

import logging
import random
from typing import Any

logger = logging.getLogger(__name__)


def _weighted_sample_chunks(
    chunks: list[dict[str, Any]],
    sample_rate: float,
    max_chunks: int,
    label: str = "sampling",
) -> list[dict[str, Any]]:
    if not chunks:
        return []

    target_count = min(max_chunks, max(1, int(len(chunks) * sample_rate)))
    population = list(chunks)
    sampled: list[dict[str, Any]] = []

    while population and len(sampled) < target_count:
        weights = [max(0.01, float(c.get("quality_score", 0.5)) ** 2) for c in population]
        selected = random.choices(population, weights=weights, k=1)[0]  # nosec B311
        sampled.append(selected)
        population = [chunk for chunk in population if chunk["id"] != selected["id"]]

    logger.info(f"{label}: selected {len(sampled)} chunks from {len(chunks)} total")
    return sampled
