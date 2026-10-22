"""Nonstream policy at synthetic SDK leaves: no real keys/SDK construction."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from google.genai import errors
from openai import APIConnectionError, APIStatusError
from pydantic import BaseModel, ValidationError

from src.infra.llm import gemini_client, litellm_client, qwen_client

METHODS = ["generate", "a_generate", "generate_structured", "a_generate_structured"]
ASYNC_METHODS = ["a_generate", "a_generate_structured"]


class Answer(BaseModel):
    answer: str


@pytest.fixture(
    params=[qwen_client, gemini_client, litellm_client], ids=["qwen", "gemini", "litellm"]
)
def provider(request, monkeypatch):
    module = request.param
    retry = SimpleNamespace(max_retries=3, retry_delay=0.0)
    monkeypatch.setattr(module, "settings", SimpleNamespace(retry=retry))
    sync, async_ = MagicMock(), AsyncMock()
    if module is qwen_client:
        client = module.QwenClient.__new__(module.QwenClient)
        sdk = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=sync)))
        async_sdk = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=async_))
        )
        sdk.with_options = MagicMock(return_value=sdk)
        async_sdk.with_options = MagicMock(return_value=async_sdk)
        client.client, client.async_client = sdk, async_sdk
    elif module is gemini_client:
        client = module.GeminiClient.__new__(module.GeminiClient)
        client.client = SimpleNamespace(
            models=SimpleNamespace(generate_content=sync),
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=async_)),
        )
    else:
        client = module.LiteLLMClient.__new__(module.LiteLLMClient)
        client._api_key = "synthetic-not-a-key"
        monkeypatch.setattr(module.litellm, "completion", sync)
        monkeypatch.setattr(module.litellm, "acompletion", async_)
        monkeypatch.setattr(module.litellm, "num_retries", 0)
        monkeypatch.setattr(module.litellm, "model_fallbacks", None)
    client.model = "synthetic-model"
    return SimpleNamespace(module=module, client=client, sync=sync, async_=async_, retry=retry)


def response(method):
    structured = "structured" in method
    return SimpleNamespace(
        text="synthetic answer",
        parsed=Answer(answer="synthetic answer") if structured else None,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"answer":"synthetic answer"}' if structured else "synthetic answer"
                )
            )
        ],
    )


def create_for(provider, method):
    return provider.async_ if method.startswith("a_") else provider.sync


async def invoke(provider, method):
    args = ("forbidden-prompt", Answer) if "structured" in method else ("forbidden-prompt",)
    result = getattr(provider.client, method)(*args, context="forbidden-context")
    return await result if method.startswith("a_") else result


def failure(provider, kind):
    request = httpx.Request("POST", "https://synthetic.invalid")
    if kind.isdigit():
        code = int(kind)
        if provider.module is gemini_client:
            return errors.APIError(
                code, {"error": {"message": "forbidden-sdk-detail", "code": code}}
            )
        return APIStatusError(
            "forbidden-sdk-detail", response=httpx.Response(code, request=request), body=None
        )
    if kind == "connection":
        if provider.module is not gemini_client:
            return APIConnectionError(message="forbidden-sdk-detail", request=request)
        return httpx.ConnectError("forbidden-sdk-detail", request=request)
    if kind == "protocol":
        return httpx.RemoteProtocolError("forbidden-sdk-detail", request=request)
    if kind == "http_timeout":
        return httpx.ReadTimeout("forbidden-sdk-detail", request=request)
    if kind == "timeout":
        return TimeoutError("forbidden-sdk-detail")
    if kind == "validation":
        try:
            Answer.model_validate({"answer": None})
        except ValidationError as exc:
            return exc
        raise AssertionError("Expected invalid synthetic response")
    return RuntimeError("forbidden-sdk-detail")


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    "kind", ["timeout", "connection", "protocol", "http_timeout", "408", "429", "500", "503"]
)
async def test_nonstream_transient_failure_retries_once_then_succeeds(
    provider, method, kind, caplog
):
    create = create_for(provider, method)
    create.side_effect = [failure(provider, kind), response(method)]
    result = await invoke(provider, method)
    assert result == (
        Answer(answer="synthetic answer") if "structured" in method else "synthetic answer"
    )
    assert create.call_count == 2
    assert "forbidden-sdk-detail" not in caplog.text
    assert "forbidden-prompt" not in caplog.text
    assert "forbidden-context" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("kind", ["400", "401", "403", "404", "422", "unknown", "validation"])
async def test_nonstream_permanent_unknown_and_validation_fail_once(provider, method, kind, caplog):
    create = create_for(provider, method)
    error = failure(provider, kind)
    create.side_effect = error
    with pytest.raises(type(error)) as raised:
        await invoke(provider, method)
    assert raised.value is error
    assert create.call_count == 1
    assert "forbidden-sdk-detail" not in caplog.text
    assert "forbidden-prompt" not in caplog.text
    assert "forbidden-context" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
async def test_nonstream_empty_response_fails_once(provider, method):
    create = create_for(provider, method)
    create.return_value = SimpleNamespace(
        text=None, parsed=None, choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
    )
    with pytest.raises(ValueError):
        await invoke(provider, method)
    assert create.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["generate_structured", "a_generate_structured"])
async def test_nonstream_malformed_structured_response_is_not_regenerated(provider, method):
    create = create_for(provider, method)
    create.return_value = SimpleNamespace(
        text="not json",
        parsed=None,
        choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))],
    )
    with pytest.raises(ValueError):
        await invoke(provider, method)
    assert create.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("attempts", [-1, 0, 1, 2, 3])
async def test_nonstream_attempt_setting_is_total_and_at_least_one(
    provider, method, attempts, caplog
):
    provider.retry.max_retries = attempts
    create = create_for(provider, method)
    error = failure(provider, "timeout")
    create.side_effect = error
    with pytest.raises(TimeoutError) as raised:
        await invoke(provider, method)
    assert raised.value is error
    assert create.call_count == max(1, attempts)
    assert "forbidden-sdk-detail" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(("delay", "expected"), [(-2.0, [0.0, 0.0]), (100.0, [30.0, 30.0])])
async def test_nonstream_backoff_is_nonnegative_and_capped(
    provider, method, delay, expected, monkeypatch
):
    provider.retry.retry_delay = delay
    create_for(provider, method).side_effect = failure(provider, "timeout")
    if method.startswith("a_"):
        sleep = AsyncMock()
        monkeypatch.setattr(provider.module.asyncio, "sleep", sleep)
    else:
        sleep = MagicMock()
        monkeypatch.setattr(provider.module.time, "sleep", sleep)
    with pytest.raises(TimeoutError):
        await invoke(provider, method)
    assert [call.args[0] for call in sleep.call_args_list] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
async def test_nonstream_native_retries_disabled_per_call_and_timeout_explicit(provider, method):
    create = create_for(provider, method)
    create.return_value = response(method)
    await invoke(provider, method)
    kwargs = create.call_args.kwargs
    if provider.module is qwen_client:
        sdk = provider.client.async_client if method.startswith("a_") else provider.client.client
        sdk.with_options.assert_called_once_with(max_retries=0, timeout=30.0)
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 2048
    elif provider.module is gemini_client:
        config = kwargs["config"]
        assert config.http_options.timeout == 30000
        assert config.http_options.retry_options.attempts == 1
        assert config.temperature == 0.7
        assert config.max_output_tokens == 2048
        if "structured" in method:
            assert config.response_schema is Answer
            assert config.response_mime_type == "application/json"
    else:
        assert kwargs["max_retries"] == kwargs["num_retries"] == 0
        assert kwargs["timeout"] == 30.0
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 2048
        assert provider.module.litellm.num_retries == 0
        assert provider.module.litellm.model_fallbacks is None


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ASYNC_METHODS)
@pytest.mark.parametrize("stage", ["request", "backoff"])
async def test_nonstream_cancellation_is_primary_and_never_retried(
    provider, method, stage, monkeypatch
):
    started = asyncio.Event()

    async def blocked(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    create = create_for(provider, method)
    if stage == "request":
        create.side_effect = blocked
    else:
        create.side_effect = failure(provider, "timeout")
        monkeypatch.setattr(provider.module.asyncio, "sleep", blocked)
    task = asyncio.create_task(invoke(provider, method))
    try:
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert create.call_count == 1
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ASYNC_METHODS)
async def test_nonstream_async_attempt_deadline_is_finite(provider, method, monkeypatch):
    monkeypatch.setattr(provider.module, "DEFAULT_TIMEOUT", 0.02)

    async def blocked(*args, **kwargs):
        await asyncio.Event().wait()

    create = create_for(provider, method)
    create.side_effect = blocked
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(invoke(provider, method), 2)
    assert create.call_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("policy", ["retries", "fallbacks"])
async def test_litellm_nonstream_rejects_conflicting_global_policy(method, policy, monkeypatch):
    client = litellm_client.LiteLLMClient.__new__(litellm_client.LiteLLMClient)
    client.model, client._api_key = "synthetic-model", "synthetic-not-a-key"
    create = AsyncMock() if method.startswith("a_") else MagicMock()
    monkeypatch.setattr(
        litellm_client.litellm, "acompletion" if method.startswith("a_") else "completion", create
    )
    retries, fallbacks = (2, None) if policy == "retries" else (0, [{"synthetic": ["other"]}])
    monkeypatch.setattr(litellm_client.litellm, "num_retries", retries)
    monkeypatch.setattr(litellm_client.litellm, "model_fallbacks", fallbacks)
    with pytest.raises(RuntimeError, match="Global LiteLLM"):
        await invoke(SimpleNamespace(client=client), method)
    create.assert_not_called()
    assert litellm_client.litellm.num_retries == retries
    assert litellm_client.litellm.model_fallbacks is fallbacks
