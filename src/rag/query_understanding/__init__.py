"""Query understanding module for medical Q&A.

Classifies queries by type and routes retrieval accordingly.
"""

from src.rag.query_understanding.classifier import (
    QueryType,
    classify_query,
    get_query_classifier,
)
from src.rag.query_understanding.router import (
    get_retrieval_params_for_query,
    route_retrieval,
)
from src.rag.query_understanding.strategies import (
    get_query_strategy,
)

__all__ = [
    "QueryType",
    "classify_query",
    "get_query_classifier",
    "get_retrieval_params_for_query",
    "route_retrieval",
    "get_query_strategy",
]
