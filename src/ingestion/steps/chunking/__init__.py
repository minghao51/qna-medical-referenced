"""Structured chunking package."""

from typing import Optional

from src.ingestion.steps.chunking.config import (
    DEFAULT_SOURCE_CHUNK_CONFIGS,
    get_source_chunk_configs,
    set_auto_select_strategy,
    set_source_chunk_configs,
    set_structured_chunking_enabled,
)
from src.ingestion.steps.chunking.core import TextChunker, chunk_documents

__all__ = [
    "DEFAULT_SOURCE_CHUNK_CONFIGS",
    "TextChunker",
    "chunk_documents",
    "get_chonkie_chunker",
    "get_source_chunk_configs",
    "set_auto_select_strategy",
    "set_source_chunk_configs",
    "set_structured_chunking_enabled",
]


def get_chonkie_chunker(
    strategy: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    min_chunk_size: int = 100,
    embedding_model: Optional[str] = None,
    medical_model: Optional[str] = None,
):
    from src.ingestion.steps.chunking.chonkie_adapter import ChonkieChunkerAdapter

    if strategy == "medical_semantic":
        try:
            import spacy  # noqa: F401
        except ImportError:
            raise ImportError(
                "The 'medical_semantic' chunking strategy requires the 'spacy' package. "
                "Install it with: uv pip install -e '.[medical]'"
            )

        from src.ingestion.steps.chunking.medical_semantic import MedicalSemanticChunkerAdapter

        return MedicalSemanticChunkerAdapter(
            strategy=strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min_chunk_size,
            embedding_model=embedding_model,
            medical_model=medical_model or "en_core_web_sm",
        )

    return ChonkieChunkerAdapter(
        strategy=strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        min_chunk_size=min_chunk_size,
        embedding_model=embedding_model,
    )
