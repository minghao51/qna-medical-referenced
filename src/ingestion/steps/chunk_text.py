"""Compatibility facade for text chunking APIs."""

from src.ingestion.steps.chunking import (
    DEFAULT_SOURCE_CHUNK_CONFIGS,
    TextChunker,
    chunk_documents,
    get_source_chunk_configs,
    set_auto_select_strategy,
    set_source_chunk_configs,
    set_structured_chunking_enabled,
)

__all__ = [
    "DEFAULT_SOURCE_CHUNK_CONFIGS",
    "TextChunker",
    "chunk_documents",
    "get_source_chunk_configs",
    "set_auto_select_strategy",
    "set_source_chunk_configs",
    "set_structured_chunking_enabled",
]
