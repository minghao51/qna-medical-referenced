"""Adapter layer for chonkie chunkers.

Provides a unified interface for using chonkie chunkers while
maintaining compatibility with the existing pipeline.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from chonkie import LateChunker, Pipeline, SemanticChunker

from src.ingestion.steps.chunking.qwen_embedding_wrapper import QwenEmbeddings

logger = logging.getLogger(__name__)


class ChonkieChunkerAdapter:
    """Adapter for chonkie chunkers.

    Wraps chonkie chunkers to provide a consistent interface
    with the existing TextChunker, enabling easy switching between
    chunking strategies.
    """

    SUPPORTED_STRATEGIES: ClassVar[frozenset[str]] = frozenset({
        "chonkie_recursive",
        "chonkie_semantic",
        "chonkie_late",
        "medical_semantic",
    })

    def __init__(
        self,
        strategy: str,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        min_chunk_size: int = 100,
        embedding_model: str | None = None,
    ):
        """Initialize the chonkie chunker adapter.

        Args:
            strategy: Chunking strategy (chonkie_recursive, chonkie_semantic, chonkie_late)
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
            min_chunk_size: Minimum chunk size (behavior varies by strategy)
            embedding_model: Embedding model for semantic/late strategies
        """
        if strategy not in self.SUPPORTED_STRATEGIES:
            raise ValueError(
                f"ChonkieChunkerAdapter does not support strategy '{strategy}'. "
                f"Supported: {self.SUPPORTED_STRATEGIES}"
            )

        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.embedding_model = embedding_model or "text-embedding-v4"

        self._chunker = self._create_chunker()

    def _create_chunker(self) -> Any:
        """Create the appropriate chonkie chunker or pipeline."""
        if self.strategy == "chonkie_recursive":
            return self._create_recursive_chunker()
        elif self.strategy in ("chonkie_semantic", "chonkie_late"):
            return self._create_semantic_chunker()
        raise ValueError(f"Unknown strategy: {self.strategy}")

    def _create_recursive_chunker(self) -> Pipeline:
        """Create recursive chunker with overlap refinement."""
        pipe = Pipeline().chunk_with("recursive", chunk_size=self.chunk_size)
        if self.chunk_overlap > 0:
            pipe = pipe.refine_with("overlap", context_size=self.chunk_overlap)
        return pipe

    def _create_semantic_chunker(self) -> Any:
        """Create semantic/late chunker (overlap handled separately)."""
        embedder = QwenEmbeddings(model=self.embedding_model)

        if self.strategy == "chonkie_semantic":
            return SemanticChunker(
                embedding_model=embedder,
                chunk_size=self.chunk_size,
                min_sentences_per_chunk=1,
            )
        elif self.strategy == "chonkie_late":
            return LateChunker(
                embedding_model=embedder,
                chunk_size=self.chunk_size,
            )
        else:
            raise ValueError(f"Unknown semantic strategy: {self.strategy}")

    def chunk_text(
        self,
        text: str,
        source: str = "unknown",
        doc_id: str = "doc",
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """Chunk text and return in our standard format.

        Args:
            text: Text to chunk
            source: Source document name
            doc_id: Document identifier
            page: Page number

        Returns:
            List of chunk dictionaries with our standard schema
        """
        # Pipeline uses run(), individual chunkers use chunk()
        if hasattr(self._chunker, "run"):
            result = self._chunker.run(text)
            chonkie_chunks = result.chunks if hasattr(result, "chunks") else [result]
        else:
            chonkie_chunks = self._chunker.chunk(text)

        chunks = [
            {
                "id": f"{doc_id}_p{page}_chunk_{idx}",
                "source": source,
                "page": page,
                "content": chunk.text,
                "content_type": "paragraph",
                "chunk_index": idx,
                "char_count": len(chunk.text),
                "token_count_estimate": (
                    chunk.token_count if hasattr(chunk, "token_count") else len(chunk.text.split())
                ),
            }
            for idx, chunk in enumerate(chonkie_chunks)
        ]

        # Apply overlap refinement for semantic chunkers if overlap > 0
        # Note: For chonkie_recursive, overlap is handled by Pipeline
        # For semantic/late, we add overlap context to each chunk's content
        if self.chunk_overlap > 0 and self.strategy in ("chonkie_semantic", "chonkie_late"):
            chunks = self._apply_overlap(chunks, text)

        return chunks

    def _apply_overlap(
        self, chunks: list[dict[str, Any]], original_text: str
    ) -> list[dict[str, Any]]:
        """Apply overlap by prepending context from previous chunks.

        For semantic chunkers where Pipeline overlap refinement isn't available.
        """
        if len(chunks) <= 1 or self.chunk_overlap <= 0:
            return chunks

        # Tokenize by words for overlap calculation
        def get_words(text: str) -> list[str]:
            return text.split()

        enriched_chunks = []
        for i, chunk in enumerate(chunks):
            if i == 0:
                enriched_chunks.append(chunk)
            else:
                # Get last N words from previous chunk as overlap
                prev_text = chunks[i - 1]["content"]
                prev_words = get_words(prev_text)
                overlap_words = (
                    prev_words[-self.chunk_overlap :]
                    if len(prev_words) > self.chunk_overlap
                    else prev_words
                )
                overlap_text = " ".join(overlap_words)

                # Prepend overlap to current chunk content
                enriched_content = f"{overlap_text} {chunk['content']}"
                enriched_chunk = dict(chunk)
                enriched_chunk["content"] = enriched_content
                enriched_chunk["char_count"] = len(enriched_content)
                enriched_chunks.append(enriched_chunk)

        return enriched_chunks
