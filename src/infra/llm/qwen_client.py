"""Alibaba Qwen LLM client with retry logic and prompt engineering.

This module provides a wrapper around the Qwen API (via Dashscope's OpenAI-compatible
endpoint) with automatic retry logic for handling transient failures. It constructs
prompts with system instructions optimized for medical information queries.

Key features:
    - Exponential backoff retry strategy for API resilience
    - Medical-domain prompt engineering with safety constraints
    - Configurable model selection (qwen3.5-flash, qwen3.5-plus, qwen-plus, etc.)
    - Temperature and token configuration for consistent responses

Example:
    Generate a response with context:
        from src.infra.llm.qwen_client import get_client
        client = get_client()
        response = client.generate(
            prompt="What is a normal cholesterol level?",
            context="Reference information from medical guidelines..."
        )
"""

import asyncio
import logging
import time
import uuid
from contextlib import nullcontext
from typing import Any, TypeVar, cast

import anyio
import httpx
from openai import APIConnectionError, AsyncOpenAI, OpenAI
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


def retry_with_backoff(func):
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        max_attempts = max(1, int(settings.retry.max_retries))
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
                    return func(*args, **kwargs)
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
                    if transient:
                        logger.error("Qwen request failed after %s attempts", max_attempts)
                    raise
                delay = min(DEFAULT_TIMEOUT, max(0.0, settings.retry.retry_delay) * (2**attempt))
                logger.warning(
                    "Qwen request attempt %s failed; retrying in %ss", attempt + 1, delay
                )
                time.sleep(delay)
        raise RuntimeError("Unexpected error in retry logic")

    return wrapper


class QwenClient:
    def __init__(self, model: str | None = None):
        self.client = OpenAI(
            api_key=settings.llm.dashscope_api_key.get_secret_value(),
            base_url=settings.llm.qwen_base_url,
            timeout=DEFAULT_TIMEOUT,
        )
        self.async_client = AsyncOpenAI(
            api_key=settings.llm.dashscope_api_key.get_secret_value(),
            base_url=settings.llm.qwen_base_url,
            timeout=DEFAULT_TIMEOUT,
        )
        self.model = model or settings.llm.model_name

    async def aclose(self) -> None:
        """Close both SDK clients; keep async cleanup on its owning loop."""
        try:
            await self.async_client.close()
        finally:
            await asyncio.to_thread(self.client.close)

    @retry_with_backoff
    def generate(self, prompt: str, context: str = "") -> str:
        with usage_call(provider="openai") as usage:
            response = self.client.with_options(
                max_retries=0, timeout=DEFAULT_TIMEOUT
            ).chat.completions.create(
                model=self.model,
                messages=build_medical_messages(prompt, context),
                temperature=0.7,
                max_tokens=2048,
            )
            if usage is not None:
                usage.record_response(response)

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Empty response from Qwen API")
        return str(content)

    async def a_generate(self, prompt: str, context: str = "") -> str:
        max_attempts = max(1, int(settings.retry.max_retries))
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
                        with usage_call(provider="openai") as usage:
                            response = await self.async_client.with_options(
                                max_retries=0, timeout=DEFAULT_TIMEOUT
                            ).chat.completions.create(
                                model=self.model,
                                messages=build_medical_messages(prompt, context),
                                temperature=0.7,
                                max_tokens=2048,
                            )
                            if usage is not None:
                                usage.record_response(response)
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("Empty response from Qwen API")
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
                    if transient:
                        logger.error("Qwen async request failed after %s attempts", max_attempts)
                    raise
                delay = min(DEFAULT_TIMEOUT, max(0.0, settings.retry.retry_delay) * (2**attempt))
                logger.warning(
                    "Qwen async request attempt %s failed; retrying in %ss", attempt + 1, delay
                )
                await asyncio.sleep(delay)
        raise RuntimeError("Unexpected error in async retry logic")

    async def a_generate_stream(self, prompt: str, context: str = ""):
        # max_retries is the existing total-attempt setting, not extra retries.
        max_attempts = max(1, int(settings.retry.max_retries))
        emitted = False
        loop = asyncio.get_running_loop()
        for attempt in range(max_attempts):
            stream = None
            usage = begin_usage_call(provider="openai")
            stream_completed = False
            try:
                try:
                    deadline = loop.time() + DEFAULT_TIMEOUT
                    async with asyncio.timeout_at(deadline):
                        stream = await self.async_client.with_options(
                            max_retries=0, timeout=DEFAULT_TIMEOUT
                        ).chat.completions.create(
                            model=self.model,
                            messages=build_medical_messages(prompt, context),
                            temperature=0.7,
                            max_tokens=2048,
                            stream=True,
                            stream_options={"include_usage": True},
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
                                cleanup_task = asyncio.ensure_future(stream.close())
                            except Exception:
                                logger.warning("Qwen stream cleanup failed")
                            else:
                                try:
                                    await asyncio.shield(cleanup_task)
                                except asyncio.CancelledError:
                                    with anyio.CancelScope(shield=True):
                                        while not cleanup_task.done():
                                            try:
                                                await asyncio.shield(cleanup_task)
                                            except asyncio.CancelledError:
                                                continue
                                            except Exception:
                                                break
                                    if not cleanup_task.cancelled():
                                        try:
                                            cleanup_task.result()
                                        except Exception:
                                            logger.warning("Qwen stream cleanup failed")
                                    raise
                                except Exception:
                                    logger.warning("Qwen stream cleanup failed")
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
                logger.warning("Qwen stream attempt %s failed; retrying in %ss", attempt + 1, delay)
                await asyncio.sleep(delay)

    def generate_structured(self, prompt: str, response_model: type[T], context: str = "") -> T:
        @retry_with_backoff
        def _inner() -> T:
            with usage_call(provider="openai") as usage:
                response = self.client.with_options(
                    max_retries=0, timeout=DEFAULT_TIMEOUT
                ).chat.completions.create(
                    model=self.model,
                    messages=build_medical_messages(prompt, context),
                    temperature=0.7,
                    max_tokens=2048,
                    response_format={"type": "json_object"},
                )
                if usage is not None:
                    usage.record_response(response)
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from Qwen API")
            return response_model.model_validate_json(content)

        return cast(T, _inner())

    async def a_generate_structured(
        self, prompt: str, response_model: type[T], context: str = ""
    ) -> T:
        max_attempts = max(1, int(settings.retry.max_retries))
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
                        with usage_call(provider="openai") as usage:
                            response = await self.async_client.with_options(
                                max_retries=0, timeout=DEFAULT_TIMEOUT
                            ).chat.completions.create(
                                model=self.model,
                                messages=build_medical_messages(prompt, context),
                                temperature=0.7,
                                max_tokens=2048,
                                response_format={"type": "json_object"},
                            )
                            if usage is not None:
                                usage.record_response(response)
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("Empty response from Qwen API")
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
                    if transient:
                        logger.error(
                            "Qwen async structured request failed after %s attempts", max_attempts
                        )
                    raise
                delay = min(DEFAULT_TIMEOUT, max(0.0, settings.retry.retry_delay) * (2**attempt))
                logger.warning(
                    "Qwen async structured request attempt %s failed; retrying in %ss",
                    attempt + 1,
                    delay,
                )
                await asyncio.sleep(delay)
        raise RuntimeError("Unexpected error in async structured retry logic")


def get_client() -> QwenClient:
    return QwenClient()
