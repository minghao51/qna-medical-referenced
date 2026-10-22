"""Stream retry transition spans are short-lived and metadata-only."""

from __future__ import annotations

import asyncio
import json
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from opentelemetry import trace

from src.config.settings import TelemetryConfig
from src.infra.llm import gemini_client, litellm_client, qwen_client
from src.infra.telemetry import ErrorCode, Operation, Telemetry, use_telemetry

_PROMPT_CANARY = "SYNTHETIC_STREAM_PROMPT_CANARY"
_CONTEXT_CANARY = "SYNTHETIC_STREAM_CONTEXT_CANARY"
_CONTENT_CANARY = "SYNTHETIC_STREAM_CONTENT_CANARY"
_DELTA_CANARY = "SYNTHETIC_STREAM_DELTA_CANARY"
_FINISH_REASON_CANARY = "SYNTHETIC_STREAM_FINISH_REASON_CANARY"
_EXCEPTION_CANARY = "SYNTHETIC_STREAM_EXCEPTION_CANARY"
_BLOCK = object()


class SyntheticStatusError(Exception):
    """Fake upstream error carrying the integer status each stream retry loop reads."""

    def __init__(self, status_code: int) -> None:
        super().__init__(_EXCEPTION_CANARY)
        # qwen/litellm classify on `status_code`; gemini's stream loop reads `code`.
        self.status_code = status_code
        self.code = status_code


class SyntheticStream:
    def __init__(self, steps: list[Any], *, check_no_active_span: bool = False) -> None:
        self.steps = iter(steps)
        self.check_no_active_span = check_no_active_span
        self.closed = 0
        self.read_started = asyncio.Event()
        self.release = asyncio.Event()

    def __aiter__(self) -> SyntheticStream:
        return self

    async def __anext__(self) -> Any:
        self._assert_no_active_span()
        try:
            item = next(self.steps)
        except StopIteration:
            raise StopAsyncIteration from None
        if item is _BLOCK:
            self.read_started.set()
            await self.release.wait()
            raise StopAsyncIteration
        if isinstance(item, BaseException):
            raise item
        return item

    async def aclose(self) -> None:
        self._assert_no_active_span()
        self.closed += 1

    async def close(self) -> None:
        await self.aclose()

    def _assert_no_active_span(self) -> None:
        if self.check_no_active_span:
            assert not trace.get_current_span().is_recording()


@pytest.fixture(
    params=[qwen_client, gemini_client, litellm_client], ids=["qwen", "gemini", "litellm"]
)
def provider(request: Any, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    module = request.param
    retry = SimpleNamespace(max_retries=3, retry_delay=0.0)
    monkeypatch.setattr(module, "settings", SimpleNamespace(retry=retry))
    create = AsyncMock()
    client: Any
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
        monkeypatch.setattr(module.litellm, "num_retries", 0)
        monkeypatch.setattr(module.litellm, "model_fallbacks", None)
    client.model = "synthetic-model"
    return SimpleNamespace(module=module, client=client, create=create, retry=retry)


def _chunk(module: Any, content: str | None, *, finish_reason: str | None = None) -> Any:
    if module is gemini_client:
        return SimpleNamespace(
            text=content,
            content=_CONTENT_CANARY,
            finish_reason=finish_reason,
        )
    return SimpleNamespace(
        content=_CONTENT_CANARY,
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ],
    )


def _retry_spans(telemetry: Telemetry) -> list[Any]:
    return [span for span in telemetry.finished_spans if span.name == Operation.RETRY.value]


async def _consume(provider: SimpleNamespace) -> list[str]:
    return [
        delta
        async for delta in provider.client.a_generate_stream(
            _PROMPT_CANARY, context=_CONTEXT_CANARY
        )
    ]


def _assert_retry_metadata(telemetry: Telemetry, error_codes: list[ErrorCode]) -> None:
    spans = _retry_spans(telemetry)
    assert len(spans) == len(error_codes)
    attributes = [dict(span.attributes or {}) for span in spans]
    assert [item["telemetry.retry_count"] for item in attributes] == list(
        range(1, len(error_codes) + 1)
    )
    assert [item["telemetry.error_code"] for item in attributes] == [
        code.value for code in error_codes
    ]
    for span, item in zip(spans, attributes, strict=True):
        assert item["telemetry.operation"] == Operation.RETRY.value
        assert item["telemetry.outcome"] == "retry"
        assert isinstance(item["telemetry.retry_count"], int)
        assert not isinstance(item["telemetry.retry_count"], bool)
        assert uuid.UUID(item["telemetry.attempt_id"]).version == 4
        assert str(uuid.UUID(item["telemetry.attempt_id"])) == item["telemetry.attempt_id"]
        assert set(item) == {
            "telemetry.operation",
            "telemetry.attempt_id",
            "telemetry.retry_count",
            "telemetry.outcome",
            "telemetry.error_code",
        }
        assert span.status.status_code.name == "ERROR"
        assert not span.events
        assert span.end_time is not None

    serialized = json.dumps(
        [
            {"name": span.name, "attributes": dict(span.attributes or {}), "events": span.events}
            for span in spans
        ]
    )
    assert all(
        canary not in serialized
        for canary in (
            _PROMPT_CANARY,
            _CONTEXT_CANARY,
            _CONTENT_CANARY,
            _DELTA_CANARY,
            _FINISH_REASON_CANARY,
            _EXCEPTION_CANARY,
        )
    )


@pytest.mark.asyncio
async def test_actual_stream_retries_emit_finished_safe_transition_spans(
    provider: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    streams = [
        SyntheticStream([TimeoutError(_EXCEPTION_CANARY)], check_no_active_span=True),
        SyntheticStream([httpx.ConnectError(_EXCEPTION_CANARY)], check_no_active_span=True),
        SyntheticStream(
            [
                _chunk(provider.module, _DELTA_CANARY),
                _chunk(provider.module, None, finish_reason=_FINISH_REASON_CANARY),
            ],
            check_no_active_span=True,
        ),
    ]

    next_stream: int = 0

    async def create(**kwargs: Any) -> SyntheticStream:
        nonlocal next_stream
        index = next_stream
        next_stream += 1
        if index:
            assert streams[index - 1].closed == 1
            assert all(span.end_time is not None for span in _retry_spans(telemetry))
        return streams[index]

    provider.create.side_effect = create
    start_span = provider.module.start_telemetry_operation

    def checked_start(operation: Any, **metadata: Any) -> Any:
        # The transition span starts synchronously after the failed attempt's
        # usage finalization; the existing fire-and-forget cleanup task closes
        # the stream during the backoff yield, so only already-opened retry
        # spans must be finished here.
        assert all(span.end_time is not None for span in _retry_spans(telemetry))
        return start_span(operation, **metadata)

    monkeypatch.setattr(provider.module, "start_telemetry_operation", checked_start)
    original_sleep = asyncio.sleep
    sleep_calls = 0

    async def checked_sleep(delay: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        spans = _retry_spans(telemetry)
        assert spans
        assert all(span.end_time is not None for span in spans)
        await original_sleep(0)

    monkeypatch.setattr(provider.module.asyncio, "sleep", checked_sleep)
    with use_telemetry(telemetry):
        assert await _consume(provider) == [_DELTA_CANARY]

    assert provider.create.await_count == 3
    assert [stream.closed for stream in streams] == [1, 1, 1]
    assert sleep_calls == 2
    _assert_retry_metadata(telemetry, [ErrorCode.TIMEOUT, ErrorCode.UPSTREAM])


@pytest.mark.asyncio
async def test_first_attempt_success_emits_no_retry_span(provider: SimpleNamespace) -> None:
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    stream = SyntheticStream(
        [
            _chunk(provider.module, _DELTA_CANARY),
            _chunk(provider.module, None, finish_reason=_FINISH_REASON_CANARY),
        ],
        check_no_active_span=True,
    )
    provider.create.return_value = stream

    with use_telemetry(telemetry):
        assert await _consume(provider) == [_DELTA_CANARY]

    assert provider.create.await_count == 1
    assert stream.closed == 1
    assert _retry_spans(telemetry) == []


@pytest.mark.asyncio
async def test_permanent_stream_failure_emits_no_retry_span(provider: SimpleNamespace) -> None:
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    error = RuntimeError(_EXCEPTION_CANARY)
    stream = SyntheticStream([error], check_no_active_span=True)
    provider.create.return_value = stream

    with use_telemetry(telemetry), pytest.raises(RuntimeError) as raised:
        await _consume(provider)

    assert raised.value is error
    assert provider.create.await_count == 1
    assert stream.closed == 1
    assert _retry_spans(telemetry) == []


@pytest.mark.asyncio
async def test_exhaustion_preserves_final_error_and_marks_only_actual_retry(
    provider: SimpleNamespace,
) -> None:
    provider.retry.max_retries = 2
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    errors = [TimeoutError(_EXCEPTION_CANARY), httpx.ConnectError(_EXCEPTION_CANARY)]
    streams = [SyntheticStream([error], check_no_active_span=True) for error in errors]
    provider.create.side_effect = streams

    with use_telemetry(telemetry), pytest.raises(httpx.ConnectError) as raised:
        await _consume(provider)

    assert raised.value is errors[-1]
    assert provider.create.await_count == 2
    assert [stream.closed for stream in streams] == [1, 1]
    _assert_retry_metadata(telemetry, [ErrorCode.TIMEOUT])


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 503])
async def test_status_code_transient_stream_failure_retries_then_exhausts(
    provider: SimpleNamespace, status_code: int
) -> None:
    provider.retry.max_retries = 2
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    errors = [SyntheticStatusError(status_code), SyntheticStatusError(status_code)]
    streams = [SyntheticStream([error], check_no_active_span=True) for error in errors]
    provider.create.side_effect = streams

    with use_telemetry(telemetry), pytest.raises(SyntheticStatusError) as raised:
        await _consume(provider)

    assert raised.value is errors[-1]
    assert provider.create.await_count == 2
    assert [stream.closed for stream in streams] == [1, 1]
    _assert_retry_metadata(telemetry, [ErrorCode.UPSTREAM])


@pytest.mark.asyncio
async def test_non_transient_status_code_stream_failure_emits_no_retry_span(
    provider: SimpleNamespace,
) -> None:
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    error = SyntheticStatusError(400)
    stream = SyntheticStream([error], check_no_active_span=True)
    provider.create.return_value = stream

    with use_telemetry(telemetry), pytest.raises(SyntheticStatusError) as raised:
        await _consume(provider)

    assert raised.value is error
    assert provider.create.await_count == 1
    assert stream.closed == 1
    assert _retry_spans(telemetry) == []


@pytest.mark.asyncio
async def test_stream_retry_is_a_noop_without_active_telemetry_owner(
    provider: SimpleNamespace,
) -> None:
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    streams = [
        SyntheticStream([TimeoutError(_EXCEPTION_CANARY)], check_no_active_span=True),
        SyntheticStream([_chunk(provider.module, _DELTA_CANARY)], check_no_active_span=True),
    ]
    provider.create.side_effect = streams

    with use_telemetry(None):
        assert await _consume(provider) == [_DELTA_CANARY]

    assert provider.create.await_count == 2
    assert [stream.closed for stream in streams] == [1, 1]
    assert telemetry.finished_spans == ()


@pytest.mark.asyncio
async def test_consumer_backpressure_does_not_spend_stream_attempt_budget(
    provider: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provider.module, "DEFAULT_TIMEOUT", 0.01)
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    stream = SyntheticStream(
        [_chunk(provider.module, "first"), _chunk(provider.module, "second")],
        check_no_active_span=True,
    )
    provider.create.return_value = stream
    generator = provider.client.a_generate_stream(_PROMPT_CANARY)

    with use_telemetry(telemetry):
        try:
            assert await anext(generator) == "first"
            await asyncio.sleep(0.03)
            assert await anext(generator) == "second"
            with pytest.raises(StopAsyncIteration):
                await anext(generator)
        finally:
            await generator.aclose()

    assert provider.create.await_count == 1
    assert stream.closed == 1
    assert _retry_spans(telemetry) == []


@pytest.mark.asyncio
async def test_stream_cancellation_closes_attempt_without_retry_span(
    provider: SimpleNamespace,
) -> None:
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    stream = SyntheticStream([_chunk(provider.module, "prefix"), _BLOCK], check_no_active_span=True)
    provider.create.return_value = stream
    generator = provider.client.a_generate_stream(_PROMPT_CANARY)

    with use_telemetry(telemetry):
        assert await anext(generator) == "prefix"
        read_task = asyncio.create_task(anext(generator))
        try:
            await asyncio.wait_for(stream.read_started.wait(), timeout=2)
            read_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await read_task
        finally:
            stream.release.set()
            if not read_task.done():
                read_task.cancel()
                await asyncio.gather(read_task, return_exceptions=True)
            await generator.aclose()

    assert provider.create.await_count == 1
    assert stream.closed == 1
    assert _retry_spans(telemetry) == []
