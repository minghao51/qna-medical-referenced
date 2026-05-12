"""Centralized runtime configuration context."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class RuntimeState:
    """Mutable runtime state with thread-safe attribute access.

    Attributes are stored in an internal dict protected by a lock.
    Attribute access (``state.pdf_extractor_strategy``) acquires the lock
    automatically via ``__getattr__`` / ``__setattr__``.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _data: dict[str, Any] = field(default_factory=dict, repr=False)

    _DEFAULTS: ClassVar[dict[str, Any]] = {
        "structured_chunking_enabled": True,
        "source_chunk_configs_override": None,
        "auto_select_strategy": False,
        "pdf_extractor_strategy": "pypdf_pdfplumber",
        "pdf_table_extractor": "heuristic",
        "index_only_classified_pages": True,
        "html_extractor_strategy": "trafilatura_bs",
        "html_extractor_mode": "auto",
        "page_classification_enabled": True,
        "reranker_instance": None,
        "vector_store_initialized": False,
        "vector_store_initialized_signature": None,
    }

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        with object.__getattribute__(self, "_lock"):
            data = object.__getattribute__(self, "_data")
            if name in data:
                return data[name]
            defaults = object.__getattribute__(self, "_DEFAULTS")
            if name in defaults:
                return defaults[name]
        raise AttributeError(f"'RuntimeState' has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        with object.__getattribute__(self, "_lock"):
            object.__getattribute__(self, "_data")[name] = value

    def reset(self) -> None:
        with self._lock:
            self._data.clear()

    def reset_vector_store_state(self) -> None:
        with self._lock:
            self._data["vector_store_initialized"] = False
            self._data.pop("vector_store_initialized_signature", None)

    def set_vector_store_initialized(self, signature: str | None) -> None:
        with self._lock:
            self._data["vector_store_initialized"] = True
            self._data["vector_store_initialized_signature"] = signature

    def get_vector_store_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "initialized": self._data.get(
                    "vector_store_initialized",
                    self._DEFAULTS["vector_store_initialized"],
                ),
                "signature": self._data.get(
                    "vector_store_initialized_signature",
                    self._DEFAULTS["vector_store_initialized_signature"],
                ),
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            merged = dict(self._DEFAULTS)
            merged.update(self._data)
            return {
                "structured_chunking_enabled": merged["structured_chunking_enabled"],
                "source_chunk_configs_override": merged["source_chunk_configs_override"],
                "auto_select_strategy": merged["auto_select_strategy"],
                "pdf_extractor_strategy": merged["pdf_extractor_strategy"],
                "pdf_table_extractor": merged["pdf_table_extractor"],
                "index_only_classified_pages": merged["index_only_classified_pages"],
                "html_extractor_strategy": merged["html_extractor_strategy"],
                "html_extractor_mode": merged["html_extractor_mode"],
                "page_classification_enabled": merged["page_classification_enabled"],
                "reranker_instance_loaded": merged["reranker_instance"] is not None,
                "vector_store_initialized": merged["vector_store_initialized"],
                "vector_store_initialized_signature": merged["vector_store_initialized_signature"],
            }


_state = RuntimeState()


def get_runtime_state() -> RuntimeState:
    return _state


def reset_runtime_state() -> None:
    get_runtime_state().reset()
