import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.app.factory import create_app
from src.app.middleware.auth import APIKeyConfig
from src.app.middleware.rate_limit import RateLimiter
from src.app.security import generate_api_key_record
from src.config import settings
from src.infra.storage.file_chat_history_store import FileChatHistoryStore


def _parse_sse_events(response) -> list[dict]:
    return [json.loads(line[6:]) for line in response.text.split("\n") if line.startswith("data: ")]


class DummyLLMClient:
    def generate(self, prompt: str, context: str) -> str:
        return f"answer:{prompt}:{len(context)}"


def _build_client(
    monkeypatch,
    tmp_path: Path,
    *,
    api_keys: str | None = "secret-key",
    rate_limit: int = 10,
    anonymous_chat_rate_limit: int = 2,
    trust_proxy_headers: bool = False,
    rate_limit_bypass_key_ids: str = "",
    rate_limit_bypass_roles: str = "",
):
    monkeypatch.setattr("src.app.factory.validate_security_configuration", lambda: None)
    monkeypatch.setattr("src.app.factory.initialize_runtime_index_async", lambda: None)
    monkeypatch.setattr("src.app.middleware.rate_limit.RATE_LIMIT_DB", tmp_path / "rate_limits.db")
    monkeypatch.setattr(settings.api, "api_keys", api_keys)
    monkeypatch.setattr(settings.api, "api_keys_json", None)
    monkeypatch.setattr(settings.api, "anonymous_chat_rate_limit_per_minute", anonymous_chat_rate_limit)
    monkeypatch.setattr(settings.api, "anonymous_browser_cookie_name", "anon_browser_id")
    monkeypatch.setattr(settings.api, "chat_session_cookie_name", "chat_session_id")
    monkeypatch.setattr(settings.api, "chat_session_cookie_max_age_seconds", 3600)
    monkeypatch.setattr(settings.api, "trust_proxy_headers", trust_proxy_headers)
    monkeypatch.setattr(settings.api, "rate_limit_bypass_key_ids", rate_limit_bypass_key_ids)
    monkeypatch.setattr(settings.api, "rate_limit_bypass_roles", rate_limit_bypass_roles)
    APIKeyConfig.reload()
    app = create_app()
    app.state.llm_client = DummyLLMClient()
    app.state.chat_history_store = FileChatHistoryStore(tmp_path / "chat_history.json")
    monkeypatch.setattr(
        "src.app.middleware.rate_limit.rate_limiter",
        RateLimiter(requests_per_minute=rate_limit),
    )
    return TestClient(app)


def test_chat_requires_valid_api_key(monkeypatch, tmp_path: Path):
    client = _build_client(monkeypatch, tmp_path)

    missing = client.post("/chat", json={"message": "hello", "session_id": "s1"})
    invalid = client.post(
        "/chat",
        headers={"X-API-Key": "bad-key"},
        json={"message": "hello", "session_id": "s1"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 403
    assert missing.headers["X-Request-ID"]
    assert missing.json()["error"]["request_id"] == missing.headers["X-Request-ID"]


def test_chat_success_and_rate_limit_headers(monkeypatch, tmp_path: Path):
    async def mock_stream_chat_message(**kwargs):
        yield (
            "ok",
            {
                "done": True,
                "sources": [
                    {"label": "doc", "source": "example.com", "url": "https://example.com"}
                ],
                "pipeline": None,
            },
        )

    monkeypatch.setattr(
        "src.app.routes.chat.stream_chat_message",
        mock_stream_chat_message,
    )
    client = _build_client(monkeypatch, tmp_path, rate_limit=2)

    first = client.post(
        "/chat",
        headers={"X-API-Key": "secret-key"},
        json={"message": "hello", "session_id": "s1"},
    )
    second = client.post(
        "/chat",
        headers={"X-API-Key": "secret-key"},
        json={"message": "hello again", "session_id": "s1"},
    )
    third = client.post(
        "/chat",
        headers={"X-API-Key": "secret-key"},
        json={"message": "blocked", "session_id": "s1"},
    )

    assert first.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "2"
    assert second.headers["X-RateLimit-Remaining"] == "0"
    assert third.status_code == 429
    assert third.headers["Retry-After"]


def test_rate_limit_bypass_by_key_id(monkeypatch, tmp_path: Path):
    async def mock_stream_chat_message(**kwargs):
        yield ("ok", {"done": True, "sources": [], "pipeline": None})

    monkeypatch.setattr("src.app.routes.chat.stream_chat_message", mock_stream_chat_message)
    client = _build_client(
        monkeypatch,
        tmp_path,
        api_keys="master-key",
        rate_limit=1,
        rate_limit_bypass_key_ids="key-1",
    )

    first = client.post("/chat", headers={"X-API-Key": "master-key"}, json={"message": "hello"})
    second = client.post("/chat", headers={"X-API-Key": "master-key"}, json={"message": "again"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert "X-RateLimit-Limit" not in second.headers


def test_rate_limit_bypass_by_role(monkeypatch, tmp_path: Path):
    async def mock_stream_chat_message(**kwargs):
        yield ("ok", {"done": True, "sources": [], "pipeline": None})

    monkeypatch.setattr("src.app.routes.chat.stream_chat_message", mock_stream_chat_message)
    client = _build_client(
        monkeypatch,
        tmp_path,
        api_keys=None,
        rate_limit=1,
        rate_limit_bypass_roles="master",
    )
    monkeypatch.setattr(
        settings.api,
        "api_keys_json",
        '[{"id":"ops-master","key":"master-key","role":"master","status":"active"}]',
    )
    APIKeyConfig.reload()

    first = client.post("/chat", headers={"X-API-Key": "master-key"}, json={"message": "hello"})
    second = client.post("/chat", headers={"X-API-Key": "master-key"}, json={"message": "again"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert "X-RateLimit-Limit" not in second.headers


def test_chat_accepts_bcrypt_hashed_api_keys_json(monkeypatch, tmp_path: Path):
    async def mock_stream_chat_message(**kwargs):
        yield ("ok", {"done": True, "sources": [], "pipeline": None})

    monkeypatch.setattr("src.app.routes.chat.stream_chat_message", mock_stream_chat_message)
    client = _build_client(
        monkeypatch,
        tmp_path,
        api_keys=None,
        rate_limit=5,
    )
    monkeypatch.setattr(
        settings.api,
        "api_keys_json",
        json.dumps([generate_api_key_record("ops-admin", "secret-key", role="admin")]),
    )
    APIKeyConfig.reload()

    response = client.post("/chat", headers={"X-API-Key": "secret-key"}, json={"message": "hello"})

    assert response.status_code == 200


def test_request_id_preserved_on_http_errors(monkeypatch, tmp_path: Path):
    client = _build_client(monkeypatch, tmp_path)

    response = client.get("/evaluation/steps/not-a-stage", headers={"X-API-Key": "secret-key"})

    assert response.status_code == 400
    assert response.headers["X-Request-ID"]
    body = response.json()
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


def test_evaluation_ablation_returns_consistent_error(monkeypatch, tmp_path: Path):
    client = _build_client(monkeypatch, tmp_path)
    evals_dir = tmp_path / "evals"
    run_dir = evals_dir / "20260308T101010.123456Z_baseline"
    run_dir.mkdir(parents=True)
    (run_dir / "ablation_results.json").write_text("{bad json", encoding="utf-8")
    monkeypatch.setattr("src.app.routes.evaluation.EVALS_DIR", evals_dir)
    monkeypatch.setattr("src.app.routes.evaluation.LATEST_POINTER", evals_dir / "latest_run.txt")

    response = client.get("/evaluation/ablation", headers={"X-API-Key": "secret-key"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to load ablation results"


def test_anonymous_chat_rate_limit_scoped_by_browser_cookie(monkeypatch, tmp_path: Path):
    async def mock_stream_chat_message(**kwargs):
        yield (
            "ok",
            {
                "done": True,
                "sources": [
                    {"label": "doc", "source": "example.com", "url": "https://example.com"}
                ],
                "pipeline": None,
            },
        )

    monkeypatch.setattr(
        "src.app.routes.chat.stream_chat_message",
        mock_stream_chat_message,
    )
    client = _build_client(
        monkeypatch,
        tmp_path,
        api_keys=None,
        rate_limit=50,
        anonymous_chat_rate_limit=2,
    )

    first = client.post("/chat", json={"message": "hello", "session_id": "s1"})
    second = client.post("/chat", json={"message": "again", "session_id": "s1"})
    third = client.post("/chat", json={"message": "blocked", "session_id": "s1"})

    assert first.status_code == 200
    assert first.cookies.get("anon_browser_id")
    assert second.status_code == 200
    assert third.status_code == 429

    other_browser = TestClient(client.app)
    fresh = other_browser.post("/chat", json={"message": "new browser", "session_id": "s2"})
    assert fresh.status_code == 200


def test_anonymous_chat_uses_forwarded_ip_when_proxy_headers_enabled(monkeypatch, tmp_path: Path):
    async def mock_stream_chat_message(**kwargs):
        yield (
            "ok",
            {
                "done": True,
                "sources": [
                    {"label": "doc", "source": "example.com", "url": "https://example.com"}
                ],
                "pipeline": None,
            },
        )

    monkeypatch.setattr(
        "src.app.routes.chat.stream_chat_message",
        mock_stream_chat_message,
    )
    client = _build_client(
        monkeypatch,
        tmp_path,
        api_keys=None,
        rate_limit=50,
        anonymous_chat_rate_limit=1,
        trust_proxy_headers=True,
    )

    first = client.post(
        "/chat",
        headers={"X-Forwarded-For": "198.51.100.10, 10.0.0.1"},
        json={"message": "hello", "session_id": "s1"},
    )
    second = client.post(
        "/chat",
        headers={"X-Forwarded-For": "198.51.100.10, 10.0.0.1"},
        json={"message": "blocked", "session_id": "s1"},
    )
    third = client.post(
        "/chat",
        headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"},
        json={"message": "allowed", "session_id": "s1"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert third.status_code == 200


def test_anonymous_chat_limit_still_applies_when_global_limit_disabled(monkeypatch, tmp_path: Path):
    async def mock_stream_chat_message(**kwargs):
        yield (
            "ok",
            {
                "done": True,
                "sources": [
                    {"label": "doc", "source": "example.com", "url": "https://example.com"}
                ],
                "pipeline": None,
            },
        )

    monkeypatch.setattr(
        "src.app.routes.chat.stream_chat_message",
        mock_stream_chat_message,
    )
    client = _build_client(
        monkeypatch,
        tmp_path,
        api_keys=None,
        rate_limit=0,
        anonymous_chat_rate_limit=1,
    )

    first = client.post("/chat", json={"message": "hello", "session_id": "s1"})
    second = client.post("/chat", json={"message": "blocked", "session_id": "s1"})

    assert first.status_code == 200
    assert second.status_code == 429


def test_chat_history_isolated_by_server_session_cookie(monkeypatch, tmp_path: Path):
    async def mock_stream_chat_message(**kwargs):
        yield (
            f"ok:{kwargs['session_id']}",
            {
                "done": True,
                "sources": [],
                "pipeline": None,
            },
        )

    monkeypatch.setattr(
        "src.app.routes.chat.stream_chat_message",
        mock_stream_chat_message,
    )
    client_a = _build_client(monkeypatch, tmp_path, api_keys=None, rate_limit=50)
    client_b = TestClient(client_a.app)

    first = client_a.post("/chat", json={"message": "hello", "session_id": "shared-client-value"})
    second = client_b.post("/chat", json={"message": "hello", "session_id": "shared-client-value"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.cookies.get("chat_session_id")
    assert second.cookies.get("chat_session_id")
    assert first.cookies.get("chat_session_id") != second.cookies.get("chat_session_id")
    first_events = _parse_sse_events(first)
    second_events = _parse_sse_events(second)
    assert first_events[0]["content"] != second_events[0]["content"]


def test_clear_history_rotates_chat_session_cookie(monkeypatch, tmp_path: Path):
    client = _build_client(monkeypatch, tmp_path, api_keys=None, rate_limit=50)

    initial = client.get("/history")
    original_cookie = initial.cookies.get("chat_session_id")

    cleared = client.delete("/history")
    rotated_cookie = cleared.cookies.get("chat_session_id")

    assert initial.status_code == 200
    assert cleared.status_code == 200
    assert original_cookie
    assert rotated_cookie
    assert rotated_cookie != original_cookie


def test_evaluate_single_requires_authenticated_request(monkeypatch, tmp_path: Path):
    client = _build_client(monkeypatch, tmp_path, api_keys=None, rate_limit=50)

    response = client.post(
        "/evaluation/evaluate-single",
        json={"query": "q", "answer": "a", "context": "c"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing X-API-Key header"


def test_evaluate_single_validates_payload_shape(monkeypatch, tmp_path: Path):
    client = _build_client(monkeypatch, tmp_path, api_keys="secret-key", rate_limit=50)

    response = client.post(
        "/evaluation/evaluate-single",
        headers={"X-API-Key": "secret-key"},
        json={"query": "", "answer": "a", "context": "c"},
    )

    assert response.status_code == 422


def test_evaluate_single_accepts_json_payload_with_api_key(monkeypatch, tmp_path: Path):
    async def _fake_measure(metric, test_case, ignore_errors=False, skip_on_missing_params=False):
        del test_case, ignore_errors, skip_on_missing_params
        metric.score = 0.9
        metric.reason = "ok"

    class _FakeMetric:
        def __init__(self):
            self.score = None
            self.reason = None

    monkeypatch.setattr(
        "deepeval.metrics.indicator.safe_a_measure",
        _fake_measure,
    )
    monkeypatch.setattr(
        "src.evals.metrics.medical.METRIC_SPECS",
        [SimpleNamespace(key="factual_accuracy")],
    )
    monkeypatch.setattr(
        "src.evals.metrics.medical.create_medical_metrics",
        lambda: [_FakeMetric()],
    )
    client = _build_client(monkeypatch, tmp_path, api_keys="secret-key", rate_limit=50)

    response = client.post(
        "/evaluation/evaluate-single",
        headers={"X-API-Key": "secret-key"},
        json={"query": "What is LDL?", "answer": "LDL is cholesterol.", "context": "Guideline text"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "What is LDL?"
    assert payload["answer"] == "LDL is cholesterol."
    assert payload["metrics"]["factual_accuracy"]["score"] == 0.9


def test_documents_endpoint_uses_paginated_store_contract(monkeypatch, tmp_path: Path):
    class _FakeStore:
        def list_documents_paginated(self, *, limit, offset, source_type=None):
            assert limit == 10
            assert offset == 0
            assert source_type == "pdf"
            return {
                "total": 3,
                "items": [
                    {
                        "id": "doc-1",
                        "source": "ref.pdf",
                        "page": 1,
                        "source_type": "pdf",
                        "source_class": "guideline_pdf",
                        "content_type": "paragraph",
                        "content_preview": "preview",
                        "content_length": 7,
                    }
                ],
                "source_type_counts": {"pdf": 3},
                "index_metadata": {"index": "v1"},
            }

        def get_document_by_id(self, doc_id):
            del doc_id
            return None

    client = _build_client(monkeypatch, tmp_path, api_keys="secret-key", rate_limit=50)
    from src.config.context import get_runtime_state

    get_runtime_state().vector_store_initialized = True
    monkeypatch.setattr("src.app.routes.documents.get_vector_store", lambda: _FakeStore())

    response = client.get("/documents?limit=10&offset=0&source_type=pdf", headers={"X-API-Key": "secret-key"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["offset"] == 0
    assert payload["limit"] == 10
    assert payload["items"][0]["id"] == "doc-1"
    assert payload["source_type_counts"] == {"pdf": 3}
