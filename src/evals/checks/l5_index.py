"""L5 index quality checks."""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any

from src.config import VECTOR_DIR, settings
from src.ingestion.indexing.chroma_store import ChromaVectorStore, get_vector_store

logger = logging.getLogger(__name__)


def _open_store_for_collection(collection_name: str) -> ChromaVectorStore | None:
    """Open the Chroma-backed vector store for ``collection_name``.

    Prefers the shared runtime store (so the check observes exactly what the
    pipeline indexed) and falls back to a direct store when the runtime store is
    bound to a different collection. Never mutates the shared runtime config.
    """
    try:
        store = get_vector_store()
        if store.collection_name == collection_name:
            return store
        return ChromaVectorStore(collection_name=collection_name)
    except Exception as e:
        logger.warning("Failed to open vector store collection %r: %s", collection_name, e)
        return None


def _index_size_bytes(path: Path) -> int | None:
    """Total size of the on-disk index, tolerating missing/server-mode paths."""
    try:
        if not path.exists():
            return None
        if path.is_file():
            return path.stat().st_size
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    except OSError as e:
        logger.debug("Failed to compute index size for %s: %s", path, e)
        return None


def assess_l5_index_quality(
    vector_dir: Path | None = None,
    collection_name: str | None = None,
) -> dict[str, Any]:
    vdir = Path(vector_dir or VECTOR_DIR)
    coll = collection_name or settings.storage.collection_name

    data: dict[str, Any] = {}
    content_hashes: list[str] = []
    store = _open_store_for_collection(coll)
    if store is not None:
        try:
            data = store.documents
            content_hashes = sorted(store.content_hashes)
            # A freshly opened store starts with empty index metadata; recover it
            # from the Chroma collection metadata when available.
            if not data.get("index_metadata"):
                collection_meta = getattr(store._collection, "metadata", None)
                data["index_metadata"] = dict(collection_meta or {})
        except Exception as e:
            logger.warning("Failed to read vector store collection %r: %s", coll, e)
            data = {}
            content_hashes = []

    ids = list(data.get("ids", []))
    if not ids:
        return {
            "aggregate": {"index_exists": False, "vector_path": str(vdir)},
            "records": [],
            "findings": [
                {
                    "severity": "warning",
                    "message": f"Vector index collection {coll!r} is missing or empty",
                    "stage": "L5",
                }
            ],
        }

    contents = list(data.get("contents", []))
    embeddings = list(data.get("embeddings", []))
    metadatas = list(data.get("metadatas", []))
    lengths = [len(e) for e in embeddings if isinstance(e, list)]
    source_counter = Counter((m or {}).get("source", "unknown") for m in metadatas)
    source_type_counter = Counter((m or {}).get("source_type", "unknown") for m in metadatas)
    source_class_counter = Counter((m or {}).get("source_class", "unknown") for m in metadatas)
    records = [
        {
            "id": ids[i] if i < len(ids) else None,
            "source": (metadatas[i] or {}).get("source", "unknown")
            if i < len(metadatas)
            else "unknown",
            "content_chars": len(contents[i])
            if i < len(contents) and isinstance(contents[i], str)
            else 0,
            "embedding_dim": len(embeddings[i])
            if i < len(embeddings) and isinstance(embeddings[i], list)
            else 0,
        }
        for i in range(min(len(ids), len(contents), len(embeddings), len(metadatas)))
    ]
    findings = []
    lengths_equal = len(ids) == len(contents) == len(embeddings) == len(metadatas)
    if not lengths_equal:
        findings.append(
            {"severity": "error", "message": "Vector arrays have mismatched lengths", "stage": "L5"}
        )
    unique_dims = sorted(set(lengths))
    index_metadata = data.get("index_metadata", {}) or {}
    if len(unique_dims) > 1:
        findings.append(
            {"severity": "error", "message": "Embedding dimensions are inconsistent", "stage": "L5"}
        )
    missing_embeddings = sum(1 for e in embeddings if not isinstance(e, list) or not e)
    if missing_embeddings:
        findings.append(
            {
                "severity": "warning",
                "message": f"{missing_embeddings} indexed documents have no embedding",
                "stage": "L5",
            }
        )

    aggregate = {
        "index_exists": True,
        "vector_path": str(vdir),
        "ids_count": len(ids),
        "contents_count": len(contents),
        "embeddings_count": len(embeddings),
        "metadatas_count": len(metadatas),
        "content_hashes_count": len(content_hashes),
        "lengths_consistent": lengths_equal,
        "embedding_dim_consistent": len(unique_dims) <= 1,
        "embedding_dim": unique_dims[0] if len(unique_dims) == 1 else None,
        "embedding_model": index_metadata.get("embedding_model"),
        "embedding_batch_size": index_metadata.get("embedding_batch_size"),
        "index_config_hash": index_metadata.get("index_config_hash"),
        "short_content_rate": (
            sum(1 for c in contents if isinstance(c, str) and len(c.strip()) < 20) / len(contents)
        )
        if contents
        else 0.0,
        "source_distribution": dict(source_counter),
        "source_type_distribution": dict(source_type_counter),
        "source_class_distribution": dict(source_class_counter),
        "dedupe_effect_estimate": max(0, len(content_hashes) - len(contents)),
        "index_file_size_bytes": _index_size_bytes(vdir),
    }
    return {"aggregate": aggregate, "records": records, "findings": findings}
