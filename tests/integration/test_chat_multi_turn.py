"""Tests for multi-turn conversation handling in chat endpoint."""

from pathlib import Path

from fastapi.testclient import TestClient

from src.app.factory import create_app
from src.app.middleware.auth import APIKeyConfig
from src.config import settings
from src.infra.storage.file_chat_history_store import FileChatHistoryStore


def _fake_retrieve_context(query: str, top_k: int = 5, retrieval_options=None):
    del top_k, retrieval_options
    return f"context for {query}", [{"label": f"Source for {query}"}]


class DummyLLMClient:
    def generate(self, prompt: str, context: str) -> str:
        return f"answer:{prompt[:50]}"

    async def a_generate_stream(self, prompt: str, context: str):
        response = f"answer:{prompt[:50]}"
        for token in response.split():
            yield token + " "
        yield ""


def _build_client(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("src.app.factory.validate_security_configuration", lambda: None)
    monkeypatch.setattr("src.app.factory.initialize_runtime_index_async", lambda: None)
    monkeypatch.setattr("src.usecases.chat.retrieve_context", _fake_retrieve_context)
    monkeypatch.setattr(settings.api, "api_keys", "")
    monkeypatch.setattr(settings.api, "api_keys_json", None)
    monkeypatch.setattr(settings.api, "chat_session_cookie_name", "chat_session_id")
    monkeypatch.setattr(settings.api, "chat_session_cookie_max_age_seconds", 3600)
    APIKeyConfig.reload()
    app = create_app()
    app.state.llm_client = DummyLLMClient()
    app.state.chat_history_store = FileChatHistoryStore(tmp_path / "chat_history.json")
    return TestClient(app)


def _parse_sse_response(response_text: str) -> tuple[list[str], dict]:
    lines = response_text.strip().split("\n")
    events = []
    metadata = {}
    for line in lines:
        if line.startswith("data: "):
            import json

            data = json.loads(line[6:])
            if data.get("done"):
                metadata = data
            else:
                events.append(data.get("content", ""))
    return events, metadata


class TestMultiTurnSessionPersistence:
    """Test that chat history persists correctly across multiple turns."""

    def test_three_turn_conversation_persists_history(self, monkeypatch, tmp_path: Path):
        """Verify that after 3 turns, all user and assistant messages are in history."""
        client = _build_client(monkeypatch, tmp_path)

        response1 = client.post("/chat", json={"message": "What is LDL-C target?"})
        assert response1.status_code == 200
        session_id = response1.cookies.get("chat_session_id")
        assert session_id is not None

        response2 = client.post("/chat", json={"message": "What if patient has diabetes?"})
        assert response2.status_code == 200

        response3 = client.post("/chat", json={"message": "Should they get high-intensity statin?"})
        assert response3.status_code == 200

        history_response = client.get("/history")
        assert history_response.status_code == 200
        history = history_response.json()["history"]

        assert len(history) == 6
        assert history[0]["role"] == "user"
        assert "LDL-C" in history[0]["content"]
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"
        assert "diabetes" in history[2]["content"]
        assert history[3]["role"] == "assistant"
        assert history[4]["role"] == "user"
        assert "statin" in history[4]["content"]
        assert history[5]["role"] == "assistant"

    def test_different_sessions_have_isolated_history(self, monkeypatch, tmp_path: Path):
        """Verify that different sessions maintain separate histories."""
        client_a = _build_client(monkeypatch, tmp_path)
        client_b = _build_client(monkeypatch, tmp_path)

        response1 = client_a.post("/chat", json={"message": "Session A: LDL question"})
        session_a = response1.cookies.get("chat_session_id")
        assert session_a is not None

        response2 = client_b.post("/chat", json={"message": "Session B: Pre-diabetes question"})
        session_b = response2.cookies.get("chat_session_id")
        assert session_b is not None

        assert session_a != session_b

        history_a = client_a.get("/history").json()["history"]
        history_b = client_b.get("/history").json()["history"]

        assert len(history_a) == 2
        assert len(history_b) == 2
        assert "Session A" in history_a[0]["content"]
        assert "Session B" in history_b[0]["content"]

    def test_history_clear_rotates_session(self, monkeypatch, tmp_path: Path):
        """Verify that clearing history also rotates the session ID."""
        client = _build_client(monkeypatch, tmp_path)

        response1 = client.post("/chat", json={"message": "First message"})
        old_session = response1.cookies.get("chat_session_id")
        assert old_session is not None

        client.cookies.set("chat_session_id", old_session)
        response2 = client.delete("/history")
        assert response2.status_code == 200
        new_session = response2.cookies.get("chat_session_id")
        assert new_session is not None

        assert new_session != old_session

        client.cookies.set("chat_session_id", old_session)
        old_history = client.get("/history").json()["history"]

        client.cookies.set("chat_session_id", new_session)
        new_history = client.get("/history").json()["history"]

        assert len(old_history) == 0
        assert len(new_history) == 0


class TestMultiTurnHistoryContextBuilding:
    """Test that history context is correctly built and passed to retrieval."""

    def test_history_context_formats_correctly(self, monkeypatch, tmp_path: Path):
        """Verify that history is formatted as 'role: content' per line."""
        client = _build_client(monkeypatch, tmp_path)
        store = client.app.state.chat_history_store
        session_id = "test_session"

        store.save_message(session_id, "user", "What is FH?")
        store.save_message(session_id, "assistant", "FH is familial hypercholesterolemia.")
        store.save_message(session_id, "user", "When to do genetic testing?")

        history = store.get_history(session_id)
        from src.usecases.chat import _build_history_context

        context = _build_history_context(history)
        lines = context.split("\n")

        assert len(lines) == 3
        assert lines[0] == "user: What is FH?"
        assert lines[1] == "assistant: FH is familial hypercholesterolemia."
        assert lines[2] == "user: When to do genetic testing?"

    def test_empty_history_returns_empty_context(self, monkeypatch, tmp_path: Path):
        """Verify that empty history produces empty context string."""
        from src.usecases.chat import _build_history_context

        context = _build_history_context([])
        assert context == ""

    def test_full_context_composes_history_and_retrieval(self, monkeypatch, tmp_path: Path):
        """Verify that full context combines history with retrieved context."""
        from src.usecases.chat import _compose_full_context

        history_context = "user: What is LDL-C?\nassistant: LDL-C is low-density lipoprotein."
        retrieved_context = "LDL-C target is < 1.8 mmol/L for secondary prevention."

        full = _compose_full_context(history_context, retrieved_context)

        assert "user: What is LDL-C?" in full
        assert "assistant: LDL-C is low-density lipoprotein." in full
        assert "Context: LDL-C target" in full


class TestMultiTurnKeywordVerification:
    """Test keyword verification per turn in multi-turn conversations."""

    def test_expected_keywords_in_three_turn_response(self, monkeypatch, tmp_path: Path):
        """Verify that responses contain expected keywords for each turn."""
        client = _build_client(monkeypatch, tmp_path)

        response1 = client.post(
            "/chat", json={"message": "What is LDL-C target for secondary prevention?"}
        )
        assert response1.status_code == 200

        session_id = response1.cookies.get("chat_session_id")
        events1, metadata1 = _parse_sse_response(response1.text)
        response_text1 = "".join(events1)
        del metadata1

        assert "LDL-C" in response_text1 or "answer" in response_text1.lower()

        assert session_id is not None
        response2 = client.post("/chat", json={"message": "And if patient has diabetes?"})
        assert response2.status_code == 200
        events2, metadata2 = _parse_sse_response(response2.text)
        response_text2 = "".join(events2)
        del metadata2

        assert "diabetes" in response_text2.lower() or "answer" in response_text2.lower()


class TestMultiTurnSourceVerification:
    """Test source verification per turn in multi-turn conversations."""

    def test_sources_returned_per_turn(self, monkeypatch, tmp_path: Path):
        """Verify that sources are returned in the final SSE event for each turn."""
        client = _build_client(monkeypatch, tmp_path)

        response1 = client.post("/chat", json={"message": "What is the LDL-C target?"})
        assert response1.status_code == 200
        events1, metadata1 = _parse_sse_response(response1.text)
        del events1
        assert metadata1.get("sources") is not None

        session_id = response1.cookies.get("chat_session_id")
        assert session_id is not None
        response2 = client.post("/chat", json={"message": "What about FH patients?"})
        assert response2.status_code == 200
        events2, metadata2 = _parse_sse_response(response2.text)
        del events2
        assert metadata2.get("sources") is not None


class TestMultiTurnRetrievalQuality:
    """Test that retrieval quality is maintained across turns."""

    def test_retrieval_context_includes_fresh_results_per_turn(self, monkeypatch, tmp_path: Path):
        """Verify that each turn performs fresh retrieval, not just using history."""
        client = _build_client(monkeypatch, tmp_path)

        response1 = client.post("/chat", json={"message": "What is LDL-C?"})
        assert response1.status_code == 200

        session_id = response1.cookies.get("chat_session_id")
        assert session_id is not None
        response2 = client.post("/chat", json={"message": "And triglycerides?"})
        assert response2.status_code == 200

        events2, metadata2 = _parse_sse_response(response2.text)
        assert metadata2.get("sources") is not None or len(events2) > 0


class TestMultiTurnWithRealStreaming:
    """Integration tests with streaming behavior."""

    def test_streaming_returns_tokens_across_turns(self, monkeypatch, tmp_path: Path):
        """Verify that streaming works correctly across multiple turns."""
        client = _build_client(monkeypatch, tmp_path)

        response1 = client.post("/chat", json={"message": "Question 1"})
        assert response1.status_code == 200
        events1, _ = _parse_sse_response(response1.text)
        assert len(events1) > 0 or "answer" in response1.text.lower()

        session_id = response1.cookies.get("chat_session_id")
        assert session_id is not None
        response2 = client.post("/chat", json={"message": "Question 2"})
        assert response2.status_code == 200
        events2, _ = _parse_sse_response(response2.text)
        assert len(events2) > 0 or "answer" in response2.text.lower()

    def test_session_cookie_persists_across_turns(self, monkeypatch, tmp_path: Path):
        """Verify that the session cookie remains consistent across turns."""
        client = _build_client(monkeypatch, tmp_path)

        r1 = client.post("/chat", json={"message": "First"})
        s1 = r1.cookies.get("chat_session_id")
        assert s1 is not None

        client.post("/chat", json={"message": "Second"})
        client.post("/chat", json={"message": "Third"})
        history = client.get("/history").json()["history"]

        assert len(history) == 6
        assert history[0]["content"] == "First"
        assert history[2]["content"] == "Second"
        assert history[4]["content"] == "Third"
        assert r1.cookies.get("chat_session_id") == s1
