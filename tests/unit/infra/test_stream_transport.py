"""Native OpenAI fake-HTTP evidence and fail-closed LiteLLM global policy."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIStatusError, AsyncOpenAI

from src.infra.llm import litellm_client, qwen_client


@pytest.mark.asyncio
async def test_qwen_native_sdk_does_not_multiply_stream_attempts(monkeypatch, caplog):
    calls = []

    async def respond(request):
        calls.append(request)
        return httpx.Response(503, json={"error": {"message": "forbidden-native-detail"}})

    http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    native = AsyncOpenAI(
        api_key="synthetic-not-a-key",
        base_url="https://synthetic.invalid/v1",
        http_client=http,
        max_retries=4,
    )
    client = qwen_client.QwenClient.__new__(qwen_client.QwenClient)
    client.async_client = native
    client.model = "synthetic-model"
    monkeypatch.setattr(
        qwen_client,
        "settings",
        SimpleNamespace(retry=SimpleNamespace(max_retries=3, retry_delay=0.0)),
    )
    try:
        with pytest.raises(APIStatusError):
            _ = [token async for token in client.a_generate_stream("synthetic prompt")]
        assert len(calls) == 3  # Not 3 x the SDK's configured five attempts.
        assert native.max_retries == 4  # Per-call override, not shared mutation.
        assert not native.is_closed()
        assert "forbidden-native-detail" not in caplog.text
    finally:
        await native.close()


@pytest.mark.asyncio
async def test_qwen_native_early_close_releases_response_not_shared_client():
    closed = asyncio.Event()

    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"id":"synthetic","object":"chat.completion.chunk","created":0,"model":"synthetic","choices":[{"index":0,"delta":{"content":"prefix"},"finish_reason":null}]}\n\n'
            await asyncio.Event().wait()

        async def aclose(self):
            await asyncio.sleep(0)
            closed.set()

    async def respond(request):
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=Body())

    http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    native = AsyncOpenAI(
        api_key="synthetic-not-a-key", base_url="https://synthetic.invalid/v1", http_client=http
    )
    client = qwen_client.QwenClient.__new__(qwen_client.QwenClient)
    client.async_client = native
    client.model = "synthetic-model"
    generator = client.a_generate_stream("synthetic prompt")
    try:
        assert await anext(generator) == "prefix"
        await generator.aclose()
        assert closed.is_set()
        assert not native.is_closed()
    finally:
        await generator.aclose()
        await native.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("policy", "value"), [("model_fallbacks", ["synthetic-other-model"]), ("num_retries", 5)]
)
async def test_litellm_rejects_conflicting_global_policy_without_mutation(
    monkeypatch, policy, value
):
    monkeypatch.setattr(litellm_client.litellm, policy, value)
    create = AsyncMock()
    monkeypatch.setattr(litellm_client.litellm, "acompletion", create)
    client = litellm_client.LiteLLMClient.__new__(litellm_client.LiteLLMClient)
    client.model = "synthetic-model"
    client._api_key = "synthetic-not-a-key"
    with pytest.raises(RuntimeError, match="Global LiteLLM"):
        _ = [token async for token in client.a_generate_stream("synthetic prompt")]
    assert getattr(litellm_client.litellm, policy) is value
    create.assert_not_awaited()
