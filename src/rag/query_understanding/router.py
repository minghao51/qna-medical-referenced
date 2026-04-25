"""Retrieval routing based on query classification.

Maps query types to retrieval parameters for optimized retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from src.rag.query_understanding.classifier import QueryClassification, QueryType


@dataclass
class RetrievalParams:
    """Retrieval parameters for a query type."""

    overfetch_multiplier: int = 4
    max_chunks_per_source_page: int = 2
    max_chunks_per_source: int = 3
    mmr_lambda: float = 0.75
    enable_diversification: bool = True
    search_mode: str = "rrf_hybrid"
    similarity_threshold: float | None = None  # Minimum similarity score
    min_chunks: int = 3  # Minimum chunks to return
    enable_multi_source: bool = False  # Aggregate across multiple sources


@dataclass
class RetrievalRoute:
    """Retrieval route for a classified query."""

    params: RetrievalParams
    reasoning: str
    suggested_post_processing: list[str] = field(default_factory=list)


class RetrievalRouter:
    """Routes retrieval based on query classification."""

    # Default retrieval parameters
    DEFAULT_PARAMS = RetrievalParams()

    # Query type specific parameters
    TYPE_PARAMS: ClassVar[dict[QueryType, RetrievalParams]] = {
        # Definition: High similarity threshold, top-3 only
        QueryType.DEFINITION: RetrievalParams(
            overfetch_multiplier=2,
            max_chunks_per_source_page=2,
            max_chunks_per_source=2,
            mmr_lambda=0.8,
            enable_diversification=True,
            search_mode="rrf_hybrid",
            similarity_threshold=0.6,
            min_chunks=3,
        ),
        # Comparison: Multi-source, explicit contrast
        QueryType.COMPARISON: RetrievalParams(
            overfetch_multiplier=5,
            max_chunks_per_source_page=3,
            max_chunks_per_source=4,
            mmr_lambda=0.6,  # Lower lambda = more diversity
            enable_diversification=True,
            search_mode="rrf_hybrid",
            similarity_threshold=None,
            min_chunks=5,
            enable_multi_source=True,
        ),
        # Reference range: Table-weighted retrieval
        QueryType.REFERENCE_RANGE: RetrievalParams(
            overfetch_multiplier=3,
            max_chunks_per_source_page=3,
            max_chunks_per_source=3,
            mmr_lambda=0.75,
            enable_diversification=True,
            search_mode="rrf_hybrid",
            similarity_threshold=0.5,
            min_chunks=3,
        ),
        # Symptom query: Similar to definition but more sources
        QueryType.SYMPTOM_QUERY: RetrievalParams(
            overfetch_multiplier=3,
            max_chunks_per_source_page=2,
            max_chunks_per_source=3,
            mmr_lambda=0.75,
            enable_diversification=True,
            search_mode="rrf_hybrid",
            similarity_threshold=0.55,
            min_chunks=4,
        ),
        # Treatment: Need comprehensive info
        QueryType.TREATMENT: RetrievalParams(
            overfetch_multiplier=4,
            max_chunks_per_source_page=3,
            max_chunks_per_source=4,
            mmr_lambda=0.7,
            enable_diversification=True,
            search_mode="rrf_hybrid",
            similarity_threshold=None,
            min_chunks=5,
        ),
        # Risk factor: Similar to treatment
        QueryType.RISK_FACTOR: RetrievalParams(
            overfetch_multiplier=4,
            max_chunks_per_source_page=3,
            max_chunks_per_source=4,
            mmr_lambda=0.7,
            enable_diversification=True,
            search_mode="rrf_hybrid",
            similarity_threshold=None,
            min_chunks=4,
        ),
        # Follow-up: Context-dependent, moderate params
        QueryType.FOLLOW_UP: RetrievalParams(
            overfetch_multiplier=3,
            max_chunks_per_source_page=2,
            max_chunks_per_source=3,
            mmr_lambda=0.75,
            enable_diversification=True,
            search_mode="rrf_hybrid",
            similarity_threshold=None,
            min_chunks=3,
        ),
        # Complex: Multi-query decomposition, high overfetch
        QueryType.COMPLEX: RetrievalParams(
            overfetch_multiplier=6,
            max_chunks_per_source_page=3,
            max_chunks_per_source=5,
            mmr_lambda=0.6,  # More diversity for complex queries
            enable_diversification=True,
            search_mode="rrf_hybrid",
            similarity_threshold=None,
            min_chunks=5,
            enable_multi_source=True,
        ),
    }

    def __init__(self, custom_params: dict[QueryType, RetrievalParams] | None = None):
        """Initialize retrieval router.

        Args:
            custom_params: Optional custom parameters for query types
        """
        self.type_params = dict(self.TYPE_PARAMS)
        if custom_params:
            self.type_params.update(custom_params)

    def route(self, classification: QueryClassification) -> RetrievalRoute:
        """Route retrieval based on query classification.

        Args:
            classification: Query classification result

        Returns:
            RetrievalRoute with parameters and reasoning
        """
        params = self.type_params.get(classification.query_type, self.DEFAULT_PARAMS)
        reasoning = f"Query type: {classification.query_type.value}. {classification.reasoning}"

        # Suggested post-processing based on query type
        post_processing = []
        if classification.query_type == QueryType.COMPARISON:
            post_processing.append("explicit_contrast")
        elif classification.query_type == QueryType.REFERENCE_RANGE:
            post_processing.append("prioritize_tables")
        elif classification.query_type == QueryType.COMPLEX:
            post_processing.append("multi_query_decomposition")

        return RetrievalRoute(
            params=params,
            reasoning=reasoning,
            suggested_post_processing=post_processing,
        )

    def get_retrieval_options(self, classification: QueryClassification) -> dict[str, Any]:
        """Get retrieval options dict for runtime.py.

        Args:
            classification: Query classification result

        Returns:
            Dict of retrieval options compatible with retrieve_context
        """
        route = self.route(classification)
        params = route.params

        return {
            "overfetch_multiplier": params.overfetch_multiplier,
            "max_chunks_per_source_page": params.max_chunks_per_source_page,
            "max_chunks_per_source": params.max_chunks_per_source,
            "mmr_lambda": params.mmr_lambda,
            "enable_diversification": params.enable_diversification,
            "search_mode": params.search_mode,
        }


def get_retrieval_router(
    custom_params: dict[QueryType, RetrievalParams] | None = None,
) -> RetrievalRouter:
    """Factory function for retrieval router.

    Args:
        custom_params: Optional custom parameters for query types

    Returns:
        Configured RetrievalRouter instance
    """
    return RetrievalRouter(custom_params=custom_params)


def get_retrieval_params_for_query(
    query: str,
    classification: QueryClassification | None = None,
) -> dict[str, Any]:
    """Get retrieval parameters for a query.

    Args:
        query: The query text
        classification: Optional pre-computed classification

    Returns:
        Dict of retrieval options compatible with retrieve_context
    """
    if classification is None:
        from src.rag.query_understanding.classifier import classify_query

        classification = classify_query(query)

    router = get_retrieval_router()
    return router.get_retrieval_options(classification)


def route_retrieval(
    query: str,
    classification: QueryClassification | None = None,
) -> RetrievalRoute:
    """Route retrieval for a query.

    Args:
        query: The query text
        classification: Optional pre-computed classification

    Returns:
        RetrievalRoute with parameters and reasoning
    """
    if classification is None:
        from src.rag.query_understanding.classifier import classify_query

        classification = classify_query(query)

    router = get_retrieval_router()
    return router.route(classification)
