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
    all_chunks: list[dict[str, Any]],
    reference_chunks: list[dict[str, Any]],
    embedding_config: dict[str, Any],
) -> list[dict[str, Any]]:
    from src.services.vector_store_service import get_vector_store

    if not all_chunks and not reference_chunks:
        return []

    all_docs = all_chunks + reference_chunks
    vector_store = get_vector_store()
    add_stats = vector_store.add_documents(all_docs)

    return [
        {
            "attempted": add_stats.get("attempted", 0),
            "inserted": add_stats.get("inserted", 0),
            "skipped_duplicate_id": add_stats.get("skipped_duplicate_id", 0),
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
    df = pl.DataFrame(embed_chunks)
    df.write_parquet(path)
    return {
        "embedding_count": len(embed_chunks),
        "path": str(path),
    }
