"""Hamilton components for data ingestion pipeline.

Silver→Gold: chunking documents into smaller units.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


def gold_data_path(project_root: Path) -> str:
    return str(project_root / "data" / "03_gold")


def gold_chunks_dir(gold_data_path: str) -> str:
    return str(Path(gold_data_path) / "chunks")


def chunk_silver_documents(
    silver_documents_dir: str,
    source_type: str = "pdf",
) -> list[dict[str, Any]]:
    from src.ingestion.steps.chunk_text import chunk_documents

    if source_type == "pdf":
        path = Path(silver_documents_dir) / "pdf_documents.parquet"
    else:
        path = Path(silver_documents_dir) / "markdown_documents.parquet"

    if not path.exists():
        return []

    df = pl.read_parquet(path)
    docs = df.to_dicts()
    chunks = chunk_documents(docs)
    return chunks


def all_chunks(
    pdf_chunks: list[dict[str, Any]],
    markdown_chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not pdf_chunks and not markdown_chunks:
        return []
    return pdf_chunks + markdown_chunks


def write_gold_chunks(
    all_chunks: list[dict[str, Any]],
    gold_chunks_dir: str,
) -> dict[str, Any]:
    Path(gold_chunks_dir).mkdir(parents=True, exist_ok=True)
    path = Path(gold_chunks_dir) / "raw_chunks.parquet"
    df = pl.DataFrame(all_chunks)
    df.write_parquet(path)
    return {
        "chunk_count": len(all_chunks),
        "path": str(path),
    }
