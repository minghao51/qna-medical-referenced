"""Centralized runtime configuration context.

Replaces scattered module-level globals with a single thread-safe container.
Each module still exposes its getter/setter functions for backward compatibility,
but state is stored here.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _RuntimeState:
    """Mutable runtime state, protected by a lock."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # Chunking config (from chunking/config.py)
    structured_chunking_enabled: bool = True
    source_chunk_configs_override: dict | None = None
    auto_select_strategy: bool = False

    # PDF loader (from load_pdfs.py)
    pdf_extractor_strategy: str = "pypdf_pdfplumber"
    pdf_table_extractor: str = "heuristic"

    # Markdown loader (from load_markdown.py)
    index_only_classified_pages: bool = True

    # HTML converter (from convert_html.py)
    html_extractor_strategy: str = "trafilatura_bs"
    html_extractor_mode: str = "auto"
    page_classification_enabled: bool = True

    # Reranker (from reranker.py)
    reranker_instance: Any = None


# Module-level singleton — one per process
_state = _RuntimeState()


def get_runtime_state() -> _RuntimeState:
    """Return the global runtime state."""
    return _state


def reset_runtime_state() -> None:
    """Reset runtime state to defaults (for testing)."""
    global _state
    _state = _RuntimeState()
