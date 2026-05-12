"""Backward-compatibility shim — import from chroma_store instead."""

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
    "ChromaVectorStore",
    "ChromaVectorStoreFactory",
    "VectorStore",
    "VectorStoreFactory",
    "get_vector_store",
    "get_vector_store_runtime_config",
    "set_vector_store_runtime_config",
]
