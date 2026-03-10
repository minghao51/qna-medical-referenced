from pathlib import Path

from fastapi.testclient import TestClient

from src.app.factory import create_app
from src.app.middleware.auth import APIKeyConfig
from src.app.middleware.rate_limit import RateLimiter
from src.config import settings
from src.infra.storage.file_chat_history_store import FileChatHistoryStore


class DummyLLMClient:
    def generate(self, prompt: str, context: str) -> str:
        return f"answer:{prompt}:{len(context)}"


def _build_client(
    monkeypatch, tmp_path: Path, *, api_keys: str = "secret-key", rate_limit: int = 10
):
    monkeypatch.setattr("src.app.factory.validate_security_configuration", lambda: None)
    monkeypatch.setattr("src.app.factory.initialize_runtime_index", lambda: None)
    monkeypatch.setattr("src.app.middleware.rate_limit.RATE_LIMIT_DB", tmp_path / "rate_limits.db")
    monkeypatch.setattr(settings, "api_keys", api_keys)
    monkeypatch.setattr(settings, "api_keys_json", None)
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
    monkeypatch.setattr(
        "src.app.routes.chat.process_chat_message",
        lambda **kwargs: {"response": "ok", "sources": ["doc"], "pipeline": None},
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
