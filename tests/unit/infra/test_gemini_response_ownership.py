"""Public HTTPX response handles release per-request Gemini streams."""

import asyncio
import json
from contextlib import aclosing
from types import SimpleNamespace

import anyio
import httpx
import pytest
from pydantic import BaseModel

from src.infra.llm import gemini_client


class Answer(BaseModel):
    answer: str


def _build_client(monkeypatch, *, block_response_close=False):
    control = SimpleNamespace(
        responses=[],
        close_calls=0,
        clients=[],
        events=[],
        close_started=asyncio.Event(),
        release_close=asyncio.Event(),
        block_response_close=block_response_close,
        cancel_scope=None,
        fail_first_stream=False,
        stream_requests=0,
        retry_closed_states=[],
    )
    if not block_response_close:
        control.release_close.set()
    real_async_client = httpx.AsyncClient

    class BodyStream(httpx.AsyncByteStream):
        def __init__(self, body: bytes):
            self.body = body

        async def __aiter__(self):
            yield self.body

        async def aclose(self):
            return None

    async def handle(request):
        is_stream = ":streamGenerateContent" in str(request.url)
        if is_stream:
            control.stream_requests += 1
            if control.stream_requests > 1:
                control.retry_closed_states.append(
                    all(response.is_closed for response in control.responses)
                )
        payload = json.loads(request.content)
        structured = (
            payload.get("generationConfig", {}).get("responseMimeType") == "application/json"
        )
        text = '{"answer":"synthetic answer"}' if structured else "synthetic answer"
        chunk = {
            "candidates": [
                {"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}
            ]
        }
        body = (
            f"data: {json.dumps(chunk)}\n\n".encode() if is_stream else json.dumps(chunk).encode()
        )
        status = (
            503 if is_stream and control.fail_first_stream and control.stream_requests == 1 else 200
        )
        return httpx.Response(
            status,
            headers={"content-type": "text/event-stream" if is_stream else "application/json"},
            stream=BodyStream(body),
        )

    def build_async_client(**kwargs):
        original_hooks = kwargs.get("event_hooks", {})

        async def observe_response(response):
            original_close = response.aclose

            async def tracked_close():
                control.close_calls += 1
                control.events.append("response-close-started")
                if control.block_response_close:
                    control.close_started.set()
                    await control.release_close.wait()
                await original_close()
                control.events.append("response-closed")

            response.aclose = tracked_close
            control.responses.append(response)
            for hook in original_hooks.get("response", []):
                await hook(response)

        client = real_async_client(
            **{
                **kwargs,
                "event_hooks": {"response": [observe_response]},
                "transport": httpx.MockTransport(handle),
            }
        )
        control.clients.append(client)
        return client

    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "false")
    monkeypatch.setattr(
        gemini_client,
        "settings",
        SimpleNamespace(
            llm=SimpleNamespace(
                gemini_api_key=SimpleNamespace(get_secret_value=lambda: "synthetic-not-a-key"),
                gemini_model_name="synthetic-model",
            ),
            retry=SimpleNamespace(max_retries=1, retry_delay=0.0),
        ),
    )
    monkeypatch.setattr(gemini_client.httpx, "AsyncClient", build_async_client)
    return gemini_client.GeminiClient(), control


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["text", "structured", "early-stream-close", "concurrent"])
async def test_gemini_closes_each_httpx_response_without_closing_shared_pool(
    monkeypatch, operation
):
    client, control = _build_client(monkeypatch)
    try:
        if operation == "text":
            assert await client.a_generate("synthetic prompt") == "synthetic answer"
        elif operation == "structured":
            assert await client.a_generate_structured("synthetic prompt", Answer) == Answer(
                answer="synthetic answer"
            )
        elif operation == "early-stream-close":
            stream = client.a_generate_stream("synthetic prompt")
            assert await anext(stream) == "synthetic answer"
            await stream.aclose()
        else:
            assert await asyncio.gather(
                client.a_generate("first synthetic prompt"),
                client.a_generate("second synthetic prompt"),
            ) == ["synthetic answer", "synthetic answer"]

        expected_responses = 2 if operation == "concurrent" else 1
        assert len(control.responses) == expected_responses
        assert all(response.is_closed for response in control.responses)
        assert control.close_calls >= expected_responses
        assert not control.clients[0].is_closed

        # Each request has its own response bag and leaves the shared pool reusable.
        if operation != "concurrent" and operation != "early-stream-close":
            assert await client.a_generate("second synthetic prompt") == "synthetic answer"
            assert len(control.responses) == 2
            assert all(response.is_closed for response in control.responses)
    finally:
        await client.aclose()
    assert control.clients[0].is_closed


@pytest.mark.asyncio
async def test_gemini_stream_closes_failed_attempt_response_before_retry(monkeypatch):
    client, control = _build_client(monkeypatch)
    control.fail_first_stream = True
    gemini_client.settings.retry.max_retries = 2
    try:
        stream = client.a_generate_stream("synthetic prompt")
        assert await anext(stream) == "synthetic answer"
        await stream.aclose()

        assert control.stream_requests == 2
        assert control.retry_closed_states == [True]
        assert len(control.responses) == 2
        assert all(response.is_closed for response in control.responses)
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("close_style", ["ensure-future", "aclosing"])
async def test_gemini_stream_response_cleanup_is_safe_for_public_close_contexts(
    monkeypatch, close_style
):
    client, control = _build_client(monkeypatch)
    try:
        if close_style == "ensure-future":
            stream = client.a_generate_stream("synthetic prompt")
            assert await anext(stream) == "synthetic answer"
            await asyncio.ensure_future(stream.aclose())
        else:
            async with aclosing(client.a_generate_stream("synthetic prompt")) as stream:
                assert await anext(stream) == "synthetic answer"

        control.events.append("request-release")
        assert len(control.responses) == 1
        assert control.responses[0].is_closed
        assert control.clients[0].is_closed is False
        assert client._pending_httpx_responses.get() is None
        assert control.events.index("response-closed") < control.events.index("request-release")
    finally:
        await client.aclose()
    assert control.clients[0].is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("cancellation_mode", ["repeated-task-cancel", "anyio-cancel-scope"])
async def test_gemini_response_cleanup_drains_before_request_and_pool_release(
    monkeypatch, cancellation_mode
):
    client, control = _build_client(monkeypatch, block_response_close=True)
    stream = client.a_generate_stream("synthetic prompt")
    assert await anext(stream) == "synthetic answer"

    async def close_stream():
        if cancellation_mode == "anyio-cancel-scope":
            with anyio.CancelScope() as scope:
                control.cancel_scope = scope
                await stream.aclose()
        else:
            await stream.aclose()

    close_task = asyncio.create_task(close_stream())
    try:
        await asyncio.wait_for(control.close_started.wait(), timeout=5)
        assert not control.responses[0].is_closed
        assert not control.clients[0].is_closed

        if cancellation_mode == "repeated-task-cancel":
            close_task.cancel()
            await asyncio.sleep(0)
            close_task.cancel()
        else:
            control.cancel_scope.cancel()
            await asyncio.sleep(0)
            control.cancel_scope.cancel()
        await asyncio.sleep(0)
        assert not close_task.done()
        assert not control.clients[0].is_closed

        control.release_close.set()
        if cancellation_mode == "repeated-task-cancel":
            with pytest.raises(asyncio.CancelledError):
                await close_task
        else:
            await close_task

        assert control.responses[0].is_closed
        control.events.append("request-release")
        assert control.events.index("response-closed") < control.events.index("request-release")
        assert not control.clients[0].is_closed

        control.events.append("shared-pool-close")
        await client.aclose()
        assert control.events.index("response-closed") < control.events.index("shared-pool-close")
        assert control.clients[0].is_closed
    finally:
        control.release_close.set()
        if not close_task.done():
            close_task.cancel()
            try:
                await close_task
            except asyncio.CancelledError:
                pass
        if not control.clients[0].is_closed:
            await client.aclose()
