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

# Complete, independent build-metadata fixture: every key the build payload
# records (provenance included) as literal values, so the required-key gate is
# exercised without reusing the production builder to compute the expectation.
_BUILD_METADATA = {
    "source_snapshot_sha256": "a" * 64,
    "embedding_model": "synthetic-embedder",
    "embedding_batch_size": 8,
    "semantic_weight": 0.6,
    "keyword_weight": 0.2,
    "boost_weight": 0.2,
    "page_classification_enabled": True,
    "index_only_classified_pages": False,
    "html_extractor_mode": "auto",
    "html_extractor_strategy": "synthetic_html",
    "pdf_extractor_strategy": "synthetic_pdf",
    "pdf_table_extractor": "synthetic_table",
    "structured_chunking_enabled": True,
    "source_chunk_configs": '{"default": {"chunk_size": 512}}',
    "enable_hype": False,
    "hype_sample_rate": 0.1,
    "hype_max_chunks": 500,
    "hype_questions_per_chunk": 2,
    "enable_keyword_extraction": False,
    "enable_chunk_summaries": False,
    "keyword_extraction_sample_rate": 1.0,
    "keyword_extraction_max_chunks": 500,
}

# Keys recorded by every build; provenance is absent from this view.
_REQUIRED_BUILD_KEYS = tuple(key for key in _BUILD_METADATA if key != "source_snapshot_sha256")


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


def _patch_index(
    monkeypatch, *, contents=None, index_metadata=None, build_metadata=_BUILD_METADATA
):
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

    def fake_build_metadata(*, include_source_digest: bool = True, source_digest=None):
        if build_metadata is not None:
            return dict(build_metadata)
        if include_source_digest:
            return None
        # Mirrors the real fallback: configuration view without provenance.
        return {
            key: value for key, value in _BUILD_METADATA.items() if key != "source_snapshot_sha256"
        }

    monkeypatch.setattr(rag_index, "build_collection_build_metadata", fake_build_metadata)
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
        index_metadata=dict(_BUILD_METADATA),
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
        index_metadata={**_BUILD_METADATA, "embedding_model": "different-embedder"},
    )

    with pytest.raises(RuntimeError, match="does not match runtime settings"):
        await rag_index.initialize_vector_store_async(allow_build=False)

    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_false_detects_extractor_and_chunking_drift(monkeypatch):
    for key, stale_value in (
        ("html_extractor_mode", "different-mode"),
        ("structured_chunking_enabled", False),
        ("enable_hype", True),
        ("source_chunk_configs", '{"default": {"chunk_size": 1024}}'),
    ):
        store, _state, ingestion_calls = _patch_index(
            monkeypatch,
            contents=["stale chunk"],
            index_metadata={**_BUILD_METADATA, key: stale_value},
        )

        with pytest.raises(RuntimeError, match=key):
            await rag_index.initialize_vector_store_async(allow_build=False)

        assert store.clear_calls == 0
        assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_false_detects_provenance_drift(monkeypatch):
    store, _state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["stale chunk"],
        index_metadata={**_BUILD_METADATA, "source_snapshot_sha256": "b" * 64},
    )

    with pytest.raises(RuntimeError, match="source_snapshot_sha256"):
        await rag_index.initialize_vector_store_async(allow_build=False)

    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_false_ignores_persisted_keys_unknown_to_runtime(monkeypatch):
    store, _state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["ready chunk"],
        index_metadata={**_BUILD_METADATA, "experiment_name": "synthetic-experiment"},
    )

    result = await rag_index.initialize_vector_store_async(allow_build=False)

    assert result["status"] == "ready"
    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_false_warns_but_starts_when_provenance_is_absent(monkeypatch, caplog):
    legacy_metadata = {
        key: value for key, value in _BUILD_METADATA.items() if key != "source_snapshot_sha256"
    }
    store, _state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["legacy chunk"],
        index_metadata=legacy_metadata,
    )

    with caplog.at_level("WARNING", logger=rag_index.__name__):
        result = await rag_index.initialize_vector_store_async(allow_build=False)

    assert result["status"] == "ready"
    assert store.clear_calls == 0
    assert ingestion_calls == []
    warnings = [
        record
        for record in caplog.records
        if record.levelname == "WARNING" and "source_snapshot_sha256" in record.getMessage()
    ]
    assert len(warnings) == 1


@pytest.mark.asyncio
async def test_allow_build_false_compares_build_config_when_corpus_is_unavailable(monkeypatch):
    store, _state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["ready chunk"],
        index_metadata={**_BUILD_METADATA, "html_extractor_mode": "different-mode"},
        build_metadata=None,
    )

    with pytest.raises(RuntimeError, match="html_extractor_mode"):
        await rag_index.initialize_vector_store_async(allow_build=False)

    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_false_validates_once_per_initialized_store(monkeypatch):
    store, state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["ready chunk"],
        index_metadata=dict(_BUILD_METADATA),
    )
    build_calls: list[bool] = []

    def fake_build_metadata(*, include_source_digest: bool = True, source_digest=None):
        build_calls.append(include_source_digest)
        return dict(_BUILD_METADATA)

    monkeypatch.setattr(rag_index, "build_collection_build_metadata", fake_build_metadata)

    first = await rag_index.initialize_vector_store_async(allow_build=False)
    second = await rag_index.initialize_vector_store_async(allow_build=False)

    assert first["status"] == second["status"] == "ready"
    assert state.vector_store_initialized is True
    assert build_calls.count(True) == 1
    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_false_revalidates_after_runtime_signature_change(monkeypatch):
    signature = {"value": "signature-1"}
    store, _state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["ready chunk"],
        index_metadata=dict(_BUILD_METADATA),
    )
    build_calls: list[bool] = []
    monkeypatch.setattr(rag_index, "_vector_store_runtime_signature", lambda: signature["value"])

    def fake_build_metadata(*, include_source_digest: bool = True, source_digest=None):
        build_calls.append(include_source_digest)
        return dict(_BUILD_METADATA)

    monkeypatch.setattr(rag_index, "build_collection_build_metadata", fake_build_metadata)

    assert (await rag_index.initialize_vector_store_async(allow_build=False))["status"] == "ready"
    signature["value"] = "signature-2"
    store.documents["index_metadata"] = {**_BUILD_METADATA, "embedding_model": "drifted-model"}

    with pytest.raises(RuntimeError, match="embedding_model"):
        await rag_index.initialize_vector_store_async(allow_build=False)

    assert build_calls.count(True) == 2
    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_true_initialization_does_not_earn_validation_credit(monkeypatch):
    """A permissive load must never let a later no-build call skip the gate."""
    store, state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["ready chunk"],
        index_metadata=dict(_BUILD_METADATA),
    )

    permissive = await rag_index.initialize_vector_store_async(allow_build=True)

    assert permissive["status"] == "ready"
    assert permissive["reused_existing_index"] is True
    assert state.vector_store_initialized is True
    # Metadata is discovered to be stale only after the permissive load.
    store.documents["index_metadata"] = {**_BUILD_METADATA, "embedding_model": "drifted-model"}

    with pytest.raises(RuntimeError, match="embedding_model"):
        await rag_index.initialize_vector_store_async(allow_build=False)

    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_false_fails_on_partial_build_metadata(monkeypatch):
    # Only the embedding keys survive: page classification, extractor, chunking
    # and enrichment keys are all missing, so this map is genuinely partial.
    partial_metadata = {
        key: _BUILD_METADATA[key]
        for key in (
            "embedding_model",
            "embedding_batch_size",
            "semantic_weight",
            "keyword_weight",
            "boost_weight",
        )
    }
    store, _state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["ready chunk"],
        index_metadata=partial_metadata,
        build_metadata=None,
    )

    with pytest.raises(RuntimeError, match="missing required build keys") as excinfo:
        await rag_index.initialize_vector_store_async(allow_build=False)

    message = str(excinfo.value)
    assert "page_classification_enabled" in message
    assert "html_extractor_mode" in message
    assert "source_chunk_configs" in message
    assert "enable_hype" in message
    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_false_requires_the_complete_build_key_set(monkeypatch):
    """Any single missing build key still fails closed, not just the 5 core ones."""
    for missing_key in _REQUIRED_BUILD_KEYS:
        metadata = {key: value for key, value in _BUILD_METADATA.items() if key != missing_key}
        store, _state, ingestion_calls = _patch_index(
            monkeypatch,
            contents=["ready chunk"],
            index_metadata=metadata,
        )

        with pytest.raises(RuntimeError, match=missing_key):
            await rag_index.initialize_vector_store_async(allow_build=False)

        assert store.clear_calls == 0
        assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_false_names_missing_required_build_keys(monkeypatch):
    metadata = {
        key: value
        for key, value in _BUILD_METADATA.items()
        if key not in {"embedding_batch_size", "keyword_weight"}
    }
    store, _state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["ready chunk"],
        index_metadata=metadata,
    )

    with pytest.raises(RuntimeError) as excinfo:
        await rag_index.initialize_vector_store_async(allow_build=False)

    message = str(excinfo.value)
    assert "embedding_batch_size" in message
    assert "keyword_weight" in message
    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_rebuild_drops_validation_credit_before_clearing_store(monkeypatch):
    """A failed clear must not leave a stale index certified as verified."""
    store, state, _ingestion_calls = _patch_index(
        monkeypatch,
        contents=["ready chunk"],
        index_metadata=dict(_BUILD_METADATA),
    )

    assert (await rag_index.initialize_vector_store_async(allow_build=False))["status"] == "ready"
    assert getattr(state, rag_index._VALIDATED_SIGNATURE_ATTR, None) is not None

    def failing_clear():
        raise RuntimeError("synthetic clear failure")

    monkeypatch.setattr(store, "clear", failing_clear)

    with pytest.raises(RuntimeError, match="synthetic clear failure"):
        await rag_index.initialize_vector_store_async(rebuild=True)

    assert getattr(state, rag_index._VALIDATED_SIGNATURE_ATTR, None) is None


@pytest.mark.asyncio
async def test_allow_build_false_fails_closed_on_empty_build_metadata(monkeypatch):
    store, _state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["ready chunk"],
        index_metadata={},
    )

    with pytest.raises(RuntimeError, match="embedding_model"):
        await rag_index.initialize_vector_store_async(allow_build=False)

    assert store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_allow_build_false_credit_is_bound_to_the_store_instance(monkeypatch):
    """Same runtime signature, different store: credit must not carry over."""
    first_store, _state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["ready chunk"],
        index_metadata=dict(_BUILD_METADATA),
    )

    assert (await rag_index.initialize_vector_store_async(allow_build=False))["status"] == "ready"

    second_store = _Store(
        ["ready chunk"],
        {**_BUILD_METADATA, "embedding_model": "drifted-model"},
    )
    monkeypatch.setattr(rag_index, "get_vector_store", lambda: second_store)

    with pytest.raises(RuntimeError, match="embedding_model"):
        await rag_index.initialize_vector_store_async(allow_build=False)

    assert first_store.clear_calls == 0
    assert second_store.clear_calls == 0
    assert ingestion_calls == []


@pytest.mark.asyncio
async def test_configure_runtime_for_experiment_clears_validation_credit(monkeypatch):
    store, _state, ingestion_calls = _patch_index(
        monkeypatch,
        contents=["ready chunk"],
        index_metadata=dict(_BUILD_METADATA),
    )
    monkeypatch.setattr(
        rag_index,
        "build_experiment_runtime_config",
        lambda experiment: SimpleNamespace(vector_store=None),
    )
    monkeypatch.setattr(rag_index, "apply_runtime_config", lambda config: None)

    assert (await rag_index.initialize_vector_store_async(allow_build=False))["status"] == "ready"

    rag_index.configure_runtime_for_experiment({"retrieval": {}})
    store.documents["index_metadata"] = {**_BUILD_METADATA, "embedding_model": "drifted-model"}

    with pytest.raises(RuntimeError, match="embedding_model"):
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
