"""Real lifespan/retrieval/SSE failure paths, synthetic SDK streams and storage."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from tests.integration.app import test_lifespan

lifecycle = test_lifespan.lifecycle


@pytest.mark.parametrize("provider", ["qwen", "gemini", "litellm"])
@pytest.mark.parametrize("partial", [False, True])
def test_real_sse_failure_closes_without_replay_or_partial_history(
    lifecycle, monkeypatch, caplog, provider, partial
):
    from src.app.session import _verify_signed_session_id
    from src.infra.llm import gemini_client, litellm_client, qwen_client

    control = lifecycle
    closed = []

    class SDKStream:
        def __init__(self):
            self.sent = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if partial and not self.sent:
                self.sent = True
                if provider == "gemini":
                    return SimpleNamespace(text="prefix ")
                return SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="prefix "))]
                )
            raise RuntimeError("forbidden-upstream-secret")

        async def aclose(self):
            await asyncio.sleep(0)
            closed.append("stream")

        close = aclose

    create = AsyncMock(return_value=SDKStream())
    if provider == "qwen":
        client = qwen_client.QwenClient.__new__(qwen_client.QwenClient)
        sdk = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=AsyncMock()
        )
        sdk.with_options = MagicMock(return_value=sdk)
        client.async_client = sdk
        client.client = SimpleNamespace(close=MagicMock())
    elif provider == "gemini":
        client = gemini_client.GeminiClient.__new__(gemini_client.GeminiClient)
        client.client = SimpleNamespace(
            aio=SimpleNamespace(
                models=SimpleNamespace(generate_content_stream=create), aclose=AsyncMock()
            ),
            close=MagicMock(),
        )
    else:
        client = litellm_client.LiteLLMClient.__new__(litellm_client.LiteLLMClient)
        client._api_key = "synthetic-not-a-key"
        monkeypatch.setattr(litellm_client.litellm, "acompletion", create)
    client.model = "synthetic-model"
    monkeypatch.setattr(control.factory, "get_client", lambda: client)
    app = control.factory.create_app()
    with TestClient(app) as http:
        response = http.post(
            "/chat?include_pipeline=true",
            json={"message": "synthetic question"},
            headers={"X-Request-ID": "synthetic-stream-request"},
        )
        assert response.status_code == 200
        events = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        assert "".join(event["content"] for event in events) == ("prefix " if partial else "")
        terminals = [event for event in events if event["done"]]
        assert len(terminals) == 1
        assert terminals[0]["error_code"] == "chat_stream_failed"
        assert terminals[0]["request_id"] == response.headers["X-Request-ID"]
        assert terminals[0]["sources"]
        assert terminals[0]["pipeline"]["generation"]["model"]
        session = _verify_signed_session_id(response.cookies["chat_session_id"])
        assert app.state.chat_history_store.get_history(session) == []
        assert closed == ["stream"]
        assert create.await_count == 1
    assert "forbidden-upstream-secret" not in response.text
    assert "forbidden-upstream-secret" not in caplog.text
    assert session not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["usecase", "route"])
async def test_early_consumer_close_drains_nested_generator_before_return(lifecycle, boundary):
    from src.app.routes.chat import chat_stream_generator
    from src.app.schemas import ChatRequest
    from src.usecases.chat import stream_chat_message

    control = lifecycle
    app = control.factory.create_app()
    async with app.router.lifespan_context(app):
        store = app.state.chat_history_store
        if boundary == "usecase":
            generator = stream_chat_message(
                llm_client=app.state.llm_client,
                history_store=store,
                message="synthetic question",
                session_id="synthetic-session",
            )
        else:
            request = Request(
                {"type": "http", "method": "POST", "path": "/chat", "headers": [], "app": app}
            )
            request.state.chat_session_id = "synthetic-session"
            request.state.request_id = "synthetic-request"
            generator = chat_stream_generator(
                request, ChatRequest(message="synthetic question"), False
            )
        await anext(generator)
        await generator.aclose()
        assert control.stream_closed == 1
        assert store.get_history("synthetic-session") == []


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["usecase", "route"])
async def test_active_cancellation_closes_without_error_terminal_or_history(
    lifecycle, monkeypatch, boundary
):
    from src.app.routes.chat import chat_stream_generator
    from src.app.schemas import ChatRequest
    from src.usecases.chat import stream_chat_message

    control = lifecycle
    app = control.factory.create_app()
    blocked = asyncio.Event()
    closed = asyncio.Event()
    events = []

    async def generation(**kwargs):
        try:
            yield "prefix"
            blocked.set()
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            closed.set()

    async with app.router.lifespan_context(app):
        monkeypatch.setattr(app.state.llm_client, "a_generate_stream", generation)
        if boundary == "usecase":
            generator = stream_chat_message(
                llm_client=app.state.llm_client,
                history_store=app.state.chat_history_store,
                message="synthetic question",
                session_id="synthetic-session",
            )
        else:
            request = Request(
                {"type": "http", "method": "POST", "path": "/chat", "headers": [], "app": app}
            )
            request.state.chat_session_id = "synthetic-session"
            request.state.request_id = "synthetic-request"
            generator = chat_stream_generator(
                request, ChatRequest(message="synthetic question"), False
            )

        async def consume():
            async for event in generator:
                events.append(event)

        task = asyncio.create_task(consume())
        try:
            await asyncio.wait_for(blocked.wait(), timeout=2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert closed.is_set()
            assert len(events) == 1
            if boundary == "usecase":
                assert events[0] == ("prefix", {"done": False})
            else:
                assert json.loads(events[0][6:])["done"] is False
            assert app.state.chat_history_store.get_history("synthetic-session") == []
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            await generator.aclose()


@pytest.mark.asyncio
async def test_route_does_not_emit_content_or_second_terminal_after_terminal(
    lifecycle, monkeypatch
):
    from src.app.routes import chat
    from src.app.schemas import ChatRequest

    closed = asyncio.Event()

    async def malformed_usecase(**kwargs):
        try:
            yield "", {"done": True, "sources": []}
            yield "must-not-leak-after-terminal", {"done": False}
            yield "", {"done": True, "sources": []}
        finally:
            closed.set()

    monkeypatch.setattr(chat, "stream_chat_message", malformed_usecase)
    app = lifecycle.factory.create_app()
    async with app.router.lifespan_context(app):
        request = Request(
            {"type": "http", "method": "POST", "path": "/chat", "headers": [], "app": app}
        )
        request.state.chat_session_id = "synthetic-session"
        events = [
            event
            async for event in chat.chat_stream_generator(
                request, ChatRequest(message="synthetic question"), False
            )
        ]
        assert len(events) == 1
        assert json.loads(events[0][6:])["done"] is True
        assert closed.is_set()
