"""Qwen embedding wrapper for chonkie chunkers.

Provides an embedding interface that uses the existing Qwen/Dashscope
embedding pipeline, allowing chonkie semantic chunkers to use
the same embeddings as the main retrieval pipeline.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import uuid4

import numpy as np
from chonkie.embeddings.base import BaseEmbeddings

from src.infra.telemetry import (
    ErrorCode,
    Operation,
    Stage,
    UsageCompleteness,
    telemetry_operation,
)
from src.ingestion.indexing.embedding import EXPECTED_EMBEDDING_DIM, embed_texts

# Models routed through embed_texts are always requested at the fixed width
# EXPECTED_EMBEDDING_DIM (see the `dimensions=` argument of the API call), so
# known models never need a live probe for their dimension.
_KNOWN_MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-v4": EXPECTED_EMBEDDING_DIM,
}

# Dimensions discovered by probing unknown models, shared across instances so
# each model probes the live API at most once per process.
_PROBED_MODEL_DIMENSIONS: dict[str, int] = {}


def _record_wrapper_embedding_span(
    *,
    model_name: str,
    input_count: int,
    result_count: int | None,
    elapsed_ms: float,
    error_code: ErrorCode | None = None,
) -> None:
    with telemetry_operation(
        Operation.EMBEDDING,
        stage=Stage.EMBEDDING,
        model=model_name,
        input_count=input_count,
        attempt_id=str(uuid4()),
        elapsed_ms=elapsed_ms,
    ) as span:
        span.set_usage(completeness=UsageCompleteness.UNKNOWN)
        if result_count is not None:
            span.set_result_count(result_count)
        if error_code is not None:
            span.mark_error(error_code)


class QwenEmbeddings(BaseEmbeddings):
    """Embedding wrapper that uses Qwen's embedding API.

    Implements chonkie's embedding interface so SemanticChunker
    and LateChunker can use Qwen embeddings for boundary detection.

    Example:
        >>> from chonkie import SemanticChunker
        >>> from src.ingestion.steps.chunking.qwen_embedding_wrapper import QwenEmbeddings
        >>> embedder = QwenEmbeddings()
        >>> chunker = SemanticChunker(embedding_model=embedder, chunk_size=512)
    """

    def __init__(
        self,
        model: str = "text-embedding-v4",
        batch_size: int = 10,
        dimensions: int | None = None,
    ):
        """Initialize Qwen embeddings wrapper.

        Args:
            model: Qwen embedding model name
            batch_size: Number of texts to embed per API call
            dimensions: Embedding dimensions (resolved without a live API call
                for known models, probed once otherwise)
        """
        super().__init__()
        self.model = model
        self.batch_size = batch_size
        self._dimensions: int | None = dimensions

    @property
    def dimension(self) -> int:
        """Get embedding dimensions without a live API call for known models."""
        if self._dimensions is None:
            cached = _KNOWN_MODEL_DIMENSIONS.get(self.model) or _PROBED_MODEL_DIMENSIONS.get(
                self.model
            )
            if cached is None:
                # Unknown model: probe once, then share the result process-wide.
                dummy_emb = embed_texts(["test"], batch_size=1, model=self.model)
                cached = len(dummy_emb[0])
                _PROBED_MODEL_DIMENSIONS[self.model] = cached
            self._dimensions = cached
        return self._dimensions

    def embed(self, text: str) -> np.ndarray:
        """Embed a single text using Qwen API.

        Args:
            text: Text string to embed

        Returns:
            Embedding vector as numpy array
        """
        started = perf_counter()
        try:
            embedding = np.array(embed_texts([text], batch_size=1, model=self.model)[0])
        except Exception:
            _record_wrapper_embedding_span(
                model_name=self.model,
                input_count=1,
                result_count=None,
                elapsed_ms=(perf_counter() - started) * 1000,
                error_code=ErrorCode.UPSTREAM,
            )
            raise
        _record_wrapper_embedding_span(
            model_name=self.model,
            input_count=1,
            result_count=1,
            elapsed_ms=(perf_counter() - started) * 1000,
        )
        return embedding

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed a batch of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors as numpy arrays
        """
        started = perf_counter()
        try:
            embeddings = [
                np.array(embedding)
                for embedding in embed_texts(texts, batch_size=self.batch_size, model=self.model)
            ]
        except Exception:
            _record_wrapper_embedding_span(
                model_name=self.model,
                input_count=len(texts),
                result_count=None,
                elapsed_ms=(perf_counter() - started) * 1000,
                error_code=ErrorCode.UPSTREAM,
            )
            raise
        _record_wrapper_embedding_span(
            model_name=self.model,
            input_count=len(texts),
            result_count=len(embeddings),
            elapsed_ms=(perf_counter() - started) * 1000,
        )
        return embeddings

    def get_tokenizer(self) -> Any:
        """Return a simple character tokenizer for Qwen API-based embeddings."""
        from chonkie.tokenizer import CharacterTokenizer

        return CharacterTokenizer()

    def __call__(self, text: str | list[str]) -> np.ndarray | list[np.ndarray]:
        """Embed text(s) using Qwen API.

        Args:
            text: Single text string or list of text strings

        Returns:
            Single embedding as numpy array, or list of embeddings
        """
        if isinstance(text, str):
            return self.embed(text)
        return self.embed_batch(text)
