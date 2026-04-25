"""Hamilton components for data ingestion pipeline.

Gold: reference data loading.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


def load_reference_data(
    gold_data_path: str,
) -> list[dict[str, Any]]:
    from src.ingestion.steps.load_reference_data import ReferenceDataLoader

    loader = ReferenceDataLoader()
    ref_docs = loader.load_reference_ranges_as_docs()
    return ref_docs


def write_reference_data(
    reference_chunks: list[dict[str, Any]],
    gold_chunks_dir: str,
) -> dict[str, Any]:
    """Write reference data to gold layer parquet file."""
    Path(gold_chunks_dir).mkdir(parents=True, exist_ok=True)
    path = Path(gold_chunks_dir) / "reference_data.parquet"
    df = pl.DataFrame(reference_chunks)
    df.write_parquet(path)
    return {
        "reference_count": len(reference_chunks),
        "path": str(path),
    }
