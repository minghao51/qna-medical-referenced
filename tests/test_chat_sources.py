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
    monkeypatch.setattr(settings, "chat_session_cookie_name", "chat_session_id")
    monkeypatch.setattr(settings, "chat_session_cookie_max_age_seconds", 3600)
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
    assert sources[0].canonical_label == "Lipid management"
    assert sources[0].display_label == "Lipid management page 6"
    assert sources[0].label == "Lipid management page 6"
    assert sources[0].source == "healthhub.sg"
    assert sources[0].source_url == "https://www.healthhub.sg/lipid-management.pdf"
    assert sources[0].url == "https://www.healthhub.sg/lipid-management.pdf"
    assert sources[0].source_type == "other"
    assert sources[0].source_class == "unknown"
    assert sources[0].domain == "www.healthhub.sg"
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
    assert chat_sources[0].display_label == "MOH lipid guide page 2"
    assert chat_sources[0].canonical_label == "MOH lipid guide"
    assert chat_sources[0].source == "moh.gov.sg"


def test_build_chat_sources_falls_back_to_filename_instead_of_unknown():
    results = [
        {
            "source": "lipid_management_v2.pdf",
            "content": "guideline text",
            "metadata": {"source_type": "pdf", "source_class": "guideline_pdf"},
        }
    ]

    source = build_chat_sources(results)[0]

    assert source.canonical_label == "lipid management v2"
    assert source.display_label == "lipid management v2"
    assert source.source_type == "pdf"
    assert source.source_class == "guideline_pdf"
    assert source.label != "unknown"


def test_chat_route_returns_structured_sources(monkeypatch, tmp_path: Path):
    async def mock_stream_chat_message(**kwargs):
        yield (
            "ok",
            {
                "done": True,
                "sources": [
                    {
                        "canonical_label": "HealthHub",
                        "display_label": "HealthHub page 2",
                        "source_url": "https://www.healthhub.sg/example",
                        "source_type": "html",
                        "source_class": "guideline_html",
                        "domain": "www.healthhub.sg",
                        "domain_type": "unknown",
                        "label": "HealthHub page 2",
                        "source": "healthhub.sg",
                        "url": "https://www.healthhub.sg/example",
                        "page": 2,
                    }
                ],
                "pipeline": None,
            },
        )

    monkeypatch.setattr(
        "src.app.routes.chat.stream_chat_message",
        mock_stream_chat_message,
    )
    client = _build_client(monkeypatch, tmp_path)

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.cookies.get("chat_session_id")
    # Parse SSE stream
    content = response.text
    events = [line for line in content.split("\n") if line.startswith("data: ")]
    assert len(events) == 2
    import json

    # First event has content, second has metadata
    first_event = json.loads(events[0][6:])
    assert first_event["content"] == "ok"
    assert first_event["done"] is False
    # Second event has sources and done: true
    final_event = json.loads(events[1][6:])
    assert final_event["done"] is True
    assert final_event["sources"][0]["canonical_label"] == "HealthHub"
    assert final_event["sources"][0]["display_label"] == "HealthHub page 2"
    assert final_event["sources"][0]["label"] == "HealthHub page 2"
    assert final_event["sources"][0]["source"] == "healthhub.sg"
    assert final_event["sources"][0]["url"] == "https://www.healthhub.sg/example"
    assert final_event["sources"][0]["source_url"] == "https://www.healthhub.sg/example"
    assert final_event["sources"][0]["source_type"] == "html"


def test_chat_route_with_pipeline_returns_structured_sources(monkeypatch, tmp_path: Path):
    async def mock_stream_chat_message(**kwargs):
        yield (
            "ok",
            {
                "done": True,
                "sources": [
                    {
                        "canonical_label": "HealthHub",
                        "display_label": "HealthHub page 2",
                        "source_url": "https://www.healthhub.sg/example",
                        "source_type": "html",
                        "source_class": "guideline_html",
                        "domain": "www.healthhub.sg",
                        "domain_type": "unknown",
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

    monkeypatch.setattr(
        "src.app.routes.chat.stream_chat_message",
        mock_stream_chat_message,
    )
    client = _build_client(monkeypatch, tmp_path)

    response = client.post("/chat?include_pipeline=true", json={"message": "hello"})

    assert response.status_code == 200
    # Parse SSE stream
    content = response.text
    events = [line for line in content.split("\n") if line.startswith("data: ")]
    assert len(events) == 2
    import json

    # First event has content, second has metadata
    first_event = json.loads(events[0][6:])
    assert first_event["content"] == "ok"
    assert first_event["done"] is False
    # Second event has sources, pipeline, and done: true
    final_event = json.loads(events[1][6:])
    assert final_event["done"] is True
    assert final_event["sources"][0]["label"] == "HealthHub page 2"
    assert final_event["pipeline"]["context"]["sources"] == ["HealthHub page 2"]


def test_history_routes_ignore_legacy_session_id_and_use_cookie_session(
    monkeypatch, tmp_path: Path
):
    client = _build_client(monkeypatch, tmp_path)
    store = client.app.state.chat_history_store

    response = client.get("/history/not-the-real-session")
    cookie_session_id = response.cookies.get("chat_session_id")
    assert cookie_session_id

    store.save_message(cookie_session_id, "user", "hello")
    fetched = client.get("/history/arbitrary-session-id")

    assert fetched.status_code == 200
    assert fetched.json()["history"][0]["role"] == "user"
    assert fetched.json()["history"][0]["content"] == "hello"
    assert fetched.json()["history"][0]["timestamp"]
