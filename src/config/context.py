"""Centralized runtime configuration context."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeState:
    """Mutable runtime state, protected by a lock where coordination matters.

    All field access goes through thread-safe property getters/setters.
    Direct field access (with underscore prefix) is storage only.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # Internal storage (use properties for access)
    _structured_chunking_enabled: bool = True
    _source_chunk_configs_override: dict | None = None
    _auto_select_strategy: bool = False
    _pdf_extractor_strategy: str = "pypdf_pdfplumber"
    _pdf_table_extractor: str = "heuristic"
    _index_only_classified_pages: bool = True
    _html_extractor_strategy: str = "trafilatura_bs"
    _html_extractor_mode: str = "auto"
    _page_classification_enabled: bool = True
    _reranker_instance: Any = None
    _vector_store_initialized: bool = False
    _vector_store_initialized_signature: str | None = None

    # Properties for thread-safe access

    @property
    def structured_chunking_enabled(self) -> bool:
        with self._lock:
            return self._structured_chunking_enabled

    @structured_chunking_enabled.setter
    def structured_chunking_enabled(self, value: bool) -> None:
        with self._lock:
            self._structured_chunking_enabled = value

    @property
    def source_chunk_configs_override(self) -> dict | None:
        with self._lock:
            return self._source_chunk_configs_override

    @source_chunk_configs_override.setter
    def source_chunk_configs_override(self, value: dict | None) -> None:
        with self._lock:
            self._source_chunk_configs_override = value

    @property
    def auto_select_strategy(self) -> bool:
        with self._lock:
            return self._auto_select_strategy

    @auto_select_strategy.setter
    def auto_select_strategy(self, value: bool) -> None:
        with self._lock:
            self._auto_select_strategy = value

    @property
    def pdf_extractor_strategy(self) -> str:
        with self._lock:
            return self._pdf_extractor_strategy

    @pdf_extractor_strategy.setter
    def pdf_extractor_strategy(self, value: str) -> None:
        with self._lock:
            self._pdf_extractor_strategy = value

    @property
    def pdf_table_extractor(self) -> str:
        with self._lock:
            return self._pdf_table_extractor

    @pdf_table_extractor.setter
    def pdf_table_extractor(self, value: str) -> None:
        with self._lock:
            self._pdf_table_extractor = value

    @property
    def index_only_classified_pages(self) -> bool:
        with self._lock:
            return self._index_only_classified_pages

    @index_only_classified_pages.setter
    def index_only_classified_pages(self, value: bool) -> None:
        with self._lock:
            self._index_only_classified_pages = value

    @property
    def html_extractor_strategy(self) -> str:
        with self._lock:
            return self._html_extractor_strategy

    @html_extractor_strategy.setter
    def html_extractor_strategy(self, value: str) -> None:
        with self._lock:
            self._html_extractor_strategy = value

    @property
    def html_extractor_mode(self) -> str:
        with self._lock:
            return self._html_extractor_mode

    @html_extractor_mode.setter
    def html_extractor_mode(self, value: str) -> None:
        with self._lock:
            self._html_extractor_mode = value

    @property
    def page_classification_enabled(self) -> bool:
        with self._lock:
            return self._page_classification_enabled

    @page_classification_enabled.setter
    def page_classification_enabled(self, value: bool) -> None:
        with self._lock:
            self._page_classification_enabled = value

    @property
    def reranker_instance(self) -> Any:
        with self._lock:
            return self._reranker_instance

    @reranker_instance.setter
    def reranker_instance(self, value: Any) -> None:
        with self._lock:
            self._reranker_instance = value

    @property
    def vector_store_initialized(self) -> bool:
        with self._lock:
            return self._vector_store_initialized

    @vector_store_initialized.setter
    def vector_store_initialized(self, value: bool) -> None:
        with self._lock:
            self._vector_store_initialized = value

    @property
    def vector_store_initialized_signature(self) -> str | None:
        with self._lock:
            return self._vector_store_initialized_signature

    @vector_store_initialized_signature.setter
    def vector_store_initialized_signature(self, value: str | None) -> None:
        with self._lock:
            self._vector_store_initialized_signature = value

    def reset(self) -> None:
        """Reset mutable runtime state to defaults while preserving the same lock."""
        with self._lock:
            lock = self._lock
            self.__dict__.clear()
            self._lock = lock
            self._structured_chunking_enabled = True
            self._source_chunk_configs_override = None
            self._auto_select_strategy = False
            self._pdf_extractor_strategy = "pypdf_pdfplumber"
            self._pdf_table_extractor = "heuristic"
            self._index_only_classified_pages = True
            self._html_extractor_strategy = "trafilatura_bs"
            self._html_extractor_mode = "auto"
            self._page_classification_enabled = True
            self._reranker_instance = None
            self._vector_store_initialized = False
            self._vector_store_initialized_signature = None

    def reset_vector_store_state(self) -> None:
        """Atomically reset vector store state (thread-safe compound operation)."""
        with self._lock:
            self._vector_store_initialized = False
            self._vector_store_initialized_signature = None

    def set_vector_store_initialized(self, signature: str | None) -> None:
        """Atomically set vector store as initialized with signature (thread-safe compound operation)."""
        with self._lock:
            self._vector_store_initialized = True
            self._vector_store_initialized_signature = signature

    def get_vector_store_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "initialized": self._vector_store_initialized,
                "signature": self._vector_store_initialized_signature,
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "structured_chunking_enabled": self._structured_chunking_enabled,
                "source_chunk_configs_override": self._source_chunk_configs_override,
                "auto_select_strategy": self._auto_select_strategy,
                "pdf_extractor_strategy": self._pdf_extractor_strategy,
                "pdf_table_extractor": self._pdf_table_extractor,
                "index_only_classified_pages": self._index_only_classified_pages,
                "html_extractor_strategy": self._html_extractor_strategy,
                "html_extractor_mode": self._html_extractor_mode,
                "page_classification_enabled": self._page_classification_enabled,
                "reranker_instance_loaded": self._reranker_instance is not None,
                "vector_store_initialized": self._vector_store_initialized,
                "vector_store_initialized_signature": self._vector_store_initialized_signature,
            }


# Module-level singleton — one per process
_state = RuntimeState()


def get_runtime_state() -> RuntimeState:
    """Return the global runtime state."""
    return _state


def reset_runtime_state() -> None:
    """Reset runtime state to defaults (for testing)."""
    get_runtime_state().reset()
