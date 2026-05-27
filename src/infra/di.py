"""Dependency injection container for application services.

This module provides a simple dependency injection container that manages
service instances and their lifecycle. It replaces global singletons with
explicit dependency injection, improving testability and maintainability.

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
from typing import Any, Protocol, cast, runtime_checkable

from src.config import settings
from src.config.context import RuntimeState, get_runtime_state, reset_runtime_state

logger = logging.getLogger(__name__)


@runtime_checkable
class VectorStoreProtocol(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]: ...


@runtime_checkable
class LLMClientProtocol(Protocol):
    def generate(self, prompt: str, context: str = "") -> str: ...

    async def a_generate(self, prompt: str, context: str = "") -> str: ...

    def generate_structured(self, prompt: str, response_model: type, context: str = "") -> Any: ...

    async def a_generate_structured(
        self, prompt: str, response_model: type, context: str = ""
    ) -> Any: ...


@runtime_checkable
class ChatHistoryStoreProtocol(Protocol):
    def get_history(self, session_id: str) -> list[dict]: ...

    def save_message(self, session_id: str, role: str, content: str) -> None: ...

    def clear_history(self, session_id: str) -> None: ...


@dataclass
class ServiceContainer:
    vector_store: VectorStoreProtocol | None = None
    llm_client: LLMClientProtocol | None = None
    chat_history_store: ChatHistoryStoreProtocol | None = None
    html_processor_config: dict[str, Any] = field(default_factory=dict)
    retrieval_config: dict[str, Any] = field(default_factory=dict)
    vector_store_config: dict[str, Any] = field(default_factory=dict)
    runtime_state: RuntimeState = field(default_factory=get_runtime_state)

    def get_vector_store(self, config: dict[str, Any] | None = None) -> VectorStoreProtocol:
        if self.vector_store is None or (config and config != self.vector_store_config):
            from src.ingestion.indexing.vector_store import VectorStoreFactory

            effective_config = config or self.vector_store_config
            self.vector_store = cast(
                VectorStoreProtocol, VectorStoreFactory.get_vector_store(effective_config)
            )
            if config:
                self.vector_store_config = dict(config)
        if self.vector_store is None:
            raise RuntimeError("Vector store failed to initialize")
        return self.vector_store

    def get_llm_client(self) -> LLMClientProtocol:
        if self.llm_client is None:
            from src.infra.llm import get_client

            self.llm_client = get_client()
        return self.llm_client

    def get_chat_history_store(self) -> ChatHistoryStoreProtocol:
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
        from src.ingestion.indexing.vector_store import VectorStoreFactory

        VectorStoreFactory.reset()
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
