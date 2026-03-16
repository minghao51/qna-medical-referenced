from pathlib import Path

from fastapi.testclient import TestClient

from src.app.factory import create_app
from src.app.middleware.auth import APIKeyConfig
from src.config import settings
from src.infra.storage.file_chat_history_store import FileChatHistoryStore
from src.rag.formatting import build_chat_sources, build_context_and_sources


class DummyLLMClient:
    def generate(self, prompt: str, context: str) -> str:
        return f"answer:{prompt}:{len(context)}"


def _build_client(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("src.app.factory.validate_security_configuration", lambda: None)
    monkeypatch.setattr("src.app.factory.initialize_runtime_index", lambda: None)
    monkeypatch.setattr(settings, "api_keys", "")
    monkeypatch.setattr(settings, "api_keys_json", None)
    APIKeyConfig.reload()
    app = create_app()
    app.state.llm_client = DummyLLMClient()
    app.state.chat_history_store = FileChatHistoryStore(tmp_path / "chat_history.json")
    return TestClient(app)


def test_build_chat_sources_prefers_logical_name_and_preserves_url():
    results = [
        {
            "source": "healthhub.sg",
            "page": 6,
            "content": "lipid guidance",
            "metadata": {
                "logical_name": "Lipid management",
                "source_url": "https://www.healthhub.sg/lipid-management.pdf",
            },
        }
    ]

    sources = build_chat_sources(results)

    assert len(sources) == 1
    assert sources[0].label == "Lipid management page 6"
    assert sources[0].source == "healthhub.sg"
    assert sources[0].url == "https://www.healthhub.sg/lipid-management.pdf"
    assert sources[0].page == 6


def test_build_context_and_sources_returns_labels_and_structured_sources():
    results = [
        {
            "source": "moh.gov.sg",
            "page": 2,
            "content": "guideline text",
            "metadata": {"logical_name": "MOH lipid guide"},
        }
    ]

    context, labels, chat_sources = build_context_and_sources(results)

    assert "[Source: MOH lipid guide page 2]" in context
    assert labels == ["MOH lipid guide page 2"]
    assert chat_sources[0].label == "MOH lipid guide page 2"
    assert chat_sources[0].source == "moh.gov.sg"


def test_chat_route_returns_structured_sources(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "src.app.routes.chat.process_chat_message",
        lambda **kwargs: {
            "response": "ok",
            "sources": [
                {
                    "label": "HealthHub page 2",
                    "source": "healthhub.sg",
                    "url": "https://www.healthhub.sg/example",
                    "page": 2,
                }
            ],
            "pipeline": None,
        },
    )
    client = _build_client(monkeypatch, tmp_path)

    response = client.post("/chat", json={"message": "hello", "session_id": "s1"})

    assert response.status_code == 200
    body = response.json()
    assert body["sources"][0]["label"] == "HealthHub page 2"
    assert body["sources"][0]["source"] == "healthhub.sg"
    assert body["sources"][0]["url"] == "https://www.healthhub.sg/example"


def test_chat_route_with_pipeline_returns_structured_sources(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "src.app.routes.chat.process_chat_message",
        lambda **kwargs: {
            "response": "ok",
            "sources": [
                {
                    "label": "HealthHub page 2",
                    "source": "healthhub.sg",
                    "url": "https://www.healthhub.sg/example",
                    "page": 2,
                }
            ],
            "pipeline": {
                "retrieval": {
                    "query": "hello",
                    "top_k": 1,
                    "documents": [],
                    "score_weights": {},
                    "timing_ms": 1,
                },
                "context": {
                    "total_chunks": 1,
                    "total_chars": 10,
                    "sources": ["HealthHub page 2"],
                    "preview": "preview",
                },
                "generation": {
                    "model": "demo",
                    "timing_ms": 1,
                    "tokens_estimate": 1,
                },
                "total_time_ms": 2,
            },
        },
    )
    client = _build_client(monkeypatch, tmp_path)

    response = client.post("/chat?include_pipeline=true", json={"message": "hello", "session_id": "s1"})

    assert response.status_code == 200
    body = response.json()
    assert body["sources"][0]["label"] == "HealthHub page 2"
    assert body["pipeline"]["context"]["sources"] == ["HealthHub page 2"]
