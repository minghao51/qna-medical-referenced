"""Hamilton components for data ingestion pipeline.

Gold→Platinum: embedding generation and vector storage.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def platinum_data_path(project_root: Path) -> str:
    return str(project_root / "data" / "04_platinum")


def platinum_embeddings_dir(platinum_data_path: str) -> str:
    return str(Path(platinum_data_path) / "embeddings")


def embed_chunks(
    enriched_chunks: list[dict[str, Any]],
    reference_chunks: list[dict[str, Any]],
    force_rebuild: bool,
) -> list[dict[str, Any]]:
    from src.ingestion.indexing.chroma_store import get_vector_store

    if not enriched_chunks and not reference_chunks:
        return []

    all_docs = enriched_chunks + reference_chunks
    vector_store = get_vector_store()
    if force_rebuild:
        vector_store.clear()
    add_stats = vector_store.add_documents(all_docs)

    return [
        {
            "attempted": add_stats.get("attempted", 0),
            "inserted": add_stats.get("inserted", 0),
            "skipped_duplicate_content": add_stats.get("skipped_duplicate_content", 0),
        }
    ]


def write_embedding_stats(
    embed_chunks: list[dict[str, Any]],
    platinum_embeddings_dir: str,
) -> dict[str, Any]:
    import polars as pl

    Path(platinum_embeddings_dir).mkdir(parents=True, exist_ok=True)
    path = Path(platinum_embeddings_dir) / "embedding_stats.parquet"
    if not embed_chunks:
        logger.warning("No embedding stats to write; skipping %s", path)
        return {
            "embedding_count": 0,
            "path": str(path),
        }
    df = pl.DataFrame(embed_chunks)
    df.write_parquet(path)
    return {
        "embedding_count": len(embed_chunks),
        "path": str(path),
    }
