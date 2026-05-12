"""RAG module — public API."""

from src.rag.config import RetrievalDiversityConfig, get_runtime_retrieval_config
from src.rag.diversification import diversify_results
from src.rag.index import (
    configure_runtime_for_experiment,
    get_runtime_status,
    initialize_runtime_index,
    initialize_runtime_index_async,
    initialize_vector_store,
    initialize_vector_store_async,
    reset_runtime_index_state,
)
from src.rag.runtime import (
    get_context,
    get_full_context,
    retrieve_context,
    retrieve_context_with_trace,
    retrieve_context_with_trace_async,
)

__all__ = [
    "RetrievalDiversityConfig",
    "configure_runtime_for_experiment",
    "diversify_results",
    "get_context",
    "get_full_context",
    "get_runtime_retrieval_config",
    "get_runtime_status",
    "initialize_runtime_index",
    "initialize_runtime_index_async",
    "initialize_vector_store",
    "initialize_vector_store_async",
    "reset_runtime_index_state",
    "retrieve_context",
    "retrieve_context_with_trace",
    "retrieve_context_with_trace_async",
]
