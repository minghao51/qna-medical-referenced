"""Vector store service for data access abstraction.

This service wraps the ChromaVectorStore and provides a clean interface
for business logic to interact with vector storage without knowing
implementation details.
"""

from __future__ import annotations

from typing import Any

from src.ingestion.indexing.vector_store import get_vector_store
from src.services.base_service import BaseService


class VectorStoreService(BaseService):
    """Service for vector store operations.

    This service abstracts ChromaDB operations and provides:
    - Document storage and retrieval
    - Hybrid search (semantic + keyword)
    - Index management and initialization
    """

    def search(
        self,
        query: str,
        top_k: int = 5,
        hybrid: bool = True,
        search_mode: str | None = None,
        filter: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Search the vector store for relevant documents.

        Args:
            query: The search query
            top_k: Number of results to return
            hybrid: Whether to use hybrid search (semantic + keyword)
            search_mode: Search mode override (rrf_hybrid, semantic_only, bm25_only)
            filter: Metadata filter for query

        Returns:
            List of matching documents with scores and metadata
        """
        vector_store = get_vector_store()
        return vector_store.similarity_search(
            query=query,
            top_k=top_k,
            hybrid=hybrid,
            search_mode=search_mode,
            filter=filter,
        )

    def get_document_count(self) -> int:
        """Return the number of documents in the vector store."""
        vector_store = get_vector_store()
        return vector_store._collection.count()

    def is_index_initialized(self) -> bool:
        """Check if the vector store index is initialized."""
        from src.config.context import get_runtime_state

        state = get_runtime_state()
        status = state.get_vector_store_status()
        return status["initialized"]

    def clear_index(self) -> None:
        """Clear the vector store index."""
        vector_store = get_vector_store()
        vector_store.clear()

        from src.config.context import get_runtime_state
        get_runtime_state().reset_vector_store_state()

        self.logger.info("Vector store index cleared")
