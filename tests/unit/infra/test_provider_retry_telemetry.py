"""Retry spans are synthetic, metadata-only, and scoped to nonstream attempts."""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from src.config.settings import TelemetryConfig
from src.infra.llm import gemini_client, litellm_client, qwen_client
from src.infra.telemetry import Operation, Telemetry, use_telemetry
from src.infra.usage import capture_usage

METHODS = ("generate", "a_generate", "generate_structured", "a_generate_structured")
ASYNC_METHODS = ("a_generate", "a_generate_structured")
_PROMPT_CANARY = "SYNTHETIC_RETRY_PROMPT_CANARY"
_CONTEXT_CANARY = "SYNTHETIC_RETRY_CONTEXT_CANARY"
_EXCEPTION_CANARY = "SYNTHETIC_RETRY_EXCEPTION_CANARY"


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


def _response():
    content = '{"answer":"synthetic answer"}'
    return SimpleNamespace(
        text=content,
        parsed=Answer(answer="synthetic answer"),
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=4, total_tokens=7),
        usage_metadata=SimpleNamespace(
            prompt_token_count=3, candidates_token_count=4, total_token_count=7
        ),
    )


def _create(provider, method):
    return provider.async_ if method.startswith("a_") else provider.sync


async def _invoke(provider, method):
    args = (_PROMPT_CANARY, Answer) if "structured" in method else (_PROMPT_CANARY,)
    result = getattr(provider.client, method)(*args, context=_CONTEXT_CANARY)
    return await result if method.startswith("a_") else result


def _serialize_spans(telemetry):
    return repr(
        [
            {
                "name": span.name,
                "attributes": dict(span.attributes or {}),
                "events": span.events,
            }
            for span in telemetry.finished_spans
        ]
    )


def _retry_spans(telemetry):
    return [span for span in telemetry.finished_spans if span.name == Operation.RETRY.value]


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
async def test_retry_spans_are_fresh_and_preserve_provider_usage(provider, method, caplog):
    create = _create(provider, method)
    create.side_effect = [TimeoutError(_EXCEPTION_CANARY), _response()]
    telemetry = Telemetry(TelemetryConfig(mode="local"))

    with use_telemetry(telemetry), capture_usage() as captured:
        result = await _invoke(provider, method)

    assert result == (
        Answer(answer="synthetic answer") if "structured" in method else _response().text
    )
    spans = _retry_spans(telemetry)
    assert len(spans) == 1
    attributes = dict(spans[0].attributes or {})
    assert attributes["telemetry.operation"] == Operation.RETRY.value
    assert attributes["telemetry.retry_count"] == 1
    attempt_id = attributes["telemetry.attempt_id"]
    assert str(uuid.UUID(attempt_id)) == attempt_id
    assert uuid.UUID(attempt_id).version == 4
    assert "telemetry.model" not in attributes
    assert "telemetry.stage" not in attributes
    assert not spans[0].events
    assert captured.usage_by_role["generation"]["total_tokens"] == 7
    assert "provider_call_failed" in captured.unknowns
    serialized = _serialize_spans(telemetry)
    assert all(
        canary not in serialized and canary not in caplog.text
        for canary in (_PROMPT_CANARY, _CONTEXT_CANARY, _EXCEPTION_CANARY)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
async def test_retry_count_tracks_each_actual_retry_with_distinct_ids(provider, method):
    create = _create(provider, method)
    create.side_effect = [
        TimeoutError("first synthetic failure"),
        TimeoutError("second synthetic failure"),
        _response(),
    ]
    telemetry = Telemetry(TelemetryConfig(mode="local"))

    with use_telemetry(telemetry):
        await _invoke(provider, method)

    spans = _retry_spans(telemetry)
    attributes = [dict(span.attributes or {}) for span in spans]
    assert [item["telemetry.retry_count"] for item in attributes] == [1, 2]
    assert len({item["telemetry.attempt_id"] for item in attributes}) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
async def test_permanent_error_is_not_retried_or_given_retry_span(provider, method, caplog):
    create = _create(provider, method)
    create.side_effect = RuntimeError(_EXCEPTION_CANARY)
    telemetry = Telemetry(TelemetryConfig(mode="local"))

    with use_telemetry(telemetry), pytest.raises(RuntimeError):
        await _invoke(provider, method)

    assert create.call_count == 1
    assert _retry_spans(telemetry) == []
    assert _EXCEPTION_CANARY not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
async def test_single_total_attempt_does_not_create_retry_span(provider, method):
    provider.retry.max_retries = 1
    create = _create(provider, method)
    error = TimeoutError("synthetic exhausted failure")
    create.side_effect = error
    telemetry = Telemetry(TelemetryConfig(mode="local"))

    with use_telemetry(telemetry), pytest.raises(TimeoutError) as raised:
        await _invoke(provider, method)

    assert raised.value is error
    assert create.call_count == 1
    assert _retry_spans(telemetry) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ASYNC_METHODS)
async def test_async_cancellation_is_not_retried_or_traced_as_retry(provider, method):
    started = asyncio.Event()

    async def blocked(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    create = _create(provider, method)
    create.side_effect = blocked
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    with use_telemetry(telemetry):
        task = asyncio.create_task(_invoke(provider, method))
        try:
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 2)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    assert create.call_count == 1
    assert _retry_spans(telemetry) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("method", METHODS)
async def test_retry_remains_functional_without_active_telemetry_owner(provider, method):
    create = _create(provider, method)
    create.side_effect = [TimeoutError("synthetic failure"), _response()]
    telemetry = Telemetry(TelemetryConfig(mode="local"))

    with use_telemetry(None), capture_usage() as captured:
        result = await _invoke(provider, method)

    assert result == (
        Answer(answer="synthetic answer") if "structured" in method else _response().text
    )
    assert create.call_count == 2
    assert telemetry.finished_spans == ()
    assert captured.usage_by_role["generation"]["total_tokens"] == 7
