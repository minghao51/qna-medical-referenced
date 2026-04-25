"""Backward-compatibility shim for vector_store.

All code importing from this module gets ChromaVectorStore and
ChromaVectorStoreFactory via chroma_store.py, preserving the original
import paths so no caller code needs to change.
"""

from src.ingestion.indexing.chroma_store import (
    ChromaVectorStore,
    ChromaVectorStoreFactory,
    get_vector_store,
    get_vector_store_runtime_config,
    set_vector_store_runtime_config,
)

VectorStore = ChromaVectorStore
VectorStoreFactory = ChromaVectorStoreFactory

__all__ = [
    "VectorStore",
    "VectorStoreFactory",
    "get_vector_store",
    "get_vector_store_runtime_config",
    "set_vector_store_runtime_config",
]
