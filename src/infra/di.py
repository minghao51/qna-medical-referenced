"""Dependency injection container for application services.

This module provides a simple dependency injection container that manages
service instances and their lifecycle. It replaces global singletons with
explicit dependency injection, improving testability and maintainability.

.. deprecated:: Phase 3
    This container is scheduled for deletion (replaced by real constructor
    injection from composition roots — see
    docs/plans/20260910-structural-refactor-roadmap.md §P3.1).
    **Do not extend.** Protocol types are imported from their canonical homes:
    `infra/llm/interfaces.py`, `infra/storage/interfaces.py`, `rag/protocols.py`.

Example:
    Get services from container:
        from src.infra.di import container
        vector_store = container.get_vector_store()
        llm_client = container.get_llm_client()

    Reset for testing:
        from src.infra.di import reset_container
        reset_container()
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from src.config import settings
from src.config.context import RuntimeState, get_runtime_state, reset_runtime_state
from src.infra.llm.interfaces import LLMClient
from src.infra.storage.interfaces import ChatHistoryStore

if TYPE_CHECKING:
    # Typing-only: the canonical vector-store interface lives in rag/ (the
    # layer that consumes it). No runtime import — infra must not depend on rag.
    from src.rag.protocols import VectorStoreProtocol

logger = logging.getLogger(__name__)


@dataclass
class ServiceContainer:
    vector_store: "VectorStoreProtocol | None" = None
    llm_client: LLMClient | None = None
    chat_history_store: ChatHistoryStore | None = None
    html_processor_config: dict[str, Any] = field(default_factory=dict)
    retrieval_config: dict[str, Any] = field(default_factory=dict)
    vector_store_config: dict[str, Any] = field(default_factory=dict)
    runtime_state: RuntimeState = field(default_factory=get_runtime_state)

    def get_vector_store(self, config: dict[str, Any] | None = None) -> "VectorStoreProtocol":
        if self.vector_store is None or (config and config != self.vector_store_config):
            from src.ingestion.indexing.chroma_store import ChromaVectorStoreFactory

            effective_config = config or self.vector_store_config
            self.vector_store = cast(
                "VectorStoreProtocol", ChromaVectorStoreFactory.get_vector_store(effective_config)
            )
            if config:
                self.vector_store_config = dict(config)
        if self.vector_store is None:
            raise RuntimeError("Vector store failed to initialize")
        return self.vector_store

    def get_llm_client(self) -> LLMClient:
        if self.llm_client is None:
            from src.infra.llm import get_client

            self.llm_client = get_client()
        return self.llm_client

    def get_chat_history_store(self) -> ChatHistoryStore:
        if self.chat_history_store is None:
            from src.infra.storage.file_chat_history_store import FileChatHistoryStore

            self.chat_history_store = FileChatHistoryStore()
        return self.chat_history_store

    def get_html_processor_config(self) -> dict[str, Any]:
        if not self.html_processor_config:
            self.html_processor_config = {
                "extractor_strategy": settings.ingestion.html_extractor_strategy,
                "chain_depth": None,
                "page_classification_enabled": settings.ingestion.page_classification_enabled,
                "extractor_mode": settings.ingestion.html_extractor_mode,
            }
        return self.html_processor_config

    def get_retrieval_config(self) -> dict[str, Any]:
        if not self.retrieval_config:
            self.retrieval_config = {
                "overfetch_multiplier": settings.retrieval.retrieval_overfetch_multiplier,
                "max_chunks_per_source_page": settings.retrieval.max_chunks_per_source_page,
                "max_chunks_per_source": settings.retrieval.max_chunks_per_source,
                "mmr_lambda": settings.retrieval.mmr_lambda,
                "search_mode": settings.retrieval.rrf_search_mode,
            }
        return self.retrieval_config

    def reset(self):
        self.vector_store = None
        self.llm_client = None
        self.chat_history_store = None
        self.html_processor_config = {}
        self.retrieval_config = {}
        self.vector_store_config = {}
        from src.ingestion.indexing.chroma_store import ChromaVectorStoreFactory

        ChromaVectorStoreFactory.reset()
        reset_runtime_state()
        self.runtime_state = get_runtime_state()


# Global container instance
_container: ServiceContainer | None = None
_container_lock = threading.Lock()


def get_container() -> ServiceContainer:
    """Get the global service container instance.

    Returns:
        ServiceContainer instance
    """
    global _container
    with _container_lock:
        if _container is None:
            _container = ServiceContainer()
        return _container


def reset_container():
    """Reset the global service container.

    This is primarily useful for testing to ensure clean state
    between test cases.
    """
    global _container
    with _container_lock:
        if _container:
            _container.reset()
        _container = None


# Convenience accessor (lazy — calls get_container() on first attribute access)
class _ContainerProxy:
    def __getattr__(self, name):
        return getattr(get_container(), name)

    def __repr__(self):
        return repr(get_container())


container = _ContainerProxy()
