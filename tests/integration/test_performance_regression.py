"""Lightweight latency and memory regression guards for critical endpoints."""

from __future__ import annotations

import time
import tracemalloc
from pathlib import Path

from fastapi.testclient import TestClient

from src.app.factory import create_app
from src.app.middleware.auth import APIKeyConfig
from src.app.middleware.rate_limit import RateLimiter
from src.config import settings
from src.infra.storage.file_chat_history_store import FileChatHistoryStore


def _build_client(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.setattr("src.app.factory.validate_security_configuration", lambda: None)
    monkeypatch.setattr("src.app.factory.initialize_runtime_index_async", lambda: None)
    monkeypatch.setattr("src.app.middleware.rate_limit.RATE_LIMIT_DB", tmp_path / "rate_limits.db")
    monkeypatch.setattr(settings.api, "api_keys", "secret-key")
    monkeypatch.setattr(settings.api, "api_keys_json", None)
    APIKeyConfig.reload()
    app = create_app()
    app.state.chat_history_store = FileChatHistoryStore(tmp_path / "chat_history.json")
    monkeypatch.setattr(
        "src.app.middleware.rate_limit.rate_limiter",
        RateLimiter(requests_per_minute=200),
    )
    return TestClient(app)


def test_chat_endpoint_latency_regression_guard(monkeypatch, tmp_path: Path):
    async def _mock_stream_chat_message(**kwargs):
        del kwargs
        yield (
            "ok",
            {
                "done": True,
                "sources": [],
                "pipeline": None,
            },
        )

    monkeypatch.setattr("src.app.routes.chat.stream_chat_message", _mock_stream_chat_message)
    client = _build_client(monkeypatch, tmp_path)

    latencies = []
    for _ in range(5):
        start = time.perf_counter()
        response = client.post("/chat", headers={"X-API-Key": "secret-key"}, json={"message": "hello"})
        latencies.append(time.perf_counter() - start)
        assert response.status_code == 200

    assert max(latencies) < 2.0


def test_documents_endpoint_memory_regression_guard(monkeypatch, tmp_path: Path):
    class _FakeStore:
        def list_documents_paginated(self, *, limit, offset, source_type=None):
            del limit, offset, source_type
            return {
                "total": 1,
                "items": [
                    {
                        "id": "doc-1",
                        "source": "guide.pdf",
                        "page": 1,
                        "source_type": "pdf",
                        "source_class": "guideline_pdf",
                        "content_type": "paragraph",
                        "content_preview": "preview",
                        "content_length": 7,
                    }
                ],
                "source_type_counts": {"pdf": 1},
                "index_metadata": {"collection": "test"},
            }

        def get_document_by_id(self, doc_id):
            del doc_id
            return None

    from src.config.context import get_runtime_state

    get_runtime_state().vector_store_initialized = True
    monkeypatch.setattr("src.app.routes.documents.get_vector_store", lambda: _FakeStore())
    client = _build_client(monkeypatch, tmp_path)

    tracemalloc.start()
    start = time.perf_counter()
    response = client.get("/documents?limit=50&offset=0", headers={"X-API-Key": "secret-key"})
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert response.status_code == 200
    assert elapsed < 2.0
    assert peak < 25_000_000
