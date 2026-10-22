"""Readiness guarantees for no-build RAG initialization."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.config.context import RuntimeState
from src.rag import index as rag_index
from src.rag import query_expansion, retrieval, runtime

_RUNTIME_CONFIG = {
    "collection_name": "synthetic",
    "embedding_model": "synthetic-embedder",
    "embedding_batch_size": 8,
    "semantic_weight": 0.6,
    "keyword_weight": 0.2,
    "boost_weight": 0.2,
}


class _Store:
    def __init__(self, contents=None, index_metadata=None):
        self.documents = {
            "contents": list(contents or []),
            "index_metadata": dict(index_metadata or {}),
        }
        self.last_indexing_stats = {}
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1
        self.documents["contents"] = []


class _IngestionResult:
    def to_stats(self):
        return {"attempted": 1, "inserted": 1, "skipped_duplicate_content": 0}


def _patch_index(monkeypatch, *, contents=None, index_metadata=None):
    store = _Store(contents, index_metadata)
    state = RuntimeState()
    ingestion_calls = []

    def ingest(config):
        ingestion_calls.append(config)
        store.documents["contents"] = ["built chunk"]
        return _IngestionResult()

    monkeypatch.setattr(rag_index, "get_runtime_state", lambda: state)
    monkeypatch.setattr(rag_index, "get_vector_store", lambda: store)
    monkeypatch.setattr(rag_index, "get_vector_store_runtime_config", lambda: dict(_RUNTIME_CONFIG))
    monkeypatch.setattr(rag_index, "_vector_store_runtime_signature", lambda: "synthetic-signature")
    monkeypatch.setattr(rag_index, "run_ingestion", ingest)
    monkeypatch.setattr(
        rag_index.IngestionRunConfig,
        "from_runtime_state",
        classmethod(lambda cls, **kwargs: SimpleNamespace(**kwargs)),
    )
    return store, state, ingestion_calls


@pytest.mark.asyncio
async def test_allow_build_false_empty_index_fails_without_clear_or_ingestion(monkeypatch):
    store, _state, ingestion_calls = _patch_index(monkeypatch)

    with pytest.raises(RuntimeError, match="allow_build=False prevents ingestion"):
        await rag_index.initialize_vector_store_async(allow_build=False)

    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_false_reuses_matching_ready_index(monkeypatch):
    store, state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["ready chunk"],
        index_metadata={
            key: _RUNTIME_CONFIG[key] for key in _RUNTIME_CONFIG if key != "collection_name"
        },
    )

    result = await rag_index.initialize_runtime_index_async(allow_build=False)

    assert result["status"] == "ready"
    assert result["reused_existing_index"] is True
    assert result["vector_document_count"] == 1
    assert state.vector_store_initialized is True
    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_false_mismatch_fails_without_rebuild(monkeypatch):
    store, _state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["stale chunk"],
        index_metadata={"embedding_model": "different-embedder"},
    )

    with pytest.raises(RuntimeError, match="does not match runtime settings"):
        await rag_index.initialize_vector_store_async(allow_build=False)

    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_legacy_cold_initialization_still_builds_by_default(monkeypatch):
    store, state, ingestion_calls = _patch_index(monkeypatch)

    result = await rag_index.initialize_runtime_index_async()

    assert result["status"] == "built"
    assert result["reused_existing_index"] is False
    assert len(ingestion_calls) == 1
    assert store.documents["contents"] == ["built chunk"]
    assert state.vector_store_initialized is True


@pytest.mark.asyncio
async def test_async_rag_propagates_allow_build_false(monkeypatch):
    initialization_calls = []
    cfg = SimpleNamespace(
        top_k=1,
        overfetch_multiplier=1,
        search_mode="semantic_only",
        enable_hyde=False,
        hyde_max_length=200,
        enable_hype=False,
        enable_medical_expansion=False,
        medical_expansion_provider="noop",
        enable_reranking=False,
        reranking_mode="cross_encoder",
        rerank_score_threshold=None,
        mmr_lambda=0.75,
        max_chunks_per_source_page=2,
        max_chunks_per_source=3,
        enable_diversification=False,
    )

    monkeypatch.setattr(
        runtime, "_prepare_query", lambda query, options: (query, len(query), cfg, 0.0)
    )

    async def initialize(**kwargs):
        initialization_calls.append(kwargs)

    async def inline_worker(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(runtime, "initialize_runtime_index_async", initialize)
    monkeypatch.setattr(runtime, "_run_owned_worker", inline_worker)
    monkeypatch.setattr(runtime, "get_vector_store", lambda: object())
    monkeypatch.setattr(
        query_expansion,
        "prepare_expanded_queries",
        lambda query, **kwargs: ([query], []),
    )
    monkeypatch.setattr(
        query_expansion,
        "expand_queries_async",
        lambda query, **kwargs: _async_queries(kwargs.get("pre_expanded_queries")),
    )
    monkeypatch.setattr(
        runtime,
        "_extend_with_hype_questions",
        lambda store, query, expanded, **kwargs: (expanded, []),
    )

    async def search(*args, **kwargs):
        return [], {"timing_ms": 0, "score_weights": {}}

    monkeypatch.setattr(retrieval, "retrieve_candidates_with_trace_async", search)
    monkeypatch.setattr(
        runtime, "_rerank_and_diversify", lambda results, *args: (results, None, {}, False)
    )
    monkeypatch.setattr(runtime, "_build_pipeline_trace", lambda **kwargs: ("", [], object()))

    await runtime.retrieve_context_with_trace_async("synthetic query", allow_build=False)

    assert initialization_calls == [{"allow_build": False}]


async def _async_queries(queries):
    return list(queries or [])
