"""ASGI response ownership and app shutdown drain through public boundaries."""

import asyncio
import json

import pytest
from fastapi import Request

from tests.integration.app import test_lifespan

lifecycle = test_lifespan.lifecycle


def _scope(*, body: bytes = b"", path: str = "/chat"):
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }


async def _request(app, *, disconnect: asyncio.Event | None = None):
    body = json.dumps({"message": "synthetic question"}).encode()
    first = True
    sent = []

    async def receive():
        nonlocal first
        if first:
            first = False
            return {"type": "http.request", "body": body, "more_body": False}
        if disconnect is None:
            await asyncio.Event().wait()
        else:
            await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(event):
        sent.append(event)

    await app(_scope(body=body), receive, send)
    return sent


@pytest.mark.asyncio
async def test_shutdown_rejects_new_requests_and_waits_for_active_stream(
    lifecycle, monkeypatch, caplog
):
    control = lifecycle
    from src.config.settings import TelemetryConfig

    monkeypatch.setattr(control.settings, "telemetry", TelemetryConfig(mode="local"))
    app = control.factory.create_app()
    generation_entered, release_generation = asyncio.Event(), asyncio.Event()
    close_calls = []

    class BlockingClient:
        model = "synthetic-model"

        async def a_generate_stream(self, **kwargs):
            try:
                generation_entered.set()
                yield "prefix"
                await release_generation.wait()
                yield "answer"
            finally:
                control.stream_closed += 1

        async def aclose(self):
            close_calls.append(True)

    blocking_client = BlockingClient()
    # Keep the synthetic retrieval/store setup from the shared lifespan fixture.
    from src.app import factory

    monkeypatch.setattr(factory, "get_client", lambda: blocking_client)
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    request_task = asyncio.create_task(_request(app))
    shutdown_task = None
    try:
        await asyncio.wait_for(generation_entered.wait(), 2)
        shutdown_task = asyncio.create_task(lifespan.__aexit__(None, None, None))
        for _ in range(5):
            await asyncio.sleep(0)
        assert not shutdown_task.done()
        assert close_calls == []
        assert app.state.llm_client is blocking_client
        assert app.state.request_lifecycle._closing is True

        rejected = await _request(app)
        assert rejected[0]["status"] == 503
        request_id = dict(rejected[0]["headers"])[b"x-request-id"].decode()
        assert len(request_id) == 36
        assert request_id in caplog.text
        spans = app.state.telemetry.finished_spans
        assert any(
            span.attributes.get("telemetry.request_id") == request_id
            and span.attributes.get("telemetry.error_code") == "shutdown"
            for span in spans
        )
        assert not request_task.done()

        release_generation.set()
        await asyncio.wait_for(request_task, 2)
        await asyncio.wait_for(shutdown_task, 2)
        assert close_calls == [True]
        assert control.stream_closed == 1
        assert app.state.llm_client is None
    finally:
        release_generation.set()
        if not request_task.done():
            request_task.cancel()
        if shutdown_task is None:
            shutdown_task = asyncio.create_task(lifespan.__aexit__(None, None, None))
        await asyncio.gather(request_task, shutdown_task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["response-start", "stream-send"])
async def test_stream_response_closes_iterator_on_asgi_send_failure(lifecycle, failure_point):
    from src.app.routes.chat import chat
    from src.app.schemas import ChatRequest

    control = lifecycle
    app = control.factory.create_app()
    async with app.router.lifespan_context(app):
        request = Request(
            {"type": "http", "method": "POST", "path": "/chat", "headers": [], "app": app}
        )
        request.state.chat_session_id = "synthetic-session"
        request.state.request_id = "synthetic-request"
        response = await chat(request, ChatRequest(message="synthetic question"), False)
        disconnect = asyncio.Event()

        async def receive():
            await disconnect.wait()
            return {"type": "http.disconnect"}

        async def send(event):
            if failure_point == "response-start" and event["type"] == "http.response.start":
                raise OSError("synthetic send failure")
            if failure_point == "stream-send" and event["type"] == "http.response.body":
                if event.get("body"):
                    raise OSError("synthetic send failure")

        with pytest.raises(OSError, match="synthetic send failure"):
            await response(_scope(), receive, send)
        assert control.stream_closed == int(failure_point == "stream-send")
        assert app.state.chat_history_store.get_history("synthetic-session") == []
        with app.state.chat_history_store.turn("synthetic-session"):
            pass


@pytest.mark.asyncio
async def test_asgi_disconnect_closes_active_chat_iterator(lifecycle, monkeypatch):
    from src.app.routes.chat import chat
    from src.app.schemas import ChatRequest

    control = lifecycle
    app = control.factory.create_app()
    disconnect, body_sent, release_generation = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async with app.router.lifespan_context(app):
        request = Request(
            {"type": "http", "method": "POST", "path": "/chat", "headers": [], "app": app}
        )
        request.state.chat_session_id = "synthetic-session"
        request.state.request_id = "synthetic-request"

        async def blocked_stream(**kwargs):
            try:
                yield "prefix"
                await release_generation.wait()
                yield "unreachable"
            finally:
                control.stream_closed += 1

        monkeypatch.setattr(app.state.llm_client, "a_generate_stream", blocked_stream)
        response = await chat(request, ChatRequest(message="synthetic question"), False)

        async def receive():
            await disconnect.wait()
            return {"type": "http.disconnect"}

        async def send(event):
            if event["type"] == "http.response.body" and event.get("body"):
                body_sent.set()

        task = asyncio.create_task(response(_scope(), receive, send))
        try:
            await asyncio.wait_for(body_sent.wait(), 2)
            disconnect.set()
            await asyncio.wait_for(task, 2)
            assert control.stream_closed == 1
            assert app.state.chat_history_store.get_history("synthetic-session") == []
            with app.state.chat_history_store.turn("synthetic-session"):
                pass
        finally:
            disconnect.set()
            release_generation.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
