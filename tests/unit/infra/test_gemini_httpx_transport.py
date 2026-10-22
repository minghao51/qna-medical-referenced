"""Actual application constructor + installed SDK, in-memory transport, no sockets."""

import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
import httpx
import pytest
import pytest_asyncio
from google.genai import errors
from pydantic import BaseModel

from src.infra.llm import gemini_client

METHODS = ["a_generate", "a_generate_structured", "a_generate_stream"]


class Answer(BaseModel):
    answer: str


@pytest_asyncio.fixture
async def native_constructor(monkeypatch):
    real_async_client = httpx.AsyncClient
    real_sdk = gemini_client.genai.Client
    control = SimpleNamespace(
        error=None,
        calls=[],
        created=[],
        sdk=[],
        options=[],
        client_kwargs=[],
        transport_closes=[],
        owned_closers=[],
        sdk_closers=[],
        retry=SimpleNamespace(max_retries=3, retry_delay=0.0),
    )
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "false")
    monkeypatch.setattr(
        gemini_client,
        "settings",
        SimpleNamespace(
            llm=SimpleNamespace(
                gemini_api_key=SimpleNamespace(get_secret_value=lambda: "synthetic-not-a-key"),
                gemini_model_name="synthetic-default-model",
            ),
            retry=control.retry,
        ),
    )

    async def handler(request):
        control.calls.append(request)
        if control.error == "connection":
            raise httpx.ConnectError("forbidden-connection-detail", request=request)
        if control.error == "timeout":
            raise httpx.ReadTimeout("forbidden-timeout-detail", request=request)
        if control.error == "server":
            return httpx.Response(
                500,
                json={
                    "error": {
                        "code": 500,
                        "message": "forbidden-server-detail",
                        "status": "INTERNAL",
                    }
                },
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
        if ":streamGenerateContent" in str(request.url):
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=f"data: {json.dumps(chunk)}\n\n".encode(),
            )
        return httpx.Response(200, json=chunk)

    def build_async_client(**kwargs):
        control.client_kwargs.append(dict(kwargs))
        transport = httpx.MockTransport(handler)
        original_close = transport.aclose

        async def close_transport():
            control.transport_closes.append((asyncio.get_running_loop(), threading.get_ident()))
            await original_close()

        monkeypatch.setattr(transport, "aclose", close_transport)
        client = real_async_client(**{**kwargs, "transport": transport})
        control.created.append(client)
        control.owned_closers.append(client.aclose)
        return client

    def build_sdk(*args, **kwargs):
        control.options.append(kwargs.get("http_options"))
        client = real_sdk(*args, **kwargs)
        control.sdk.append(client)
        control.sdk_closers.append((client.aio.aclose, client.close))
        return client

    monkeypatch.setattr(gemini_client.httpx, "AsyncClient", build_async_client)
    monkeypatch.setattr(gemini_client.genai, "Client", build_sdk)
    control.aiohttp_request = AsyncMock(
        side_effect=AssertionError("Default aiohttp request path used")
    )
    monkeypatch.setattr(aiohttp.ClientSession, "request", control.aiohttp_request)
    try:
        yield control
    finally:
        for close in control.owned_closers:
            await close()
        for async_close, sync_close in control.sdk_closers:
            try:
                await async_close()
            finally:
                sync_close()


async def invoke(client, method):
    if method == "a_generate_stream":
        return "".join([token async for token in client.a_generate_stream("synthetic prompt")])
    if method == "a_generate_structured":
        return await client.a_generate_structured("synthetic prompt", Answer)
    return await client.a_generate("synthetic prompt")


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("attempts", [1, 3])
@pytest.mark.parametrize("failure", ["connection", "timeout", "server"])
async def test_actual_constructor_uses_httpx_and_respects_total_attempts(
    native_constructor, method, attempts, failure, caplog
):
    control = native_constructor
    control.retry.max_retries = attempts
    control.error = failure
    client = gemini_client.GeminiClient(model="synthetic-selected-model")
    try:
        expected = {
            "connection": httpx.ConnectError,
            "timeout": httpx.ReadTimeout,
            "server": errors.APIError,
        }[failure]
        with pytest.raises(expected):
            await invoke(client, method)
        assert len(control.calls) == attempts
        control.aiohttp_request.assert_not_called()
        assert len(control.created) == 1
        assert control.options[0].httpx_async_client is control.created[0]
        assert control.created[0].follow_redirects is True
        assert control.created[0].trust_env is True
        assert "transport" not in control.client_kwargs[0]
        assert client.model == "synthetic-selected-model"
        assert not control.created[0].is_closed
        assert control.transport_closes == []
        # Failed calls must not dispose the shared application-owned HTTP pool.
        control.error = None
        result = await invoke(client, method)
        assert result == (
            Answer(answer="synthetic answer")
            if method == "a_generate_structured"
            else "synthetic answer"
        )
        assert not control.created[0].is_closed
        assert "forbidden-connection-detail" not in caplog.text
        assert "forbidden-timeout-detail" not in caplog.text
        assert "forbidden-server-detail" not in caplog.text
    finally:
        await client.aclose()
    assert control.created[0].is_closed
    assert control.transport_closes == [(asyncio.get_running_loop(), threading.get_ident())]


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
async def test_constructor_native_success_keeps_pool_until_explicit_close(
    native_constructor, method
):
    control = native_constructor
    client = gemini_client.GeminiClient()
    try:
        result = await invoke(client, method)
        assert result == (
            Answer(answer="synthetic answer")
            if method == "a_generate_structured"
            else "synthetic answer"
        )
        assert client.model == "synthetic-default-model"
        assert len(control.calls) == 1
        assert len(control.created) == 1
        assert not control.created[0].is_closed
        assert control.transport_closes == []
        control.aiohttp_request.assert_not_called()
    finally:
        await client.aclose()
    assert control.created[0].is_closed
    assert len(control.transport_closes) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "sdk-async",
        "owned-httpx",
        "sdk-sync",
        "cancelled",
        "sdk-plus-owned",
        "cancel-plus-owned",
        "all-fail",
    ],
)
async def test_owned_transport_and_sync_sdk_close_are_attempted_on_cleanup_failure(
    native_constructor, failure, monkeypatch
):
    control = native_constructor
    client = gemini_client.GeminiClient()
    sdk = client.client
    original_async, original_sync = sdk.aio.aclose, sdk.close
    owned = control.created[0]
    original_owned = owned.aclose
    calls = []
    owner_thread = threading.get_ident()

    async def close_sdk():
        calls.append(("sdk-async", threading.get_ident()))
        await original_async()
        if failure in {"sdk-async", "sdk-plus-owned", "all-fail"}:
            raise RuntimeError("synthetic sdk close failure")
        if failure in {"cancelled", "cancel-plus-owned"}:
            raise asyncio.CancelledError

    async def close_owned():
        calls.append(("owned-httpx", threading.get_ident()))
        await original_owned()
        if failure in {"owned-httpx", "sdk-plus-owned", "cancel-plus-owned", "all-fail"}:
            raise RuntimeError("synthetic httpx close failure")

    def close_sync():
        calls.append(("sdk-sync", threading.get_ident()))
        original_sync()
        if failure in {"sdk-sync", "all-fail"}:
            raise RuntimeError("synthetic sync close failure")

    monkeypatch.setattr(sdk.aio, "aclose", close_sdk)
    monkeypatch.setattr(owned, "aclose", close_owned)
    monkeypatch.setattr(sdk, "close", close_sync)
    try:
        expected = (
            asyncio.CancelledError
            if failure in {"cancelled", "cancel-plus-owned"}
            else BaseExceptionGroup
            if failure in {"sdk-plus-owned", "all-fail"}
            else RuntimeError
        )
        with pytest.raises(expected):
            await client.aclose()
        assert [name for name, _ in calls] == ["sdk-async", "owned-httpx", "sdk-sync"]
        assert calls[0][1] == calls[1][1] == owner_thread
        assert calls[2][1] != owner_thread
        assert owned.is_closed
        assert len(control.transport_closes) == 1
    finally:
        await original_owned()
        await original_async()
        original_sync()


@pytest.mark.asyncio
async def test_sdk_constructor_failure_propagates_without_io_or_background_cleanup(
    native_constructor, monkeypatch, request
):
    """A sync constructor cannot await disposal of its never-used async client."""
    import gc

    # Prior tests can leave closed SDK objects in cycles whose vendor destructors
    # schedule redundant closes. Do not attribute that unrelated GC to this
    # synchronous constructor; its own task creation remains observable below.
    if gc.isenabled():
        gc.disable()
        request.addfinalizer(gc.enable)
    control = native_constructor
    error = ValueError("synthetic SDK constructor failure")
    before = asyncio.all_tasks()

    def fail_sdk(**kwargs):
        raise error

    monkeypatch.setattr(gemini_client.genai, "Client", fail_sdk)
    with pytest.raises(ValueError) as raised:
        gemini_client.GeminiClient()
    assert raised.value is error
    assert len(control.created) == 1
    assert control.calls == []
    assert control.sdk == []
    assert control.transport_closes == []
    control.aiohttp_request.assert_not_called()
    assert asyncio.all_tasks() == before
    # The fixture retains the unused object for inspection and closes it at teardown.
