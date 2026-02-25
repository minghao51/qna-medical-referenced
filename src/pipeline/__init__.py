"""Deprecated compatibility exports for legacy `src.pipeline` imports."""

import warnings

from src.rag import (
    get_context,
    initialize_runtime_index,
    initialize_vector_store,
    retrieve_context,
    retrieve_context_with_trace,
)

warnings.warn(
    "src.pipeline runtime imports are deprecated; use src.rag (runtime) or src.ingestion (offline pipeline).",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "get_context",
    "initialize_runtime_index",
    "initialize_vector_store",
    "retrieve_context",
    "retrieve_context_with_trace",
]
