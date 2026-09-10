"""Unit tests for the chunking-subsystem cleanups (H7).

Covers: single strategy registry, per-config chunker caching, and the
QwenEmbeddings known-dimension table.
"""

from __future__ import annotations

import pytest

from src.ingestion.steps.chunking.config import _VALID_STRATEGIES
from src.ingestion.steps.chunking.core import TextChunker
from src.ingestion.steps.chunking.strategies import CHONKIE_ADAPTER_STRATEGIES, CHUNKING_STRATEGIES


def test_strategy_registry_is_single_source_of_truth():
    # core.py and config.py both derive their whitelists from strategies.py.
    assert TextChunker.SUPPORTED_STRATEGIES == CHUNKING_STRATEGIES
    assert _VALID_STRATEGIES == CHUNKING_STRATEGIES


def test_medical_semantic_is_selectable_end_to_end():
    # "medical_semantic" is a genuinely selectable TextChunker strategy (the
    # registry must not drop it), even though the plain chonkie adapter
    # rejects it.
    assert "medical_semantic" in TextChunker.SUPPORTED_STRATEGIES
    assert "medical_semantic" in _VALID_STRATEGIES


def test_chonkie_adapter_whitelist_is_truthful():
    pytest.importorskip("chonkie")
    from src.ingestion.steps.chunking.chonkie_adapter import ChonkieChunkerAdapter

    assert ChonkieChunkerAdapter.SUPPORTED_STRATEGIES == CHONKIE_ADAPTER_STRATEGIES
    assert "medical_semantic" not in ChonkieChunkerAdapter.SUPPORTED_STRATEGIES
    # Constructing the plain adapter with medical_semantic must fail fast at
    # the whitelist instead of reaching _create_chunker's ValueError.
    with pytest.raises(ValueError, match="does not support strategy 'medical_semantic'"):
        ChonkieChunkerAdapter(strategy="medical_semantic")


def test_per_source_chunkers_are_cached_by_resolved_config():
    docs = [
        {"id": f"d{idx}", "source": f"doc{idx}.pdf", "content": "Some care sentence. " * 30}
        for idx in range(4)
    ]
    base = TextChunker(chunk_size=512, chunk_overlap=64)
    chunks = base.chunk_documents_with_configs(
        docs, source_chunk_configs={"pdf": {"chunk_size": 200, "chunk_overlap": 24}}
    )
    assert chunks
    # One distinct non-self config -> exactly one cached chunker reused for all docs.
    assert len(base._config_chunker_cache) == 1
    cached = next(iter(base._config_chunker_cache.values()))
    assert cached is not base
    assert (cached.chunk_size, cached.chunk_overlap) == (200, 24)

    chunks_again = base.chunk_documents_with_configs(
        docs, source_chunk_configs={"pdf": {"chunk_size": 200, "chunk_overlap": 24}}
    )
    assert chunks_again == chunks
    assert len(base._config_chunker_cache) == 1

    # A config equal to self (including strategy) reuses self without
    # polluting the cache.
    base.chunk_documents_with_configs(
        docs,
        source_chunk_configs={
            "pdf": {"chunk_size": 512, "chunk_overlap": 64, "strategy": "recursive"}
        },
    )
    assert len(base._config_chunker_cache) == 1


def test_semantic_adapter_built_once_per_config(monkeypatch):
    pytest.importorskip("chonkie")
    import src.ingestion.steps.chunking.qwen_embedding_wrapper as qw
    from tests.fixtures.gen_chunking_golden import _deterministic_embed

    monkeypatch.setattr(qw, "embed_texts", _deterministic_embed)

    import src.ingestion.steps.chunking.chonkie_adapter as adapter_mod

    calls = []

    class CountingEmbeddings(adapter_mod.QwenEmbeddings):
        def __init__(self, *args, **kwargs):
            calls.append(1)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(adapter_mod, "QwenEmbeddings", CountingEmbeddings)

    docs = [
        {"id": f"d{idx}", "source": f"doc{idx}.pdf", "content": "Aspirin dosing text. " * 40}
        for idx in range(3)
    ]
    base = TextChunker(chunk_size=512, chunk_overlap=64, strategy="custom_recursive")
    base.chunk_documents_with_configs(
        docs, source_chunk_configs={"pdf": {"strategy": "chonkie_semantic"}}
    )
    cached = next(iter(base._config_chunker_cache.values()))
    assert cached.strategy == "chonkie_semantic"
    # Repeated chunk_text calls through the cached chunker build the chonkie
    # adapter (and its embedder) exactly once, not once per call.
    for doc in docs:
        assert cached.chunk_text(doc["content"], doc["source"], doc["id"])
    assert len(calls) == 1


def test_known_model_dimension_avoids_live_probe(monkeypatch):
    pytest.importorskip("chonkie")
    import src.ingestion.steps.chunking.qwen_embedding_wrapper as qw

    def _fail(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("dimension lookup must not call the embedding API")

    monkeypatch.setattr(qw, "embed_texts", _fail)
    embedder = qw.QwenEmbeddings(model="text-embedding-v4")
    assert embedder.dimension == qw.EXPECTED_EMBEDDING_DIM
    # Resolved dimension is cached per model across instances.
    assert qw.QwenEmbeddings(model="text-embedding-v4").dimension == qw.EXPECTED_EMBEDDING_DIM


def test_unknown_model_dimension_probes_once_and_caches(monkeypatch):
    pytest.importorskip("chonkie")
    import src.ingestion.steps.chunking.qwen_embedding_wrapper as qw

    qw._PROBED_MODEL_DIMENSIONS.pop("some-unknown-model", None)
    calls = []

    def fake_embed(texts, batch_size=10, model=None, **kwargs):
        calls.append(list(texts))
        return [[0.0] * 321 for _ in texts]

    monkeypatch.setattr(qw, "embed_texts", fake_embed)
    first = qw.QwenEmbeddings(model="some-unknown-model")
    assert first.dimension == 321
    assert len(calls) == 1
    # A fresh instance for the same model reuses the probe result.
    second = qw.QwenEmbeddings(model="some-unknown-model")
    assert second.dimension == 321
    assert len(calls) == 1
    qw._PROBED_MODEL_DIMENSIONS.pop("some-unknown-model", None)
