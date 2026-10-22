"""SDK cleanup ownership through real lifespan/retrieval/route/ASGI boundaries."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import anyio
import pytest
from fastapi import Request
from fastapi.responses import StreamingResponse

from tests.integration.app import test_lifespan
from tests.unit.infra import test_stream_cleanup_cancellation, test_stream_contract

lifecycle = test_lifespan.lifecycle
provider = test_stream_contract.provider


@pytest.fixture(params=[False, True], ids=["close-ok", "close-fails"])
def streaming(request, lifecycle, provider, monkeypatch):
    class SDKStream(test_stream_cleanup_cancellation.BlockedCloseStream):
        sent = False

        async def __anext__(self):
            if not self.sent:
                self.sent = True
                return provider.chunk("prefix")
            return await super().__anext__()

    body = SDKStream(close_error=request.param)
    provider.create.return_value = body
    client = provider.client
    shared_close = AsyncMock()
    if provider.module.__name__.endswith("qwen_client"):
        client.async_client.close = shared_close
        client.client = SimpleNamespace(close=MagicMock())
    elif provider.module.__name__.endswith("gemini_client"):
        client.client.aio.aclose = shared_close
        client.client.close = MagicMock()
    monkeypatch.setattr(lifecycle.factory, "get_client", lambda: client)
    app = lifecycle.factory.create_app()
    return SimpleNamespace(app=app, body=body, shared_close=shared_close, provider=provider)


def assert_session_owned(store):
    from src.core.exceptions import AppError

    with pytest.raises(AppError) as busy:
        with store.turn("synthetic-session"):
            pass
    assert busy.value.code == "chat_session_busy"
    with pytest.raises(AppError) as busy:
        store.clear_history("synthetic-session")
    assert busy.value.code == "chat_session_busy"
    with store.turn("unrelated-session"):
        pass
    assert store.get_history("synthetic-session") == []


def request_for(app):
    request = Request(
        {"type": "http", "method": "POST", "path": "/chat", "headers": [], "app": app}
    )
    request.state.chat_session_id = "synthetic-session"
    request.state.request_id = "synthetic-request"
    return request


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["usecase", "route"])
@pytest.mark.parametrize("cancellation", ["asyncio", "anyio"])
async def test_session_is_owned_until_cancelled_public_sdk_cleanup_settles(
    streaming, boundary, cancellation, caplog
):
    from src.app.routes.chat import chat_stream_generator
    from src.app.schemas import ChatRequest
    from src.usecases.chat import stream_chat_message

    app, body = streaming.app, streaming.body
    events, cancelled = [], []
    done = asyncio.Event()
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
            generator = chat_stream_generator(
                request_for(app), ChatRequest(message="synthetic question"), False
            )

        async def consume():
            try:
                async for event in generator:
                    events.append(event)
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
            finally:
                done.set()

        if cancellation == "asyncio":
            task = asyncio.create_task(consume())
            try:
                await asyncio.wait_for(body.read_started.wait(), 2)
                task.cancel()
                await asyncio.wait_for(body.close_started.wait(), 2)
                task.cancel()
                for _ in range(3):
                    await asyncio.sleep(0)
                assert not task.done()
                assert_session_owned(store)
                streaming.shared_close.assert_not_called()
                body.release_close.set()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 2)
            finally:
                body.release_close.set()
                if not task.done():
                    task.cancel()
                await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)
                await generator.aclose()
        else:
            async with anyio.create_task_group() as group:
                group.start_soon(consume)
                await asyncio.wait_for(body.read_started.wait(), 2)
                group.cancel_scope.cancel()
                with anyio.CancelScope(shield=True):
                    try:
                        await asyncio.wait_for(body.close_started.wait(), 2)
                        for _ in range(3):
                            await asyncio.sleep(0)
                        assert not done.is_set()
                        assert_session_owned(store)
                        streaming.shared_close.assert_not_called()
                    finally:
                        body.release_close.set()
                    await asyncio.wait_for(done.wait(), 2)
            await generator.aclose()
        assert cancelled == [True]
        assert body.closed.is_set()
        assert body.close_calls == 1
        assert streaming.provider.create.await_count == 1
        assert len(events) == 1
        if boundary == "usecase":
            assert events == [("prefix", {"done": False})]
        else:
            assert json.loads(events[0][6:]) == {"content": "prefix", "done": False}
        assert store.get_history("synthetic-session") == []
        with store.turn("synthetic-session"):
            pass
        store.clear_history("synthetic-session")
        assert "forbidden-close-detail" not in caplog.text


@pytest.mark.asyncio
async def test_real_starlette_disconnect_waits_for_sdk_cleanup_without_terminal_or_history(
    streaming, caplog
):
    from src.app.routes.chat import chat_stream_generator
    from src.app.schemas import ChatRequest

    app, body = streaming.app, streaming.body
    disconnect = asyncio.Event()
    sent = []

    async def receive():
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(event):
        sent.append(event)

    async with app.router.lifespan_context(app):
        response = StreamingResponse(
            chat_stream_generator(
                request_for(app), ChatRequest(message="synthetic question"), False
            ),
            media_type="text/event-stream",
        )
        # ASGI2.0 spec selects Starlette's actual AnyIO disconnect listener.
        task = asyncio.create_task(
            response({"type": "http", "asgi": {"spec_version": "2.0"}}, receive, send)
        )
        try:
            await asyncio.wait_for(body.read_started.wait(), 2)
            disconnect.set()
            await asyncio.wait_for(body.close_started.wait(), 2)
            for _ in range(3):
                await asyncio.sleep(0)
            assert not task.done()
            assert_session_owned(app.state.chat_history_store)
            streaming.shared_close.assert_not_called()
            body.release_close.set()
            await asyncio.wait_for(task, 2)
            assert body.closed.is_set()
            assert body.close_calls == 1
            assert streaming.provider.create.await_count == 1
            events = [
                json.loads(line[6:])
                for event in sent
                for line in event.get("body", b"").decode().splitlines()
                if line.startswith("data: ")
            ]
            assert events == [{"content": "prefix", "done": False}]
            store = app.state.chat_history_store
            assert store.get_history("synthetic-session") == []
            with store.turn("synthetic-session"):
                pass
            assert "forbidden-close-detail" not in caplog.text
        finally:
            disconnect.set()
            body.release_close.set()
            if not task.done():
                task.cancel()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)
