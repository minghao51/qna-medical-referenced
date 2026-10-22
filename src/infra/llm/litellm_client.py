import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import nullcontext
from typing import Any, TypeVar

import anyio
import httpx
import litellm
from openai import APIConnectionError
from pydantic import BaseModel

from src.config import settings
from src.infra.llm.prompts import build_medical_messages
from src.infra.telemetry import (
    ErrorCode,
    Operation,
    start_telemetry_operation,
    telemetry_operation,
)
from src.infra.usage import begin_usage_call, finish_usage_call, usage_call

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


def _resolve_model() -> str:
    if settings.llm.litellm_model:
        return str(settings.llm.litellm_model)
    return f"openrouter/{settings.llm.openrouter_model!s}"


class LiteLLMClient:
    def __init__(self, model: str | None = None):
        self.model = model or _resolve_model()
        self._api_key = settings.llm.openrouter_api_key.get_secret_value() or None

    def generate(self, prompt: str, context: str = "") -> str:
        if litellm.model_fallbacks is not None or litellm.num_retries:
            raise RuntimeError("Global LiteLLM retries/fallbacks are unsupported")
        return _retry_sync(
            lambda: litellm.completion(
                model=self.model,
                messages=build_medical_messages(prompt, context),
                temperature=0.7,
                max_tokens=2048,
                timeout=DEFAULT_TIMEOUT,
                max_retries=0,
                num_retries=0,
                api_key=self._api_key,
            ),
            label="LiteLLM",
        )

    async def a_generate(self, prompt: str, context: str = "") -> str:
        if litellm.model_fallbacks is not None or litellm.num_retries:
            raise RuntimeError("Global LiteLLM retries/fallbacks are unsupported")
        return await _retry_async(
            lambda: litellm.acompletion(
                model=self.model,
                messages=build_medical_messages(prompt, context),
                temperature=0.7,
                max_tokens=2048,
                timeout=DEFAULT_TIMEOUT,
                max_retries=0,
                num_retries=0,
                api_key=self._api_key,
            ),
            label="LiteLLM",
        )

    async def a_generate_stream(self, prompt: str, context: str = ""):
        # Installed LiteLLM can inherit process-global fallback/retry policies.
        # Do not mutate globals or silently route outside this stream contract.
        if litellm.model_fallbacks is not None or litellm.num_retries:
            raise RuntimeError("Global LiteLLM retries/fallbacks are unsupported for streaming")
        # max_retries is the existing total-attempt setting, not extra retries.
        max_attempts = max(1, int(settings.retry.max_retries))
        emitted = False
        loop = asyncio.get_running_loop()
        for attempt in range(max_attempts):
            stream = None
            usage = begin_usage_call(provider="litellm")
            stream_completed = False
            try:
                try:
                    deadline = loop.time() + DEFAULT_TIMEOUT
                    async with asyncio.timeout_at(deadline):
                        stream = await litellm.acompletion(
                            model=self.model,
                            messages=build_medical_messages(prompt, context),
                            temperature=0.7,
                            max_tokens=2048,
                            stream=True,
                            stream_options={"include_usage": True},
                            timeout=DEFAULT_TIMEOUT,
                            max_retries=0,
                            num_retries=0,
                            api_key=self._api_key,
                        )
                    iterator = aiter(stream)
                    while True:
                        if loop.time() >= deadline:
                            raise TimeoutError("Stream attempt deadline exceeded")
                        try:
                            # Never keep a timeout scope active across a yield.
                            async with asyncio.timeout_at(deadline):
                                chunk = await anext(iterator)
                        except StopAsyncIteration:
                            stream_completed = True
                            break
                        if usage is not None:
                            usage.record_response(chunk)
                        content = chunk.choices[0].delta.content if chunk.choices else None
                        if content:
                            emitted = True
                            paused_at = loop.time()
                            yield content
                            # Consumer backpressure is not upstream work.
                            deadline += loop.time() - paused_at
                    return
                finally:
                    try:
                        if stream is not None:
                            try:
                                close_task = asyncio.ensure_future(stream.aclose())
                            except Exception:
                                logger.warning("LiteLLM stream cleanup failed")
                            else:
                                try:
                                    await asyncio.shield(close_task)
                                except asyncio.CancelledError:
                                    with anyio.CancelScope(shield=True):
                                        while not close_task.done():
                                            try:
                                                await asyncio.shield(close_task)
                                            except asyncio.CancelledError:
                                                if close_task.cancelled():
                                                    break
                                                continue
                                            except Exception:
                                                break
                                    if not close_task.cancelled():
                                        try:
                                            close_task.result()
                                        except Exception:
                                            logger.warning("LiteLLM stream cleanup failed")
                                    raise
                                except Exception:
                                    logger.warning("LiteLLM stream cleanup failed")
                    finally:
                        finish_usage_call(usage, failed=not stream_completed)
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                transient = isinstance(
                    exc,
                    (
                        TimeoutError,
                        APIConnectionError,
                        httpx.TimeoutException,
                        httpx.NetworkError,
                        httpx.RemoteProtocolError,
                    ),
                ) or (isinstance(status, int) and (status in {408, 429} or 500 <= status < 600))
                if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
                    error_code = ErrorCode.TIMEOUT
                elif transient:
                    error_code = ErrorCode.UPSTREAM
                else:
                    error_code = ErrorCode.INTERNAL
                if emitted or not transient or attempt == max_attempts - 1:
                    raise
                retry_span = start_telemetry_operation(
                    Operation.RETRY,
                    attempt_id=str(uuid.uuid4()),
                    retry_count=attempt + 1,
                )
                retry_span.finish(outcome="retry", error_code=error_code)
                delay = min(DEFAULT_TIMEOUT, max(0.0, settings.retry.retry_delay) * (2**attempt))
                logger.warning(
                    "LiteLLM stream attempt %s failed; retrying in %ss", attempt + 1, delay
                )
                await asyncio.sleep(delay)

    def generate_structured(self, prompt: str, response_model: type[T], context: str = "") -> T:
        if litellm.model_fallbacks is not None or litellm.num_retries:
            raise RuntimeError("Global LiteLLM retries/fallbacks are unsupported")
        return _retry_sync_structured(
            lambda: litellm.completion(
                model=self.model,
                messages=build_medical_messages(prompt, context),
                temperature=0.7,
                max_tokens=2048,
                timeout=DEFAULT_TIMEOUT,
                max_retries=0,
                num_retries=0,
                api_key=self._api_key,
                response_format={"type": "json_object"},
            ),
            response_model=response_model,
            label="LiteLLM",
        )

    async def a_generate_structured(
        self, prompt: str, response_model: type[T], context: str = ""
    ) -> T:
        if litellm.model_fallbacks is not None or litellm.num_retries:
            raise RuntimeError("Global LiteLLM retries/fallbacks are unsupported")
        return await _retry_async_structured(
            lambda: litellm.acompletion(
                model=self.model,
                messages=build_medical_messages(prompt, context),
                temperature=0.7,
                max_tokens=2048,
                timeout=DEFAULT_TIMEOUT,
                max_retries=0,
                num_retries=0,
                api_key=self._api_key,
                response_format={"type": "json_object"},
            ),
            response_model=response_model,
            label="LiteLLM",
        )


def _retry_max_retries() -> int:
    return max(1, int(settings.retry.max_retries))


def _retry_sync(fn: Callable[[], Any], *, label: str = "call") -> str:
    max_attempts = _retry_max_retries()
    for attempt in range(max_attempts):
        try:
            retry_span = (
                telemetry_operation(
                    Operation.RETRY,
                    attempt_id=str(uuid.uuid4()),
                    retry_count=attempt,
                )
                if attempt > 0
                else nullcontext()
            )
            with retry_span:
                with usage_call(provider="litellm") as usage:
                    response = fn()
                    if usage is not None:
                        usage.record_response(response)
            content = response.choices[0].message.content
            if content is None:
                raise ValueError(f"Empty response from {label}")
            return str(content)
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            transient = isinstance(
                exc,
                (
                    TimeoutError,
                    APIConnectionError,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                ),
            ) or (isinstance(status, int) and (status in {408, 429} or 500 <= status < 600))
            if not transient or attempt == max_attempts - 1:
                logger.error("%s request failed on attempt %s", label, attempt + 1)
                raise
            delay = min(DEFAULT_TIMEOUT, max(0.0, settings.retry.retry_delay) * (2**attempt))
            logger.warning("%s attempt %s failed; retrying in %ss", label, attempt + 1, delay)
            time.sleep(delay)
    raise RuntimeError("Unexpected error in retry logic")


async def _retry_async(fn: Callable[[], Awaitable[Any]], *, label: str = "call") -> str:
    max_attempts = _retry_max_retries()
    for attempt in range(max_attempts):
        try:
            retry_span = (
                telemetry_operation(
                    Operation.RETRY,
                    attempt_id=str(uuid.uuid4()),
                    retry_count=attempt,
                )
                if attempt > 0
                else nullcontext()
            )
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                with retry_span:
                    with usage_call(provider="litellm") as usage:
                        response = await fn()
                        if usage is not None:
                            usage.record_response(response)
            content = response.choices[0].message.content
            if content is None:
                raise ValueError(f"Empty response from {label}")
            return str(content)
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            transient = isinstance(
                exc,
                (
                    TimeoutError,
                    APIConnectionError,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                ),
            ) or (isinstance(status, int) and (status in {408, 429} or 500 <= status < 600))
            if not transient or attempt == max_attempts - 1:
                logger.error("%s async request failed on attempt %s", label, attempt + 1)
                raise
            delay = min(DEFAULT_TIMEOUT, max(0.0, settings.retry.retry_delay) * (2**attempt))
            logger.warning("%s async attempt %s failed; retrying in %ss", label, attempt + 1, delay)
            await asyncio.sleep(delay)
    raise RuntimeError("Unexpected error in retry logic")


def _retry_sync_structured[T: BaseModel](
    fn: Callable[[], Any], *, response_model: type[T], label: str = "call"
) -> T:
    max_attempts = _retry_max_retries()
    for attempt in range(max_attempts):
        try:
            retry_span = (
                telemetry_operation(
                    Operation.RETRY,
                    attempt_id=str(uuid.uuid4()),
                    retry_count=attempt,
                )
                if attempt > 0
                else nullcontext()
            )
            with retry_span:
                with usage_call(provider="litellm") as usage:
                    response = fn()
                    if usage is not None:
                        usage.record_response(response)
            content = response.choices[0].message.content
            if content is None:
                raise ValueError(f"Empty response from {label}")
            return response_model.model_validate_json(content)
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            transient = isinstance(
                exc,
                (
                    TimeoutError,
                    APIConnectionError,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                ),
            ) or (isinstance(status, int) and (status in {408, 429} or 500 <= status < 600))
            if not transient or attempt == max_attempts - 1:
                logger.error("%s structured request failed on attempt %s", label, attempt + 1)
                raise
            delay = min(DEFAULT_TIMEOUT, max(0.0, settings.retry.retry_delay) * (2**attempt))
            logger.warning("%s attempt %s failed; retrying in %ss", label, attempt + 1, delay)
            time.sleep(delay)
    raise RuntimeError("Unexpected error in retry logic")


async def _retry_async_structured[T: BaseModel](
    fn: Callable[[], Awaitable[Any]], *, response_model: type[T], label: str = "call"
) -> T:
    max_attempts = _retry_max_retries()
    for attempt in range(max_attempts):
        try:
            retry_span = (
                telemetry_operation(
                    Operation.RETRY,
                    attempt_id=str(uuid.uuid4()),
                    retry_count=attempt,
                )
                if attempt > 0
                else nullcontext()
            )
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                with retry_span:
                    with usage_call(provider="litellm") as usage:
                        response = await fn()
                        if usage is not None:
                            usage.record_response(response)
            content = response.choices[0].message.content
            if content is None:
                raise ValueError(f"Empty response from {label}")
            return response_model.model_validate_json(content)
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            transient = isinstance(
                exc,
                (
                    TimeoutError,
                    APIConnectionError,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                ),
            ) or (isinstance(status, int) and (status in {408, 429} or 500 <= status < 600))
            if not transient or attempt == max_attempts - 1:
                logger.error("%s async structured request failed on attempt %s", label, attempt + 1)
                raise
            delay = min(DEFAULT_TIMEOUT, max(0.0, settings.retry.retry_delay) * (2**attempt))
            logger.warning("%s async attempt %s failed; retrying in %ss", label, attempt + 1, delay)
            await asyncio.sleep(delay)
    raise RuntimeError("Unexpected error in retry logic")
