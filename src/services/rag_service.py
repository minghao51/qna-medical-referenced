"""RAG service for retrieval orchestration.

This service coordinates query expansion, retrieval, and result formatting
for the RAG pipeline. It replaces the direct imports from runtime.py.
"""

from __future__ import annotations

from typing import Any

from src.services.base_service import BaseService
from src.services.vector_store_service import VectorStoreService


class RAGService(BaseService):
    """Service for RAG retrieval operations.

    This service orchestrates:
    - Query expansion (lexical, medical, HyDE/HyPE)
    - Vector store retrieval
    - Result diversification and reranking
    - Context assembly
    """

    def __init__(self, vector_store_service: VectorStoreService) -> None:
        """Initialize RAG service.

        Args:
            vector_store_service: Injected vector store service
        """
        super().__init__()
        self._vector_store = vector_store_service

    def retrieve_context(
        self,
        query: str,
        top_k: int = 3,
        enable_expansion: bool = True,
        retrieval_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retrieve context for a query using the full RAG pipeline.

        Args:
            query: User's question
            top_k: Number of results to return
            enable_expansion: Whether to enable query expansion
            retrieval_overrides: Optional overrides for retrieval config

        Returns:
            Dictionary with context, sources, and trace metadata
        """
        from src.rag.runtime import (
            _build_retrieved_documents,
            _diversify_results,
            _prepare_expanded_queries,
            _resolve_retrieval_config,
        )

        # Resolve retrieval configuration
        config = _resolve_retrieval_config(retrieval_overrides)

        # Expand query if enabled
        if enable_expansion:
            expanded_queries, medical_trace = _prepare_expanded_queries(
                query,
                enable_medical_expansion=config.enable_medical_expansion,
                medical_expansion_provider=config.medical_expansion_provider,
            )
        else:
            expanded_queries = [query]
            medical_trace = []

        # Retrieve from vector store for each expanded query
        all_results = []
        for expanded_query in expanded_queries:
            results = self._vector_store.search(
                query=expanded_query,
                top_k=top_k * config.overfetch_multiplier,
                hybrid=(config.search_mode == "rrf_hybrid"),
                search_mode=config.search_mode,
            )
            all_results.extend(results)

        # Diversify results
        diversified = _diversify_results(
            all_results,
            top_k=top_k,
            mmr_lambda=config.mmr_lambda,
            overfetch_multiplier=config.overfetch_multiplier,
            max_chunks_per_source_page=config.max_chunks_per_source_page,
            max_chunks_per_source=config.max_chunks_per_source,
            enable_diversification=_should_apply_diversification(config),
        )

        # Build retrieved documents
        retrieved_docs = _build_retrieved_documents(diversified)

        # Build context and sources
        from src.rag.formatting import build_context_and_sources

        context, sources = build_context_and_sources(retrieved_docs)

        return {
            "context": context,
            "sources": sources,
            "retrieved_documents": retrieved_docs,
            "trace": {
                "expanded_queries": expanded_queries,
                "medical_expansions": medical_trace,
                "search_mode": config.search_mode,
                "diversification_enabled": config.enable_diversification,
            },
        }

    @property
    def vector_store(self) -> VectorStoreService:
        """Return the vector store service."""
        return self._vector_store


def _should_apply_diversification(config: Any) -> bool:
    """Check if diversification should be applied based on config."""
    return config.enable_diversification and config.reranking_mode in {"mmr", "both"}
