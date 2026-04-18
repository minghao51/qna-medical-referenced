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
from typing import Any

from src.config import settings
from src.config.context import RuntimeState, get_runtime_state, reset_runtime_state

logger = logging.getLogger(__name__)


@dataclass
class ServiceContainer:
    """Container for application services.

    This container manages service instances using lazy initialization.
    Services are created only when first requested and cached for reuse.

    Attributes:
        vector_store: Cached vector store instance
        llm_client: Cached LLM client instance
        html_processor_config: HTML processing configuration
        retrieval_config: Retrieval configuration
    """

    vector_store: Any = None
    llm_client: Any = None
    html_processor_config: dict[str, Any] = field(default_factory=dict)
    retrieval_config: dict[str, Any] = field(default_factory=dict)
    vector_store_config: dict[str, Any] = field(default_factory=dict)
    runtime_state: RuntimeState = field(default_factory=get_runtime_state)

    def get_vector_store(self, config: dict[str, Any] | None = None) -> Any:
        """Get or create vector store instance.

        Args:
            config: Optional configuration override

        Returns:
            VectorStore instance
        """
        if self.vector_store is None or (config and config != self.vector_store_config):
            from src.ingestion.indexing.vector_store import VectorStoreFactory

            effective_config = config or self.vector_store_config
            self.vector_store = VectorStoreFactory.get_vector_store(effective_config)
            if config:
                self.vector_store_config = dict(config)
        return self.vector_store

    def get_llm_client(self) -> Any:
        """Get or create LLM client instance.

        Returns:
            LLM client instance
        """
        if self.llm_client is None:
            from src.infra.llm import get_client

            self.llm_client = get_client()
        return self.llm_client

    def get_html_processor_config(self) -> dict[str, Any]:
        """Get HTML processor configuration.

        Returns:
            HTML processor configuration dict
        """
        if not self.html_processor_config:
            self.html_processor_config = {
                "extractor_strategy": "trafilatura_bs",
                "chain_depth": None,
                "page_classification_enabled": True,
                "extractor_mode": "auto",
            }
        return self.html_processor_config

    def get_retrieval_config(self) -> dict[str, Any]:
        """Get retrieval configuration from settings.

        Returns:
            Retrieval configuration dict
        """
        if not self.retrieval_config:
            self.retrieval_config = {
                "overfetch_multiplier": settings.retrieval_overfetch_multiplier,
                "max_chunks_per_source_page": settings.max_chunks_per_source_page,
                "max_chunks_per_source": settings.max_chunks_per_source,
                "mmr_lambda": settings.mmr_lambda,
                "search_mode": settings.rrf_search_mode,
            }
        return self.retrieval_config

    def reset(self):
        """Reset all cached services.

        This is primarily useful for testing to ensure clean state
        between test cases.
        """
        self.vector_store = None
        self.llm_client = None
        self.html_processor_config = {}
        self.retrieval_config = {}
        self.vector_store_config = {}
        # Also reset the VectorStoreFactory
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


# Convenience accessor
container = get_container
