"""Compatibility exports for legacy pipeline runtime imports."""

from src.rag import (
    get_context,
    initialize_runtime_index,
    retrieve_context,
    retrieve_context_with_trace,
)

__all__ = [
    "get_context",
    "initialize_runtime_index",
    "retrieve_context",
    "retrieve_context_with_trace",
]
