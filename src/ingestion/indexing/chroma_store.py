"""Backward-compatible re-export of the vector-store public surface.

Canonical modules (Phase 2, roadmap P2.3):
- store.py    — ChromaVectorStore core (client, CRUD, mirrors, BM25, search)
- hype_index.py  — HyPE hypothetical-question search mixin
- listing.py  — paginated document listing mixin
- factory.py  — ChromaVectorStoreFactory + module-level accessors
"""

from src.ingestion.indexing.factory import (
    ChromaVectorStoreFactory,
    get_vector_store,
    get_vector_store_runtime_config,
    set_vector_store_runtime_config,
)
from src.ingestion.indexing.store import ChromaVectorStore

__all__ = [
    "ChromaVectorStore",
    "ChromaVectorStoreFactory",
    "get_vector_store",
    "get_vector_store_runtime_config",
    "set_vector_store_runtime_config",
]
