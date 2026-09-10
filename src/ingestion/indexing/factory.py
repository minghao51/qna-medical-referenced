"""Signature-cached singleton factory for ChromaVectorStore.

Split in Phase 2 (roadmap P2.3) from chroma_store.py.
"""

from __future__ import annotations

from typing import Any, ClassVar

from src.config import settings
from src.ingestion.indexing.store import ChromaVectorStore


class ChromaVectorStoreFactory:
    _instance: ClassVar[ChromaVectorStore | None] = None
    _runtime_config: ClassVar[dict[str, Any]] = {}
    _runtime_signature_value: ClassVar[tuple[tuple[str, Any], ...] | None] = None

    @classmethod
    def _normalize_runtime_config(cls, config: dict[str, Any] | None = None) -> dict[str, Any]:
        resolved = dict(config or cls._runtime_config or {})
        return {
            "collection_name": resolved.get("collection_name", settings.storage.collection_name),
            "semantic_weight": float(resolved.get("semantic_weight", 0.6)),
            "keyword_weight": float(resolved.get("keyword_weight", 0.2)),
            "boost_weight": float(resolved.get("boost_weight", 0.2)),
            "embedding_model": resolved.get("embedding_model", settings.llm.embedding_model),
            "embedding_batch_size": int(
                resolved.get("embedding_batch_size", settings.llm.embedding_batch_size)
            ),
            "index_metadata": dict(resolved.get("index_metadata", {})),
        }

    @classmethod
    def _compute_runtime_signature(cls, config: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
        return tuple(
            sorted(
                (
                    key,
                    tuple(sorted(value.items())) if isinstance(value, dict) else value,
                )
                for key, value in config.items()
            )
        )

    @classmethod
    def set_runtime_config(cls, config: dict[str, Any] | None = None) -> None:
        normalized = cls._normalize_runtime_config(config)
        signature = cls._compute_runtime_signature(normalized)
        cls._runtime_config = normalized
        if cls._runtime_signature_value != signature:
            cls._instance = None
            cls._runtime_signature_value = signature

    @classmethod
    def get_runtime_config(cls) -> dict[str, Any]:
        return dict(cls._normalize_runtime_config(cls._runtime_config))

    @classmethod
    def get_vector_store(cls, config: dict[str, Any] | None = None) -> ChromaVectorStore:
        normalized = cls._normalize_runtime_config(config)
        signature = cls._compute_runtime_signature(normalized)
        if config is not None:
            cls.set_runtime_config(normalized)
        if cls._instance is None:
            cls._instance = ChromaVectorStore(**normalized)
            cls._runtime_signature_value = signature
        elif cls._runtime_signature_value != signature:
            cls._instance = ChromaVectorStore(**normalized)
            cls._runtime_signature_value = signature
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
        cls._runtime_config = {}
        cls._runtime_signature_value = None


def set_vector_store_runtime_config(config: dict[str, Any] | None = None) -> None:
    ChromaVectorStoreFactory.set_runtime_config(config)


def get_vector_store_runtime_config() -> dict[str, Any]:
    return ChromaVectorStoreFactory.get_runtime_config()


def get_vector_store(config: dict[str, Any] | None = None) -> ChromaVectorStore:
    return ChromaVectorStoreFactory.get_vector_store(config)
