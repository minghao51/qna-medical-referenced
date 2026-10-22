"""Provider stream contracts with synthetic SDK leaves: no SDK/key construction."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from google.genai import errors
from openai import APIConnectionError, APIStatusError

from src.infra.llm import gemini_client, litellm_client, qwen_client


class SyntheticStream:
    def __init__(self, steps, *, close_error=False):
        self.steps = iter(steps)
        self.closed = 0
        self.close_error = close_error
        self.read_started = asyncio.Event()
        self.release = asyncio.Event()

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = next(self.steps, StopAsyncIteration)
        if item is StopAsyncIteration:
            raise StopAsyncIteration
        if item == "BLOCK":
            self.read_started.set()
            await self.release.wait()
            raise StopAsyncIteration
        if isinstance(item, BaseException):
            raise item
        return item

    async def aclose(self):
        self.closed += 1
        await asyncio.sleep(0)
        if self.close_error:
            raise RuntimeError("forbidden-close-detail")

    close = aclose


@pytest.fixture(
    params=[qwen_client, gemini_client, litellm_client], ids=["qwen", "gemini", "litellm"]
)
def provider(request, monkeypatch):
    module = request.param
    monkeypatch.setattr(
        module, "settings", SimpleNamespace(retry=SimpleNamespace(max_retries=3, retry_delay=0.0))
    )
    create = AsyncMock()
    if module is qwen_client:
        client = qwen_client.QwenClient.__new__(qwen_client.QwenClient)
        sdk = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        sdk.with_options = MagicMock(return_value=sdk)
        client.async_client = sdk
    elif module is gemini_client:
        client = gemini_client.GeminiClient.__new__(gemini_client.GeminiClient)
        client.client = SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content_stream=create))
        )
    else:
        client = litellm_client.LiteLLMClient.__new__(litellm_client.LiteLLMClient)
        client._api_key = "synthetic-not-a-key"
        monkeypatch.setattr(module.litellm, "acompletion", create)
    client.model = "synthetic-model"

    def chunk(text):
        if module is gemini_client:
            return SimpleNamespace(text=text)
        return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])

    def status_error(code):
        if module is gemini_client:
            return errors.APIError(
                code, {"error": {"message": "forbidden-sdk-detail", "code": code}}
            )
        response = httpx.Response(code, request=httpx.Request("POST", "https://synthetic.invalid"))
        return APIStatusError("forbidden-sdk-detail", response=response, body=None)

    return SimpleNamespace(
        module=module, client=client, create=create, chunk=chunk, status_error=status_error
    )


async def consume(provider):
    return [token async for token in provider.client.a_generate_stream("synthetic prompt")]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["unknown", "timeout", "server"])
async def test_never_replays_after_first_content(provider, failure):
    error = {
        "unknown": RuntimeError("forbidden-sdk-detail"),
        "timeout": TimeoutError(),
        "server": provider.status_error(503),
    }[failure]
    first = SyntheticStream([provider.chunk("prefix "), error])
    retry = SyntheticStream([provider.chunk("prefix tail")])
    provider.create.side_effect = [first, retry]
    tokens = []
    with pytest.raises(type(error)):
        async for token in provider.client.a_generate_stream("synthetic prompt"):
            tokens.append(token)
    assert tokens == ["prefix "]
    assert provider.create.await_count == 1
    assert first.closed == 1
    assert retry.closed == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "rate", "server", "transport"])
async def test_transient_failure_before_content_retries_after_close(provider, failure):
    error = {
        "timeout": TimeoutError(),
        "rate": provider.status_error(429),
        "server": provider.status_error(503),
        "transport": APIConnectionError(request=httpx.Request("POST", "https://synthetic.invalid")),
    }[failure]
    # Gemini's HTTPX transport failure is native; OpenAI's connection wrapper is not.
    if failure == "transport" and provider.module is gemini_client:
        error = httpx.ConnectError("synthetic transport")
    first = SyntheticStream([error])
    second = SyntheticStream([provider.chunk("complete")])

    async def create(**kwargs):
        if provider.create.await_count == 1:
            return first
        assert first.closed == 1
        return second

    provider.create.side_effect = create
    assert await consume(provider) == ["complete"]
    assert provider.create.await_count == 2
    assert first.closed == second.closed == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["validation", "unknown", "auth", "bad_request"])
async def test_permanent_failure_is_not_retried(provider, failure, caplog):
    error = {
        "validation": ValueError("forbidden-sdk-detail"),
        "unknown": RuntimeError("forbidden-sdk-detail"),
        "auth": provider.status_error(401),
        "bad_request": provider.status_error(400),
    }[failure]
    stream = SyntheticStream([error])
    provider.create.return_value = stream
    with pytest.raises(type(error)):
        await consume(provider)
    assert provider.create.await_count == 1
    assert stream.closed == 1
    assert "forbidden-sdk-detail" not in caplog.text


@pytest.mark.asyncio
async def test_empty_and_usage_chunks_are_not_content(provider):
    empty = (
        provider.chunk(None) if provider.module is gemini_client else SimpleNamespace(choices=[])
    )
    stream = SyntheticStream([empty, provider.chunk(""), provider.chunk("answer")])
    provider.create.return_value = stream
    assert await consume(provider) == ["answer"]
    assert stream.closed == 1


@pytest.mark.asyncio
async def test_attempt_limit_is_total_calls_and_closes_every_attempt(provider):
    streams = [SyntheticStream([TimeoutError()]) for _ in range(3)]
    provider.create.side_effect = streams
    with pytest.raises(TimeoutError):
        await consume(provider)
    assert provider.create.await_count == 3
    assert [stream.closed for stream in streams] == [1, 1, 1]


@pytest.mark.asyncio
@pytest.mark.parametrize("partial", [False, True])
@pytest.mark.parametrize("close_error", [False, True])
async def test_read_cancellation_closes_without_retry(provider, partial, close_error):
    stream = SyntheticStream(
        ([provider.chunk("prefix")] if partial else []) + ["BLOCK"], close_error=close_error
    )
    provider.create.return_value = stream
    task = asyncio.create_task(consume(provider))
    try:
        await asyncio.wait_for(stream.read_started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stream.closed == 1
        assert provider.create.await_count == 1
    finally:
        stream.release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_explicit_early_close_reaches_owned_sdk_stream(provider):
    stream = SyntheticStream([provider.chunk("prefix"), "BLOCK"])
    provider.create.return_value = stream
    generator = provider.client.a_generate_stream("synthetic prompt")
    assert await anext(generator) == "prefix"
    await generator.aclose()
    assert stream.closed == 1
    assert provider.create.await_count == 1


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_mask_primary_or_log_details(provider, caplog):
    error = ValueError("forbidden-sdk-detail")
    stream = SyntheticStream([error], close_error=True)
    provider.create.return_value = stream
    with pytest.raises(ValueError) as raised:
        await consume(provider)
    assert raised.value is error
    assert stream.closed == 1
    assert "forbidden-close-detail" not in caplog.text
    assert "forbidden-sdk-detail" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "auth", "cancel"])
async def test_creation_failure_policy(provider, failure):
    error = {
        "timeout": TimeoutError(),
        "auth": provider.status_error(401),
        "cancel": asyncio.CancelledError(),
    }[failure]
    provider.create.side_effect = error
    with pytest.raises(type(error)):
        await consume(provider)
    assert provider.create.await_count == (3 if failure == "timeout" else 1)


@pytest.mark.asyncio
async def test_lower_layer_retries_disabled_and_timeout_explicit(provider):
    provider.create.return_value = SyntheticStream([provider.chunk("complete")])
    assert await consume(provider) == ["complete"]
    kwargs = provider.create.call_args.kwargs
    if provider.module is qwen_client:
        provider.client.async_client.with_options.assert_called_once_with(
            max_retries=0, timeout=30.0
        )
    elif provider.module is gemini_client:
        options = kwargs["config"].http_options
        assert options.retry_options.attempts == 1
        assert options.timeout == 30000
    else:
        assert kwargs["max_retries"] == kwargs["num_retries"] == 0
        assert kwargs["timeout"] == 30.0


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["create", "read"])
async def test_attempt_deadline_is_finite(provider, monkeypatch, stage):
    monkeypatch.setattr(provider.module, "DEFAULT_TIMEOUT", 0.02)
    streams = []

    async def create(**kwargs):
        if stage == "create":
            await asyncio.Event().wait()
        stream = SyntheticStream(["BLOCK"])
        streams.append(stream)
        return stream

    provider.create.side_effect = create
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(consume(provider), timeout=2)
    assert provider.create.await_count == 3
    assert all(stream.closed == 1 for stream in streams)


@pytest.mark.asyncio
async def test_attempt_budget_excludes_suspended_consumer(provider, monkeypatch):
    monkeypatch.setattr(provider.module, "DEFAULT_TIMEOUT", 0.02)
    stream = SyntheticStream([provider.chunk("prefix"), provider.chunk("tail")])
    provider.create.return_value = stream
    generator = provider.client.a_generate_stream("synthetic prompt")
    try:
        assert await anext(generator) == "prefix"
        # No active timeout scope or spent upstream budget during backpressure.
        await asyncio.sleep(0.04)
        assert await anext(generator) == "tail"
        with pytest.raises(StopAsyncIteration):
            await anext(generator)
        assert provider.create.await_count == 1
        assert stream.closed == 1
    finally:
        await generator.aclose()


@pytest.mark.asyncio
async def test_cleanup_failure_alone_never_retries_a_completed_stream(provider, caplog):
    stream = SyntheticStream([provider.chunk("complete")], close_error=True)
    provider.create.return_value = stream
    assert await consume(provider) == ["complete"]
    assert stream.closed == 1
    assert provider.create.await_count == 1
    assert "forbidden-close-detail" not in caplog.text


@pytest.mark.asyncio
async def test_cancellation_during_backoff_stops_new_attempts(provider, monkeypatch):
    stream = SyntheticStream([TimeoutError()])
    provider.create.return_value = stream
    backoff_started = asyncio.Event()
    monkeypatch.setattr(provider.module.settings.retry, "retry_delay", 1.0)
    monkeypatch.setattr(
        provider.module.logger, "warning", lambda *args, **kwargs: backoff_started.set()
    )
    task = asyncio.create_task(consume(provider))
    try:
        await asyncio.wait_for(backoff_started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stream.closed == 1
        assert provider.create.await_count == 1
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
