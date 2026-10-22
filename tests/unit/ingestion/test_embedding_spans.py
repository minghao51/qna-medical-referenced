"""Synthetic embedding-boundary telemetry tests; no provider or network access."""

import importlib
import json
import sys
import types
from types import SimpleNamespace
from uuid import UUID

import httpx
import openai
import pytest

# The wrapper targets the optional `chunkers` extra; when that extra is absent a
# temporary synthetic chonkie base is installed strictly for the wrapper's own
# import and then removed, so other tests never observe a fake chonkie module.
_MISSING = object()


@pytest.fixture(scope="module")
def wrapper_module():
    try:
        importlib.import_module("chonkie.embeddings.base")
    except ModuleNotFoundError:
        stub_base = types.ModuleType("chonkie.embeddings.base")

        class _SyntheticBaseEmbeddings:
            pass

        stub_base.BaseEmbeddings = _SyntheticBaseEmbeddings
        stub_pkg = types.ModuleType("chonkie")
        stub_pkg.__path__ = []
        saved = {
            name: sys.modules.get(name, _MISSING) for name in ("chonkie", "chonkie.embeddings.base")
        }
        sys.modules["chonkie"] = stub_pkg
        sys.modules["chonkie.embeddings.base"] = stub_base
        try:
            return importlib.import_module("src.ingestion.steps.chunking.qwen_embedding_wrapper")
        finally:
            for name, module in saved.items():
                if module is _MISSING:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module
    return importlib.import_module("src.ingestion.steps.chunking.qwen_embedding_wrapper")


from src.config.settings import TelemetryConfig
from src.infra.telemetry import (
    ErrorCode,
    Operation,
    Stage,
    Telemetry,
    UsageCompleteness,
    current_telemetry,
    use_telemetry,
)
from src.ingestion.indexing import embedding
from src.ingestion.indexing import store as store_module
from src.ingestion.indexing.store import ChromaVectorStore


class _EmbeddingItem:
    def __init__(self, value):
        self.embedding = value


class _Response:
    def __init__(self, items, usage=None):
        self.data = [_EmbeddingItem(item) for item in items]
        if usage is not None:
            self.usage = usage


class _EmbeddingsAPI:
    def __init__(self, response=None, failures=None):
        self.response = response
        self.failures = list(failures or [])
        self.calls = []

    def create(self, *, model, input, dimensions, timeout=None):
        self.calls.append((model, list(input), dimensions, timeout))
        if self.failures:
            raise self.failures.pop(0)
        if self.response is not None:
            return self.response
        return _Response([[0.0] * dimensions for _ in input])


class _Client:
    def __init__(self, api):
        self.embeddings = api


@pytest.fixture
def local_telemetry():
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    try:
        yield telemetry
    finally:
        telemetry.close()


@pytest.fixture(autouse=True)
def _clear_embedding_cache():
    with embedding._embedding_cache_lock:
        embedding._embedding_cache.clear()
    yield
    with embedding._embedding_cache_lock:
        embedding._embedding_cache.clear()


def _serialized(telemetry):
    return json.dumps(
        [
            {
                "name": span.name,
                "attributes": dict(span.attributes or {}),
                "events": [
                    {"name": event.name, "attributes": dict(event.attributes or {})}
                    for event in span.events
                ],
            }
            for span in telemetry.finished_spans
        ],
        sort_keys=True,
        default=str,
    )


def _spans(telemetry, name):
    return [span for span in telemetry.finished_spans if span.name == name]


def _full_usage():
    return SimpleNamespace(prompt_tokens=12, completion_tokens=0, total_tokens=12)


def test_batch_embedding_spans_record_counts_usage_and_exclude_content(
    monkeypatch, local_telemetry
):
    canary = "doc-1234 SYNTHETIC_SECRET_CANARY patient_id=12345678"
    api = _EmbeddingsAPI()
    api.response = _Response([[0.0] * embedding.EXPECTED_EMBEDDING_DIM] * 2, _full_usage())
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _Client(api))

    with use_telemetry(local_telemetry):
        with local_telemetry.span(Operation.SEARCH) as _:
            vectors, stats = embedding.embed_texts_with_stats(
                [canary, "second synthetic text"], batch_size=2, model="test-embedder"
            )

    assert len(vectors) == 2
    assert stats["batch_count"] == 1
    spans = _spans(local_telemetry, Operation.EMBEDDING.value)
    api_span = next(
        span for span in spans if span.attributes.get("usage.completeness") == "complete"
    )
    assert api_span.attributes["telemetry.stage"] == Stage.EMBEDDING.value
    assert api_span.attributes["telemetry.model"] == "test-embedder"
    assert api_span.attributes["telemetry.input_count"] == 2
    assert api_span.attributes["telemetry.result_count"] == 2
    assert api_span.attributes["usage.input_tokens"] == 12
    assert api_span.attributes["usage.output_tokens"] == 0
    attempt_id = UUID(api_span.attributes["telemetry.attempt_id"])
    assert attempt_id.version == 4

    search_span = _spans(local_telemetry, Operation.SEARCH.value)[0]
    assert not any(key.startswith("usage.") for key in search_span.attributes)
    serialized = _serialized(local_telemetry)
    assert canary not in serialized
    assert "second synthetic text" not in serialized
    assert all(not span.events for span in local_telemetry.finished_spans)


def test_empty_input_records_single_success_span_without_provider_call(
    monkeypatch, local_telemetry
):
    def _unexpected_client() -> _Client:
        raise AssertionError("empty input must not reach the embedding provider")

    monkeypatch.setattr(embedding, "get_embedding_client", _unexpected_client)

    with use_telemetry(local_telemetry):
        vectors, stats = embedding.embed_texts_with_stats([], batch_size=2, model="test-embedder")

    assert vectors == []
    assert stats["text_count"] == 0
    assert stats["batch_count"] == 0
    assert stats["failure_count"] == 0
    assert len(local_telemetry.finished_spans) == 1
    span = local_telemetry.finished_spans[0]
    assert span.name == Operation.EMBEDDING.value
    assert span.attributes["telemetry.stage"] == Stage.EMBEDDING.value
    assert span.attributes["telemetry.model"] == "test-embedder"
    assert span.attributes["telemetry.input_count"] == 0
    assert span.attributes["telemetry.result_count"] == 0
    assert span.attributes["telemetry.outcome"] == "success"
    assert "telemetry.error_code" not in span.attributes


def test_outer_embedding_span_records_no_provider_usage(monkeypatch, local_telemetry):
    api = _EmbeddingsAPI()
    api.response = _Response([[0.0] * embedding.EXPECTED_EMBEDDING_DIM] * 2, _full_usage())
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _Client(api))

    with use_telemetry(local_telemetry):
        embedding.embed_texts_with_stats(
            ["first synthetic text", "second synthetic text"], batch_size=2, model="test-embedder"
        )

    embedding_spans = _spans(local_telemetry, Operation.EMBEDDING.value)
    assert len(embedding_spans) == 2
    provider_span = next(
        span
        for span in embedding_spans
        if span.attributes.get("usage.completeness") == UsageCompleteness.COMPLETE.value
    )
    assert provider_span.attributes["usage.input_tokens"] == 12
    assert provider_span.attributes["usage.output_tokens"] == 0
    # The usage-recording path belongs to the provider-call span only: the
    # outer wrapper span records no usage tokens (its completeness stays the
    # no-provider-response default) and no error.
    outer_spans = [span for span in embedding_spans if "usage.input_tokens" not in span.attributes]
    assert len(outer_spans) == 1
    outer_span = outer_spans[0]
    assert "usage.input_tokens" not in outer_span.attributes
    assert "usage.output_tokens" not in outer_span.attributes
    assert outer_span.attributes["usage.completeness"] == UsageCompleteness.UNKNOWN.value
    assert outer_span.attributes["telemetry.outcome"] == "success"
    assert "telemetry.error_code" not in outer_span.attributes


@pytest.mark.parametrize(
    ("usage", "expected_completeness", "expected_input", "expected_output"),
    [
        (None, UsageCompleteness.UNKNOWN.value, None, None),
        (
            SimpleNamespace(prompt_tokens=5),
            UsageCompleteness.PARTIAL.value,
            5,
            None,
        ),
    ],
)
def test_embedding_span_labels_missing_or_partial_provider_usage(
    monkeypatch,
    local_telemetry,
    usage,
    expected_completeness,
    expected_input,
    expected_output,
):
    api = _EmbeddingsAPI(response=_Response([[0.0] * embedding.EXPECTED_EMBEDDING_DIM], usage))
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _Client(api))

    with use_telemetry(local_telemetry):
        embedding.embed_texts_with_stats(["synthetic query"], batch_size=1, model="test-embedder")

    api_span = next(
        span
        for span in _spans(local_telemetry, Operation.EMBEDDING.value)
        if span.attributes.get("telemetry.input_count") == 1
        and "usage.completeness" in span.attributes
    )
    assert api_span.attributes["usage.completeness"] == expected_completeness
    assert api_span.attributes.get("usage.input_tokens") == expected_input
    assert api_span.attributes.get("usage.output_tokens") == expected_output


def test_store_batch_and_query_embedding_paths_emit_child_spans(monkeypatch, local_telemetry):
    store = object.__new__(ChromaVectorStore)
    store.embedding_model = "store-embedder"
    store._query_embedding_fn = None
    store.semantic_weight = 0.6
    store.keyword_weight = 0.2
    store.boost_weight = 0.2
    vectors = [[0.0] * embedding.EXPECTED_EMBEDDING_DIM]
    monkeypatch.setattr(
        store_module,
        "embed_texts_with_stats",
        lambda texts, batch_size, model: (vectors * len(texts), {"batch_count": 1}),
    )

    store._rebuild_index_if_needed = lambda: None
    store._ensure_embeddings_loaded = lambda: None
    store._keyword_score = lambda query: {0: 1.0}
    store._doc_ids = ["source-1234"]
    store._doc_contents = ["synthetic document"]
    store._doc_embeddings = [vectors[0]]
    store._doc_metadatas = [{}]
    monkeypatch.setattr(
        store_module,
        "rank_documents",
        lambda **kwargs: [{"idx": 0, "combined_score": 1.0}],
    )

    with use_telemetry(local_telemetry):
        with local_telemetry.span(Operation.SEARCH):
            batch, _ = store._embed_with_stats(["synthetic chunk"], batch_size=1)
            assert store._embed(["synthetic batch"])[0] == vectors[0]
            store._search_ranked("SYNTHETIC_SECRET_CANARY patient_id=12345678", "semantic_only")

    assert batch == vectors
    search_span = _spans(local_telemetry, Operation.SEARCH.value)[0]
    assert not any(key.startswith("usage.") for key in search_span.attributes)
    store_spans = [
        span
        for span in _spans(local_telemetry, Operation.EMBEDDING.value)
        if span.attributes.get("telemetry.model") == "store-embedder"
    ]
    assert len(store_spans) == 3
    assert all(span.attributes["telemetry.stage"] == Stage.EMBEDDING.value for span in store_spans)
    assert all(
        span.attributes["usage.completeness"] == UsageCompleteness.UNKNOWN.value
        for span in store_spans
    )
    assert all(span.attributes["telemetry.result_count"] == 1 for span in store_spans)
    serialized = _serialized(local_telemetry)
    assert "synthetic chunk" not in serialized
    assert "synthetic batch" not in serialized
    assert "SYNTHETIC_SECRET_CANARY" not in serialized
    assert "12345678" not in serialized
    assert "source-1234" not in serialized


def test_query_embedding_failure_marks_child_error_and_keeps_search_fallback(
    local_telemetry, monkeypatch
):
    def fail_query(_query: str) -> list[float]:
        raise ValueError("SYNTHETIC_SECRET_CANARY provider detail")

    store = object.__new__(ChromaVectorStore)
    store.embedding_model = "store-embedder"
    store._query_embedding_fn = fail_query
    store._strict_query_embedding = False
    store.semantic_weight = 0.6
    store.keyword_weight = 0.2
    store.boost_weight = 0.2
    store._rebuild_index_if_needed = lambda: None
    store._ensure_embeddings_loaded = lambda: None
    store._keyword_score = lambda query: {0: 1.0}
    store._doc_ids = ["source-1234"]
    store._doc_contents = ["synthetic document"]
    store._doc_embeddings = []
    store._doc_metadatas = [{}]
    monkeypatch.setattr(
        store_module,
        "rank_documents",
        lambda **kwargs: [{"idx": 0, "combined_score": 1.0}],
    )

    with use_telemetry(local_telemetry):
        with local_telemetry.span(Operation.SEARCH):
            ranked, trace, _ = store._search_ranked("synthetic query", "semantic_only")

    assert ranked
    assert trace["query_embedding_timing_ms"] == 0
    failed = [
        span
        for span in _spans(local_telemetry, Operation.EMBEDDING.value)
        if span.attributes.get("telemetry.outcome") == "error"
    ]
    assert len(failed) == 1
    assert failed[0].attributes["telemetry.error_code"] == ErrorCode.UPSTREAM.value
    assert "SYNTHETIC_SECRET_CANARY" not in _serialized(local_telemetry)
    assert "provider detail" not in _serialized(local_telemetry)


def test_qwen_wrapper_delegation_spans_record_batch_counts_without_content(
    monkeypatch, local_telemetry, wrapper_module
):
    model = wrapper_module.QwenEmbeddings(model="wrapper-embedder", batch_size=2)
    monkeypatch.setattr(
        wrapper_module,
        "embed_texts",
        lambda texts, batch_size, model: [[0.0] * embedding.EXPECTED_EMBEDDING_DIM for _ in texts],
    )

    with use_telemetry(local_telemetry):
        with local_telemetry.span(Operation.SEARCH):
            assert (
                model.embed("synthetic wrapper input").shape[0] == embedding.EXPECTED_EMBEDDING_DIM
            )
            assert len(model.embed_batch(["first", "second"])) == 2

    spans = [
        span
        for span in _spans(local_telemetry, Operation.EMBEDDING.value)
        if span.attributes.get("telemetry.model") == "wrapper-embedder"
    ]
    assert [span.attributes["telemetry.input_count"] for span in spans] == [1, 2]
    assert all(span.attributes["telemetry.result_count"] in {1, 2} for span in spans)
    assert all(
        span.attributes["usage.completeness"] == UsageCompleteness.UNKNOWN.value for span in spans
    )
    serialized = _serialized(local_telemetry)
    assert "synthetic wrapper input" not in serialized
    assert "first" not in serialized
    assert "second" not in serialized


def test_subsequent_embedding_attempt_is_retry_with_fresh_attempt_id(monkeypatch, local_telemetry):
    request = httpx.Request("POST", "https://api.test/embeddings")
    response = httpx.Response(429, request=request)
    failure = openai.RateLimitError("synthetic provider failure", response=response, body=None)
    api = _EmbeddingsAPI(
        response=_Response([[0.0] * embedding.EXPECTED_EMBEDDING_DIM], _full_usage()),
        failures=[failure],
    )
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _Client(api))
    monkeypatch.setattr(embedding.time, "sleep", lambda _: None)

    with use_telemetry(local_telemetry):
        result, _ = embedding.embed_texts_with_stats(
            ["synthetic retry input"], batch_size=1, model="test-embedder"
        )

    assert len(result) == 1
    retry_span = _spans(local_telemetry, Operation.RETRY.value)[0]
    assert retry_span.attributes["telemetry.stage"] == Stage.EMBEDDING.value
    assert retry_span.attributes["telemetry.retry_count"] == 1
    assert "telemetry.error_code" not in retry_span.attributes
    assert retry_span.attributes["telemetry.outcome"] == "success"
    attempt_ids = [
        span.attributes["telemetry.attempt_id"]
        for span in local_telemetry.finished_spans
        if "telemetry.attempt_id" in span.attributes
    ]
    assert len(attempt_ids) == len(set(attempt_ids))
    assert all(UUID(value).version == 4 for value in attempt_ids)
    serialized = _serialized(local_telemetry)
    assert "synthetic retry input" not in serialized
    assert "synthetic provider failure" not in serialized


def test_handled_embedding_failure_marks_safe_error_and_still_raises(monkeypatch, local_telemetry):
    api = _EmbeddingsAPI(failures=[ValueError("SYNTHETIC_SECRET_CANARY private body")])
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _Client(api))

    with use_telemetry(local_telemetry):
        with pytest.raises(ValueError, match="SYNTHETIC_SECRET_CANARY"):
            embedding.embed_texts_with_stats(["synthetic failed input"], model="test-embedder")

    failed_spans = [
        span
        for span in _spans(local_telemetry, Operation.EMBEDDING.value)
        if span.attributes.get("telemetry.outcome") == "error"
    ]
    # Two error spans: the per-attempt span keeps its blanket UPSTREAM code and
    # the outer wrapper span (finished last) classifies the unmarked
    # provider-origin ValueError as UPSTREAM too — the outer code follows the
    # failure's origin, not its exception type, so both spans now agree.
    assert len(failed_spans) == 2
    assert failed_spans[0].attributes["telemetry.error_code"] == ErrorCode.UPSTREAM.value
    assert failed_spans[-1].attributes["telemetry.error_code"] == ErrorCode.UPSTREAM.value
    serialized = _serialized(local_telemetry)
    assert "SYNTHETIC_SECRET_CANARY" not in serialized
    assert "private body" not in serialized
    assert "synthetic failed input" not in serialized


def test_local_dimension_mismatch_classifies_outer_span_internal(monkeypatch, local_telemetry):
    wrong_width = embedding.EXPECTED_EMBEDDING_DIM - 1
    api = _EmbeddingsAPI(response=_Response([[0.0] * wrong_width]))
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _Client(api))

    with use_telemetry(local_telemetry):
        with pytest.raises(ValueError, match="returned dimension"):
            embedding.embed_texts_with_stats(
                ["synthetic dimension input"], batch_size=1, model="test-embedder"
            )

    assert len(api.calls) == 1
    # The provider call itself succeeded (a success attempt span); only the
    # outer wrapper span errors, and the locally raised dimension-mismatch
    # ValueError is classified INTERNAL by origin. Every embedding span,
    # including the outer wrapper, carries its own generated attempt id.
    success_attempts = [
        span
        for span in _spans(local_telemetry, Operation.EMBEDDING.value)
        if span.attributes.get("telemetry.outcome") == "success"
    ]
    assert len(success_attempts) == 1
    assert "telemetry.attempt_id" in success_attempts[0].attributes
    outer_errors = [
        span
        for span in _spans(local_telemetry, Operation.EMBEDDING.value)
        if span.attributes.get("telemetry.outcome") == "error"
    ]
    assert len(outer_errors) == 1
    assert outer_errors[0].attributes["telemetry.error_code"] == ErrorCode.INTERNAL.value
    serialized = _serialized(local_telemetry)
    assert "synthetic dimension input" not in serialized


def test_incomplete_embedding_results_classify_outer_span_internal(monkeypatch, local_telemetry):
    # Drive the real resolver invariant without mocking internals: a negative
    # batch size turns the batch loop (range step < 0) into a no-op, so the
    # uncached slot stays unassigned and embed_texts_with_stats raises its own
    # incomplete-results RuntimeError, which must be classified by origin.
    api = _EmbeddingsAPI()
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _Client(api))

    with use_telemetry(local_telemetry):
        with pytest.raises(RuntimeError, match="incomplete results"):
            embedding.embed_texts_with_stats(
                ["synthetic incomplete input"], batch_size=-1, model="test-embedder"
            )

    assert api.calls == []
    errors = [
        span
        for span in _spans(local_telemetry, Operation.EMBEDDING.value)
        if span.attributes.get("telemetry.outcome") == "error"
    ]
    # No provider attempt ran, so the only error span is the outer wrapper
    # (which carries its own generated attempt id like every embedding span).
    assert len(errors) == 1
    assert errors[0].attributes["telemetry.error_code"] == ErrorCode.INTERNAL.value
    serialized = _serialized(local_telemetry)
    assert "synthetic incomplete input" not in serialized


def test_unparseable_provider_response_classifies_attempt_and_outer_internal(
    monkeypatch, local_telemetry
):
    api = _EmbeddingsAPI(response=SimpleNamespace())  # provider response without `.data`
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _Client(api))

    with use_telemetry(local_telemetry):
        with pytest.raises(AttributeError):
            embedding.embed_texts_with_stats(
                ["synthetic parse input"], batch_size=1, model="test-embedder"
            )

    errors = [
        span
        for span in _spans(local_telemetry, Operation.EMBEDDING.value)
        if span.attributes.get("telemetry.outcome") == "error"
    ]
    # The result-count parse failure is INTERNAL on both the per-attempt span
    # and the outer wrapper span (each carries its own generated attempt id).
    assert len(errors) == 2
    assert {span.attributes["telemetry.error_code"] for span in errors} == {
        ErrorCode.INTERNAL.value
    }
    serialized = _serialized(local_telemetry)
    assert "synthetic parse input" not in serialized


def test_embedding_without_active_telemetry_remains_a_pure_noop(monkeypatch):
    api = _EmbeddingsAPI(
        response=_Response([[0.0] * embedding.EXPECTED_EMBEDDING_DIM], _full_usage())
    )
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _Client(api))

    assert current_telemetry() is None
    vectors, stats = embedding.embed_texts_with_stats(["offline synthetic"], model="test-embedder")

    assert current_telemetry() is None
    assert len(vectors) == 1
    assert stats["text_count"] == 1
    assert len(api.calls) == 1


@pytest.mark.parametrize("max_retries", [1, 2])
def test_terminal_transient_embedding_failure_is_retry_exhausted(
    monkeypatch, local_telemetry, max_retries
):
    request = httpx.Request("POST", "https://api.test/embeddings")
    response = httpx.Response(429, request=request)
    failure = openai.RateLimitError("synthetic provider failure", response=response, body=None)
    api = _EmbeddingsAPI(failures=[failure] * max_retries)
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _Client(api))
    monkeypatch.setattr(
        embedding,
        "settings",
        SimpleNamespace(retry=SimpleNamespace(max_retries=max_retries, retry_delay=0.0)),
    )
    monkeypatch.setattr(embedding.time, "sleep", lambda _: None)

    with use_telemetry(local_telemetry):
        with pytest.raises(openai.RateLimitError):
            embedding.embed_texts_with_stats(
                ["synthetic exhausted input"], batch_size=1, model="test-embedder"
            )

    error_spans = [
        span
        for span in local_telemetry.finished_spans
        if span.attributes.get("telemetry.outcome") == "error"
    ]
    assert error_spans
    # The terminal attempt span and the outer wrapper span are both
    # RETRY_EXHAUSTED (also when the first and only attempt is terminal — the
    # fix); only earlier mid-retry transient attempts stay UPSTREAM.
    exhausted = [
        span
        for span in error_spans
        if span.attributes.get("telemetry.error_code") == ErrorCode.RETRY_EXHAUSTED.value
    ]
    assert len(exhausted) == 2
    assert (
        len(
            [
                span
                for span in error_spans
                if span.attributes.get("telemetry.error_code") == ErrorCode.UPSTREAM.value
            ]
        )
        == max_retries - 1
    )
    serialized = _serialized(local_telemetry)
    assert "synthetic exhausted input" not in serialized
    assert "synthetic provider failure" not in serialized
