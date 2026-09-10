"""Unit tests for embedding retry, timeout and dimension validation (no network)."""

import httpx
import openai
import pytest

from src.ingestion.indexing import embedding


class _StubEmbeddingItem:
    def __init__(self, value):
        self.embedding = value


class _StubResponse:
    def __init__(self, items):
        self.data = items


class _StubEmbeddingsAPI:
    """Stub of the OpenAI embeddings API with scripted transient failures."""

    def __init__(self, failures=None, dim=None):
        self.failures = list(failures or [])
        self.dim = dim if dim is not None else embedding.EXPECTED_EMBEDDING_DIM
        self.calls = []

    def create(self, *, model, input, dimensions, timeout=None):
        self.calls.append(
            {
                "model": model,
                "input": list(input),
                "dimensions": dimensions,
                "timeout": timeout,
            }
        )
        if self.failures:
            raise self.failures.pop(0)
        return _StubResponse([_StubEmbeddingItem([0.0] * self.dim) for _ in input])


class _StubClient:
    def __init__(self, api):
        self.embeddings = api


def _rate_limit_error() -> openai.RateLimitError:
    request = httpx.Request("POST", "https://api.test/embeddings")
    response = httpx.Response(429, request=request)
    return openai.RateLimitError("rate limited", response=response, body=None)


def _timeout_error() -> openai.APITimeoutError:
    return openai.APITimeoutError(httpx.Request("POST", "https://api.test/embeddings"))


@pytest.fixture(autouse=True)
def _clear_embedding_cache():
    with embedding._embedding_cache_lock:
        embedding._embedding_cache.clear()
    yield
    with embedding._embedding_cache_lock:
        embedding._embedding_cache.clear()


@pytest.fixture(autouse=True)
def recorded_sleep_delays(monkeypatch):
    delays = []
    monkeypatch.setattr(embedding.time, "sleep", delays.append)
    return delays


def test_transient_errors_are_retried_with_backoff(monkeypatch, recorded_sleep_delays):
    api = _StubEmbeddingsAPI(failures=[_rate_limit_error(), _timeout_error()])
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _StubClient(api))

    embeddings, _ = embedding.embed_texts_with_stats(["alpha"], batch_size=1, model="retry-model")

    assert len(embeddings) == 1
    assert len(embeddings[0]) == embedding.EXPECTED_EMBEDDING_DIM
    assert len(api.calls) == 3
    base_delay = embedding.settings.retry.retry_delay
    assert recorded_sleep_delays == pytest.approx([base_delay, base_delay * 2])


def test_retry_exhaustion_raises_last_error(monkeypatch):
    failures = [_rate_limit_error(), _rate_limit_error(), _rate_limit_error(), _rate_limit_error()]
    api = _StubEmbeddingsAPI(failures=failures)
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _StubClient(api))

    with pytest.raises(openai.RateLimitError):
        embedding.embed_texts_with_stats(["alpha"], batch_size=1, model="retry-model")

    max_retries = embedding.settings.retry.max_retries
    assert len(api.calls) == max_retries


def test_non_retryable_error_raises_immediately(monkeypatch):
    api = _StubEmbeddingsAPI(failures=[ValueError("bad request")])
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _StubClient(api))

    with pytest.raises(ValueError, match="bad request"):
        embedding.embed_texts_with_stats(["alpha"], batch_size=1, model="retry-model")

    assert len(api.calls) == 1


def test_timeout_and_dimensions_are_passed(monkeypatch):
    api = _StubEmbeddingsAPI()
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _StubClient(api))

    embedding.embed_texts_with_stats(["alpha"], batch_size=1, model="retry-model")

    call = api.calls[0]
    assert call["dimensions"] == embedding.EXPECTED_EMBEDDING_DIM
    assert call["timeout"] == embedding._EMBEDDING_TIMEOUT_SECONDS


def test_wrong_dimension_raises_clear_error(monkeypatch):
    api = _StubEmbeddingsAPI(dim=4)
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: _StubClient(api))

    with pytest.raises(ValueError, match="retry-model"):
        embedding.embed_texts_with_stats(["alpha"], batch_size=1, model="retry-model")

    with pytest.raises(ValueError, match="expected 768"):
        embedding.embed_texts_with_stats(["beta"], batch_size=1, model="retry-model")
