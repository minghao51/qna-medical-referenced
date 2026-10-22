"""Offline request-boundary and ownership tests for direct judge SDK clients."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import litellm
import pytest
from pydantic import SecretStr

from src.config import settings
from src.evals import deepeval_models


def _response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def _set_judge_request_settings(monkeypatch):
    monkeypatch.setattr(settings.llm, "judge_temperature", 0.35)
    monkeypatch.setattr(settings.llm, "judge_max_tokens", 321)
    monkeypatch.setattr(settings.deepeval, "deepeval_metric_timeout_seconds", 17)


@pytest.mark.asyncio
async def test_qwen_judge_preserves_settings_and_disables_sdk_retries(monkeypatch):
    _set_judge_request_settings(monkeypatch)
    sync_create = MagicMock(return_value=_response("sync verdict"))
    sync_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=sync_create)),
        close=MagicMock(),
    )
    async_create = AsyncMock(return_value=_response("async verdict"))
    async_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=async_create)),
        close=AsyncMock(),
    )
    sync_constructor = MagicMock(return_value=sync_client)
    async_constructor = MagicMock(return_value=async_client)
    monkeypatch.setattr(deepeval_models, "OpenAI", sync_constructor)
    monkeypatch.setattr(deepeval_models, "AsyncOpenAI", async_constructor)
    monkeypatch.setattr(settings.llm, "dashscope_api_key", SecretStr("synthetic-key"))

    model = deepeval_models.QwenModel("judge-model")

    assert sync_constructor.call_args.kwargs["max_retries"] == 0
    assert async_constructor.call_args.kwargs["max_retries"] == 0
    assert sync_constructor.call_args.kwargs["timeout"] == 17
    assert model.generate("judge prompt") == "sync verdict"
    assert sync_create.call_args.kwargs["temperature"] == 0.35
    assert sync_create.call_args.kwargs["max_tokens"] == 321
    assert sync_create.call_args.kwargs["timeout"] == 17

    assert await model.a_generate("judge prompt") == "async verdict"
    assert async_create.call_args.kwargs["temperature"] == 0.35
    assert async_create.call_args.kwargs["max_tokens"] == 321
    await model.aclose()
    async_client.close.assert_awaited_once()
    sync_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_qwen_aclose_attempts_both_transports_when_async_close_fails(monkeypatch):
    async_client = SimpleNamespace(close=AsyncMock(side_effect=RuntimeError("synthetic")))
    sync_client = SimpleNamespace(close=MagicMock())
    monkeypatch.setattr(deepeval_models, "OpenAI", lambda **kwargs: sync_client)
    monkeypatch.setattr(deepeval_models, "AsyncOpenAI", lambda **kwargs: async_client)
    monkeypatch.setattr(settings.llm, "dashscope_api_key", SecretStr("synthetic-key"))

    model = deepeval_models.QwenModel("judge-model")

    with pytest.raises(RuntimeError, match="synthetic"):
        await model.aclose()
    async_client.close.assert_awaited_once()
    sync_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_gemini_judge_selects_public_httpx_and_closes_owned_resources(monkeypatch):
    from google import genai

    _set_judge_request_settings(monkeypatch)
    sync_generate = MagicMock(return_value=SimpleNamespace(text="sync verdict"))
    async_generate = AsyncMock(return_value=SimpleNamespace(text="async verdict"))
    aio = SimpleNamespace(
        models=SimpleNamespace(generate_content=async_generate),
        aclose=AsyncMock(),
    )
    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=sync_generate),
        aio=aio,
        close=MagicMock(),
    )
    constructor = MagicMock(return_value=client)
    monkeypatch.setattr(genai, "Client", constructor)
    monkeypatch.setattr(settings.llm, "gemini_api_key", SecretStr("synthetic-key"))

    model = deepeval_models.GeminiJudgeModel("models/gemini-test")
    transport = model._owned_async_http_client

    options = constructor.call_args.kwargs["http_options"]
    assert options.httpx_async_client is transport
    assert options.retry_options.attempts == 1
    assert options.timeout == 17_000
    assert model.generate("judge prompt") == "sync verdict"
    sync_config = sync_generate.call_args.kwargs["config"]
    assert sync_config.temperature == 0.35
    assert sync_config.max_output_tokens == 321
    assert sync_config.http_options.retry_options.attempts == 1

    assert await model.a_generate("judge prompt") == "async verdict"
    async_config = async_generate.call_args.kwargs["config"]
    assert async_config.temperature == 0.35
    assert async_config.max_output_tokens == 321
    assert async_config.http_options.retry_options.attempts == 1
    await model.aclose()
    aio.aclose.assert_awaited_once()
    assert transport.is_closed
    client.close.assert_called_once()


@pytest.mark.asyncio
async def test_gemini_judge_native_sdk_uses_httpx_once_and_closes_transport(monkeypatch):
    import aiohttp
    import httpx
    from google.genai import errors

    real_async_client = httpx.AsyncClient
    requests = []

    async def respond(request):
        requests.append(request)
        return httpx.Response(
            500,
            json={"error": {"code": 500, "message": "synthetic", "status": "INTERNAL"}},
        )

    def build_async_client(**kwargs):
        return real_async_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "false")
    monkeypatch.setattr(deepeval_models.httpx, "AsyncClient", build_async_client)
    aiohttp_request = AsyncMock(side_effect=AssertionError("aiohttp transport must not be used"))
    monkeypatch.setattr(aiohttp.ClientSession, "request", aiohttp_request)
    monkeypatch.setattr(settings.llm, "gemini_api_key", SecretStr("synthetic-key"))
    model = deepeval_models.GeminiJudgeModel("models/gemini-test")
    transport = model._owned_async_http_client

    with pytest.raises(errors.APIError):
        await model.a_generate("synthetic judge prompt")

    assert len(requests) == 1
    aiohttp_request.assert_not_called()
    await model.aclose()
    assert transport.is_closed


@pytest.mark.asyncio
async def test_gemini_aclose_attempts_all_owned_cleanup_after_failure(monkeypatch):
    from google import genai

    aio = SimpleNamespace(aclose=AsyncMock(side_effect=RuntimeError("sdk")))
    client = SimpleNamespace(aio=aio, close=MagicMock())
    monkeypatch.setattr(genai, "Client", lambda **kwargs: client)
    monkeypatch.setattr(settings.llm, "gemini_api_key", SecretStr("synthetic-key"))

    model = deepeval_models.GeminiJudgeModel("models/gemini-test")
    transport = model._owned_async_http_client

    with pytest.raises(RuntimeError, match="sdk"):
        await model.aclose()
    aio.aclose.assert_awaited_once()
    assert transport.is_closed
    client.close.assert_called_once()


def test_litellm_judge_disables_request_retries_and_preserves_parameters(monkeypatch):
    _set_judge_request_settings(monkeypatch)
    monkeypatch.setattr(litellm, "model_fallbacks", None)
    monkeypatch.setattr(litellm, "num_retries", 0)
    monkeypatch.setattr(settings.llm, "openrouter_api_key", SecretStr("synthetic-key"))
    completion = MagicMock(return_value=_response("verdict"))
    monkeypatch.setattr(litellm, "completion", completion)

    model = deepeval_models.LiteLLMJudgeModel("openrouter/test-model")

    assert model.generate("judge prompt") == "verdict"
    kwargs = completion.call_args.kwargs
    assert kwargs["max_retries"] == kwargs["num_retries"] == 0
    assert kwargs["timeout"] == 17
    assert kwargs["temperature"] == 0.35
    assert kwargs["max_tokens"] == 321


@pytest.mark.asyncio
async def test_litellm_judge_async_uses_bounded_request(monkeypatch):
    _set_judge_request_settings(monkeypatch)
    monkeypatch.setattr(litellm, "model_fallbacks", None)
    monkeypatch.setattr(litellm, "num_retries", 0)
    monkeypatch.setattr(settings.llm, "openrouter_api_key", SecretStr("synthetic-key"))
    completion = AsyncMock(return_value=_response("async verdict"))
    monkeypatch.setattr(litellm, "acompletion", completion)

    model = deepeval_models.LiteLLMJudgeModel("openrouter/test-model")

    assert await model.a_generate("judge prompt") == "async verdict"
    assert completion.call_args.kwargs["max_retries"] == 0
    assert completion.call_args.kwargs["num_retries"] == 0
    assert completion.call_args.kwargs["timeout"] == 17


@pytest.mark.parametrize("global_name", ["num_retries", "model_fallbacks"])
def test_litellm_judge_rejects_process_global_retry_or_fallback(monkeypatch, global_name):
    monkeypatch.setattr(litellm, "num_retries", 0)
    monkeypatch.setattr(litellm, "model_fallbacks", None)
    monkeypatch.setattr(
        litellm, global_name, 1 if global_name == "num_retries" else ["other/model"]
    )
    completion = MagicMock(side_effect=AssertionError("must not call LiteLLM"))
    monkeypatch.setattr(litellm, "completion", completion)
    monkeypatch.setattr(settings.llm, "openrouter_api_key", SecretStr("synthetic-key"))

    model = deepeval_models.LiteLLMJudgeModel("openrouter/test-model")

    with pytest.raises(RuntimeError, match="Global LiteLLM retries/fallbacks"):
        model.generate("judge prompt")
    completion.assert_not_called()
