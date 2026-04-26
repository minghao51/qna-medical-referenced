"""Document browsing API endpoints.

Provides a read-only view of the indexed document chunks in ChromaDB
for inspection and debugging from the frontend.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from src.config.context import get_runtime_state
from src.ingestion.indexing.vector_store import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter()


def _check_store(request_id: str | None = None) -> Any:
    if not get_runtime_state().vector_store_initialized:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    try:
        return get_vector_store()
    except Exception as exc:
        logger.exception("Vector store unavailable (request_id=%s)", request_id)
        raise HTTPException(status_code=503, detail="Vector store unavailable") from exc


@router.get(
    "/documents",
    summary="List indexed documents",
    description="Get a paginated summary of all indexed document chunks",
)
def list_documents(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    source_type: str | None = None,
) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", None)
    store = _check_store(request_id)

    try:
        paged = store.list_documents_paginated(
            limit=limit,
            offset=offset,
            source_type=source_type,
        )
    except Exception as exc:
        logger.exception("Failed to list documents (request_id=%s)", request_id)
        raise HTTPException(status_code=500, detail="Failed to load documents") from exc

    return {
        "total": paged["total"],
        "offset": offset,
        "limit": limit,
        "items": paged["items"],
        "source_type_counts": paged["source_type_counts"],
        "index_metadata": paged["index_metadata"],
    }


@router.get(
    "/documents/{doc_id}",
    summary="Get a single document chunk",
    description="Retrieve full content and metadata for a specific chunk",
)
def get_document(doc_id: str, request: Request) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", None)
    store = _check_store(request_id)

    try:
        result = store.get_document_by_id(doc_id)
    except Exception as exc:
        logger.exception("Failed to fetch document (request_id=%s doc_id=%s)", request_id, doc_id)
        raise HTTPException(status_code=500, detail="Failed to load document") from exc

    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    return result
