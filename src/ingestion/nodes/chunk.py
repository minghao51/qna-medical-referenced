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


def _chunk_silver_documents(
    parquet_path: str | None,
    source_type: str,
) -> list[dict[str, Any]]:
    from src.ingestion.steps.chunking import chunk_documents

    if not parquet_path or not Path(parquet_path).exists():
        return []

    df = pl.read_parquet(parquet_path)
    docs = df.to_dicts()
    # Silver documents carry the rich loader shape (roadmap P3.2 passthrough:
    # id/metadata/structured_blocks/pages round-trip as struct columns). The
    # legacy path/text fallback keys remain for older parquets written before
    # the passthrough.
    for doc in docs:
        doc.setdefault("source", doc.get("path", ""))
        doc.setdefault("content", doc.get("text", ""))
    chunks = chunk_documents(docs)
    return chunks


def pdf_chunks(write_silver_documents: dict[str, Any]) -> list[dict[str, Any]]:
    """Chunk the silver PDF parquet written by ``write_silver_documents``.

    Consuming the write node's output (rather than re-deriving the path from
    config) makes the silver→gold handoff a real DAG edge, so executing any
    gold-or-later node always parses and writes silver first.
    """
    return _chunk_silver_documents(write_silver_documents.get("pdf_path"), "pdf")


def markdown_chunks(write_silver_documents: dict[str, Any]) -> list[dict[str, Any]]:
    """Chunk the silver Markdown parquet written by ``write_silver_documents``."""
    return _chunk_silver_documents(write_silver_documents.get("markdown_path"), "markdown")


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
    if not all_chunks:
        logger.warning("No chunks to write; skipping %s", path)
        return {
            "chunk_count": 0,
            "path": str(path),
        }
    # An empty dict infers a field-less struct that parquet cannot store.
    rows = [{**c, "metadata": c.get("metadata") or None} for c in all_chunks]
    df = pl.DataFrame(rows)
    df.write_parquet(path)
    return {
        "chunk_count": len(all_chunks),
        "path": str(path),
    }
