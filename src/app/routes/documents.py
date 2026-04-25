"""Document browsing API endpoints.

Provides a read-only view of the indexed document chunks in ChromaDB
for inspection and debugging from the frontend.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.config.context import get_runtime_state
from src.ingestion.indexing.vector_store import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter()


def _check_store() -> Any:
    if not get_runtime_state().vector_store_initialized:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    try:
        return get_vector_store()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/documents",
    summary="List indexed documents",
    description="Get a paginated summary of all indexed document chunks",
)
def list_documents(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    source_type: str | None = None,
) -> dict[str, Any]:
    store = _check_store()

    try:
        all_docs = store.documents
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    ids = all_docs.get("ids", [])
    contents = all_docs.get("contents", [])
    metadatas = all_docs.get("metadatas", [])

    items: list[dict[str, Any]] = []
    for i, doc_id in enumerate(ids):
        meta = metadatas[i] if i < len(metadatas) else {}
        content = contents[i] if i < len(contents) else ""

        if source_type and meta.get("source_type", meta.get("source_class", "")) != source_type:
            continue

        items.append(
            {
                "id": doc_id,
                "source": meta.get("source", ""),
                "page": meta.get("page"),
                "source_type": meta.get("source_type", ""),
                "source_class": meta.get("source_class", ""),
                "content_type": meta.get("content_type", ""),
                "content_preview": content[:200] if content else "",
                "content_length": len(content),
            }
        )

    total = len(items)
    page = items[offset : offset + limit]

    source_types: dict[str, int] = {}
    for item in items:
        st = item["source_type"] or "unknown"
        source_types[st] = source_types.get(st, 0) + 1

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": page,
        "source_type_counts": source_types,
        "index_metadata": all_docs.get("index_metadata", {}),
    }


@router.get(
    "/documents/{doc_id}",
    summary="Get a single document chunk",
    description="Retrieve full content and metadata for a specific chunk",
)
def get_document(doc_id: str) -> dict[str, Any]:
    store = _check_store()

    try:
        result = store._collection.get(ids=[doc_id], include=["documents", "metadatas"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    ids = result.get("ids", [])
    if not ids:
        raise HTTPException(status_code=404, detail="Document not found")

    idx = 0
    content = result.get("documents", [""])[idx]
    meta = result.get("metadatas", [{}])[idx]

    return {
        "id": ids[idx],
        "content": content,
        "metadata": meta,
        "content_length": len(content),
    }
