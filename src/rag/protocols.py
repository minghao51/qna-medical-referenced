"""Protocols for RAG module dependencies."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VectorStoreProtocol(Protocol):
    """Minimal interface that any vector store must implement.

    Used to type-hint vector_store parameters throughout the RAG pipeline
    without coupling to the concrete ChromaStore implementation.
    """

    @property
    def documents(self) -> dict[str, Any]:
        """Return all stored documents, embeddings, and metadata."""
        ...

    @property
    def last_indexing_stats(self) -> dict[str, Any]:
        """Return stats from the most recent indexing run."""
        ...

    def similarity_search(
        self,
        query: str,
        top_k: int = 5,
        hybrid: bool = True,
        search_mode: str | None = None,
        filter: dict | None = None,
    ) -> list[dict]:
        """Return top-k results for *query*."""
        ...

    def similarity_search_with_trace(
        self,
        query: str,
        top_k: int = 5,
        hybrid: bool = True,
        search_mode: str | None = None,
        filter: dict | None = None,
    ) -> tuple[list[dict], dict]:
        """Return top-k results together with a retrieval-trace dict."""
        ...

    def search_hypothetical_questions(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[str]:
        """Return hypothetical questions matching *query*."""
        ...

    def add_documents(
        self,
        documents: list[dict],
        batch_size: int | None = None,
    ) -> dict:
        """Add documents to the store; return indexing stats."""
        ...

    def clear(self) -> None:
        """Remove all documents from the store."""
        ...
