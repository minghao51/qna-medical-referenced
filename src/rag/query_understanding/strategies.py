"""Query type-specific retrieval strategies.

Implements type-specific logic for different query categories.
"""

from __future__ import annotations

import logging

from src.rag.query_understanding.classifier import QueryType

logger = logging.getLogger(__name__)


class QueryStrategy:
    """Base class for query type-specific strategies."""

    def __init__(self, query_type: QueryType):
        """Initialize strategy for a query type.

        Args:
            query_type: The query type this strategy handles
        """
        self.query_type = query_type

    def preprocess_query(self, query: str) -> str:
        """Preprocess query for this type.

        Args:
            query: Original query

        Returns:
            Preprocessed query string
        """
        return query

    def post_process_results(self, results: list[dict], query: str) -> list[dict]:
        """Post-process retrieval results for this query type.

        Args:
            results: Retrieved documents
            query: Original query

        Returns:
            Post-processed results
        """
        return results

    def should_rerank(self, results: list[dict], query: str) -> bool:
        """Check if results should be reranked for this query type.

        Args:
            results: Retrieved documents
            query: Original query

        Returns:
            True if reranking is recommended
        """
        return True


class DefinitionStrategy(QueryStrategy):
    """Strategy for definition queries."""

    def __init__(self):
        super().__init__(QueryType.DEFINITION)

    def preprocess_query(self, query: str) -> str:
        """Clean definition queries."""
        # Remove common definition prefixes for cleaner search
        cleaned = query
        for prefix in ["what is ", "define ", "explain ", "meaning of "]:
            if cleaned.lower().startswith(prefix):
                cleaned = cleaned[len(prefix) :]
        return cleaned.strip()


class ComparisonStrategy(QueryStrategy):
    """Strategy for comparison queries."""

    def __init__(self):
        super().__init__(QueryType.COMPARISON)

    def preprocess_query(self, query: str) -> str:
        """Extract comparison terms."""
        # For comparison, we might want to search for each term separately
        # This is a simple version - could be enhanced
        return query

    def post_process_results(self, results: list[dict], query: str) -> list[dict]:
        """Ensure results cover both comparison topics."""
        # Basic implementation - could enhance to check coverage
        return results


class ReferenceRangeStrategy(QueryStrategy):
    """Strategy for reference range queries."""

    def __init__(self):
        super().__init__(QueryType.REFERENCE_RANGE)

    def post_process_results(self, results: list[dict], query: str) -> list[dict]:
        """Prioritize table results for reference ranges."""
        # Boost results with table content
        for result in results:
            content_type = result.get("content_type", "")
            if content_type == "table":
                # Boost table results for reference range queries
                result.setdefault("boost", 0)
                result["boost"] += 0.2
        return results


class ComplexQueryStrategy(QueryStrategy):
    """Strategy for complex/multi-part queries."""

    def __init__(self):
        super().__init__(QueryType.COMPLEX)

    def preprocess_query(self, query: str) -> str:
        """Decompose complex queries into sub-queries."""
        # Simple decomposition - split by common conjunctions
        # A more sophisticated version would use LLM
        return query


# Strategy factory
_STRATEGIES: dict[QueryType, QueryStrategy] = {
    QueryType.DEFINITION: DefinitionStrategy(),
    QueryType.COMPARISON: ComparisonStrategy(),
    QueryType.REFERENCE_RANGE: ReferenceRangeStrategy(),
    QueryType.SYMPTOM_QUERY: QueryStrategy(QueryType.SYMPTOM_QUERY),
    QueryType.TREATMENT: QueryStrategy(QueryType.TREATMENT),
    QueryType.RISK_FACTOR: QueryStrategy(QueryType.RISK_FACTOR),
    QueryType.FOLLOW_UP: QueryStrategy(QueryType.FOLLOW_UP),
    QueryType.COMPLEX: ComplexQueryStrategy(),
}


def get_query_strategy(query_type: QueryType) -> QueryStrategy:
    """Get strategy for a query type.

    Args:
        query_type: The query type

    Returns:
        QueryStrategy instance for the type
    """
    return _STRATEGIES.get(query_type, QueryStrategy(query_type))
