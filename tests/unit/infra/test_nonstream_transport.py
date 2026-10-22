"""Installed public SDK retry behavior over in-memory HTTPX transports only."""

from types import SimpleNamespace

import httpx
import pytest
from google import genai
from google.genai import errors, types
from openai import APIStatusError, AsyncOpenAI, OpenAI
from pydantic import BaseModel

from src.infra.llm import gemini_client, qwen_client


class Answer(BaseModel):
    answer: str


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["qwen", "gemini"])
@pytest.mark.parametrize(
    "method", ["generate", "a_generate", "generate_structured", "a_generate_structured"]
)
async def test_nonstream_native_attempts_do_not_multiply_or_mutate_shared_sdk(
    provider, method, monkeypatch
):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            500,
            json={"error": {"code": 500, "message": "synthetic-error", "status": "INTERNAL"}},
            headers={"retry-after-ms": "1"},
        )

    sync_http = httpx.Client(transport=httpx.MockTransport(handle), trust_env=False)
    async_http = httpx.AsyncClient(transport=httpx.MockTransport(handle), trust_env=False)
    module = qwen_client if provider == "qwen" else gemini_client
    monkeypatch.setattr(
        module, "settings", SimpleNamespace(retry=SimpleNamespace(max_retries=3, retry_delay=0.0))
    )
    if provider == "qwen":
        client = qwen_client.QwenClient.__new__(qwen_client.QwenClient)
        client.client = OpenAI(
            api_key="synthetic-not-a-key",
            base_url="https://synthetic.invalid/v1",
            max_retries=2,
            http_client=sync_http,
        )
        client.async_client = AsyncOpenAI(
            api_key="synthetic-not-a-key",
            base_url="https://synthetic.invalid/v1",
            max_retries=2,
            http_client=async_http,
        )
        expected_error = APIStatusError
    else:
        options = types.HttpOptions(
            base_url="https://synthetic.invalid",
            httpx_client=sync_http,
            httpx_async_client=async_http,
            retry_options=types.HttpRetryOptions(
                attempts=3,
                initial_delay=0.001,
                max_delay=0.001,
                jitter=0.0,
            ),
        )
        client = gemini_client.GeminiClient.__new__(gemini_client.GeminiClient)
        client.client = genai.Client(
            vertexai=False, api_key="synthetic-not-a-key", http_options=options
        )
        expected_error = errors.APIError
    client.model = "synthetic-model"
    try:
        args = ("synthetic prompt", Answer) if "structured" in method else ("synthetic prompt",)
        with pytest.raises(expected_error):
            result = getattr(client, method)(*args)
            if method.startswith("a_"):
                await result
        assert len(calls) == 3  # Wrapper total, not three times native retries.
        assert not sync_http.is_closed
        assert not async_http.is_closed

        # A direct public SDK call still uses its original three-attempt policy.
        # This proves per-call overrides did not mutate or close the shared SDK.
        with pytest.raises(expected_error):
            if provider == "qwen":
                native = client.async_client if method.startswith("a_") else client.client
                assert native.max_retries == 2
                result = native.chat.completions.create(
                    model=client.model,
                    messages=[{"role": "user", "content": "synthetic"}],
                )
            else:
                assert options.retry_options.attempts == 3
                native = client.client.aio if method.startswith("a_") else client.client
                result = native.models.generate_content(model=client.model, contents="synthetic")
            if method.startswith("a_"):
                await result
        assert len(calls) == 6
    finally:
        try:
            await client.aclose()
        finally:
            sync_http.close()
            await async_http.aclose()
