import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from contextlib import asynccontextmanager, nullcontext
from contextvars import ContextVar
from typing import Any, TypeVar, cast

import anyio
import httpx
from google import genai
from google.genai import types
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

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")

DEFAULT_TIMEOUT = 30.0


def _to_gemini_contents(prompt: str, context: str) -> list[types.ContentDict | str]:
    messages = build_medical_messages(prompt, context)
    return [
        {
            "role": str(m["role"]),
            "parts": [{"text": str(m["content"] or "")}],
        }
        for m in messages
    ]


class GeminiClient:
    def __init__(self, model: str | None = None):
        api_key = settings.llm.gemini_api_key.get_secret_value()
        self._pending_httpx_responses: ContextVar[list[httpx.Response] | None] = ContextVar(
            f"gemini_httpx_responses_{id(self)}", default=None
        )
        async_http_client = httpx.AsyncClient(
            follow_redirects=True,
            event_hooks={"response": [self._capture_httpx_response]},
        )
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(httpx_async_client=async_http_client),
        )
        self._owned_async_http_client = async_http_client
        self.model = model or settings.llm.gemini_model_name

    async def _capture_httpx_response(self, response: httpx.Response) -> None:
        pending = self._pending_httpx_responses.get()
        if pending is not None:
            pending.append(response)

    async def _await_with_httpx_capture(
        self, awaitable: Awaitable[R], responses: list[httpx.Response]
    ) -> R:
        capture = getattr(self, "_pending_httpx_responses", None)
        if capture is None:
            return await awaitable
        token = capture.set(responses)
        try:
            return await awaitable
        finally:
            capture.reset(token)

    @asynccontextmanager
    async def _own_httpx_responses(self) -> AsyncIterator[list[httpx.Response]]:
        responses: list[httpx.Response] = []
        try:
            yield responses
        finally:
            if responses:

                async def close_responses() -> None:
                    results = await asyncio.gather(
                        *(response.aclose() for response in responses), return_exceptions=True
                    )
                    cancellation = next(
                        (
                            result
                            for result in results
                            if isinstance(result, asyncio.CancelledError)
                        ),
                        None,
                    )
                    if cancellation is not None:
                        raise cancellation
                    if any(isinstance(result, Exception) for result in results):
                        logger.warning("Gemini HTTP response cleanup failed")

                cleanup = asyncio.create_task(close_responses())
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    with anyio.CancelScope(shield=True):
                        while not cleanup.done():
                            try:
                                await asyncio.shield(cleanup)
                            except asyncio.CancelledError:
                                continue
                            except Exception:
                                break
                    if not cleanup.cancelled():
                        try:
                            cleanup.result()
                        except Exception:
                            logger.warning("Gemini HTTP response cleanup failed")
                    raise
                except Exception:
                    logger.warning("Gemini HTTP response cleanup failed")

    async def aclose(self) -> None:
        """Close owned async HTTP and SDK transports, then the sync SDK client."""
        cleanup_errors: list[BaseException] = []
        try:
            await self.client.aio.aclose()
        except BaseException as exc:
            cleanup_errors.append(exc)

        owned_async_http_client = getattr(self, "_owned_async_http_client", None)
        if owned_async_http_client is not None:
            try:
                await owned_async_http_client.aclose()
            except BaseException as exc:
                cleanup_errors.append(exc)

        try:
            await asyncio.to_thread(self.client.close)
        except BaseException as exc:
            cleanup_errors.append(exc)

        if cleanup_errors:
            cancellation = next(
                (error for error in cleanup_errors if isinstance(error, asyncio.CancelledError)),
                None,
            )
            if cancellation is not None:
                for error in cleanup_errors:
                    if error is not cancellation:
                        cancellation.add_note(
                            f"Additional Gemini cleanup failure: {type(error).__name__}"
                        )
                raise cancellation
            if len(cleanup_errors) == 1:
                raise cleanup_errors[0]
            raise BaseExceptionGroup("Gemini client cleanup failed", cleanup_errors)

    def generate(self, prompt: str, context: str = "") -> str:
        return _retry_sync(
            lambda: self._generate_sync(prompt, context),
            label="Gemini",
        )

    async def a_generate(self, prompt: str, context: str = "") -> str:
        return await _retry_async(
            lambda: self._generate_async(prompt, context),
            label="Gemini",
        )

    async def a_generate_stream(self, prompt: str, context: str = ""):
        contents = cast(Any, _to_gemini_contents(prompt, context))
        # max_retries is the existing total-attempt setting, not extra retries.
        max_attempts = max(1, int(settings.retry.max_retries))
        emitted = False
        loop = asyncio.get_running_loop()
        for attempt in range(max_attempts):
            stream = None
            usage = begin_usage_call(provider="gemini")
            stream_completed = False
            try:
                async with self._own_httpx_responses() as responses:
                    try:
                        deadline = loop.time() + DEFAULT_TIMEOUT
                        async with asyncio.timeout_at(deadline):
                            stream = await self._await_with_httpx_capture(
                                self.client.aio.models.generate_content_stream(
                                    model=self.model,
                                    contents=contents,
                                    config=types.GenerateContentConfig(
                                        temperature=0.7,
                                        max_output_tokens=2048,
                                        http_options=types.HttpOptions(
                                            timeout=int(DEFAULT_TIMEOUT * 1000),
                                            retry_options=types.HttpRetryOptions(attempts=1),
                                        ),
                                    ),
                                ),
                                responses,
                            )
                        iterator = aiter(stream)
                        while True:
                            if loop.time() >= deadline:
                                raise TimeoutError("Stream attempt deadline exceeded")
                            try:
                                # Never keep a timeout scope active across a yield.
                                async with asyncio.timeout_at(deadline):
                                    chunk = await self._await_with_httpx_capture(
                                        anext(iterator), responses
                                    )
                            except StopAsyncIteration:
                                stream_completed = True
                                break
                            if usage is not None:
                                usage.record_response(chunk)
                            content = chunk.text
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
                                close = getattr(stream, "aclose", None)
                                if close is not None:
                                    try:
                                        cleanup_task = asyncio.ensure_future(close())
                                    except Exception:
                                        logger.warning("Gemini stream cleanup failed")
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
                                                    logger.warning("Gemini stream cleanup failed")
                                            raise
                                        except Exception:
                                            logger.warning("Gemini stream cleanup failed")
                        finally:
                            finish_usage_call(usage, failed=not stream_completed)
            except Exception as exc:
                status = getattr(exc, "code", None)
                transient = isinstance(
                    exc,
                    (
                        TimeoutError,
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
                    "Gemini stream attempt %s failed; retrying in %ss", attempt + 1, delay
                )
                await asyncio.sleep(delay)

    def generate_structured(self, prompt: str, response_model: type[T], context: str = "") -> T:
        return _retry_sync_structured(
            lambda: self._generate_structured_sync(prompt, response_model, context),
            label="Gemini",
        )

    async def a_generate_structured(
        self, prompt: str, response_model: type[T], context: str = ""
    ) -> T:
        return await _retry_async_structured(
            lambda: self._generate_structured_async(prompt, response_model, context),
            label="Gemini",
        )

    def _generate_sync(self, prompt: str, context: str) -> str:
        contents = cast(Any, _to_gemini_contents(prompt, context))
        with usage_call(provider="gemini") as usage:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                    http_options=types.HttpOptions(
                        timeout=int(DEFAULT_TIMEOUT * 1000),
                        retry_options=types.HttpRetryOptions(attempts=1),
                    ),
                ),
            )
            if usage is not None:
                usage.record_response(response)
        if response.text is None:
            raise ValueError("Empty response from Gemini API")
        return str(response.text)

    async def _generate_async(self, prompt: str, context: str) -> str:
        contents = cast(Any, _to_gemini_contents(prompt, context))
        async with self._own_httpx_responses() as responses:
            with usage_call(provider="gemini") as usage:
                response = await self._await_with_httpx_capture(
                    self.client.aio.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            temperature=0.7,
                            max_output_tokens=2048,
                            http_options=types.HttpOptions(
                                timeout=int(DEFAULT_TIMEOUT * 1000),
                                retry_options=types.HttpRetryOptions(attempts=1),
                            ),
                        ),
                    ),
                    responses,
                )
                if usage is not None:
                    usage.record_response(response)
            if response.text is None:
                raise ValueError("Empty response from Gemini API")
            return str(response.text)

    def _generate_structured_sync(self, prompt: str, response_model: type[T], context: str) -> T:
        contents = cast(Any, _to_gemini_contents(prompt, context))
        with usage_call(provider="gemini") as usage:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                    response_mime_type="application/json",
                    response_schema=response_model,
                    http_options=types.HttpOptions(
                        timeout=int(DEFAULT_TIMEOUT * 1000),
                        retry_options=types.HttpRetryOptions(attempts=1),
                    ),
                ),
            )
            if usage is not None:
                usage.record_response(response)
        parsed = response.parsed
        if parsed is None:
            raise ValueError("Empty structured response from Gemini API")
        return cast(T, parsed)

    async def _generate_structured_async(
        self, prompt: str, response_model: type[T], context: str
    ) -> T:
        contents = cast(Any, _to_gemini_contents(prompt, context))
        async with self._own_httpx_responses() as responses:
            with usage_call(provider="gemini") as usage:
                response = await self._await_with_httpx_capture(
                    self.client.aio.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            temperature=0.7,
                            max_output_tokens=2048,
                            response_mime_type="application/json",
                            response_schema=response_model,
                            http_options=types.HttpOptions(
                                timeout=int(DEFAULT_TIMEOUT * 1000),
                                retry_options=types.HttpRetryOptions(attempts=1),
                            ),
                        ),
                    ),
                    responses,
                )
                if usage is not None:
                    usage.record_response(response)
            parsed = response.parsed
            if parsed is None:
                raise ValueError("Empty structured response from Gemini API")
            return cast(T, parsed)


def _retry_max_retries() -> int:
    return max(1, int(settings.retry.max_retries))


def _retry_sync(fn: Callable[[], str], *, label: str = "call") -> str:
    max_retries = _retry_max_retries()
    for attempt in range(max_retries):
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
                return fn()
        except Exception as exc:
            status = getattr(exc, "code", None)
            transient = isinstance(
                exc,
                (
                    TimeoutError,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                ),
            ) or (isinstance(status, int) and (status in {408, 429} or 500 <= status < 600))
            if not transient or attempt == max_retries - 1:
                logger.error("%s request failed after %s attempts", label, attempt + 1)
                raise
            delay = min(DEFAULT_TIMEOUT, max(0.0, settings.retry.retry_delay) * (2**attempt))
            logger.warning("%s attempt %s failed; retrying in %ss", label, attempt + 1, delay)
            time.sleep(delay)
    raise RuntimeError("Unexpected error in retry logic")


async def _retry_async(fn: Callable[[], Coroutine[Any, Any, str]], *, label: str = "call") -> str:
    max_retries = _retry_max_retries()
    for attempt in range(max_retries):
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
                    return await fn()
        except Exception as exc:
            status = getattr(exc, "code", None)
            transient = isinstance(
                exc,
                (
                    TimeoutError,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                ),
            ) or (isinstance(status, int) and (status in {408, 429} or 500 <= status < 600))
            if not transient or attempt == max_retries - 1:
                logger.error("%s async request failed after %s attempts", label, attempt + 1)
                raise
            delay = min(DEFAULT_TIMEOUT, max(0.0, settings.retry.retry_delay) * (2**attempt))
            logger.warning("Gemini async attempt %s failed; retrying in %ss", attempt + 1, delay)
            await asyncio.sleep(delay)
    raise RuntimeError("Unexpected error in retry logic")


def _retry_sync_structured[T: BaseModel](fn: Callable[[], T], *, label: str = "call") -> T:
    max_retries = _retry_max_retries()
    for attempt in range(max_retries):
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
                return fn()
        except Exception as exc:
            status = getattr(exc, "code", None)
            transient = isinstance(
                exc,
                (
                    TimeoutError,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                ),
            ) or (isinstance(status, int) and (status in {408, 429} or 500 <= status < 600))
            if not transient or attempt == max_retries - 1:
                logger.error("%s structured request failed after %s attempts", label, attempt + 1)
                raise
            delay = min(DEFAULT_TIMEOUT, max(0.0, settings.retry.retry_delay) * (2**attempt))
            logger.warning("%s attempt %s failed; retrying in %ss", label, attempt + 1, delay)
            time.sleep(delay)
    raise RuntimeError("Unexpected error in retry logic")


async def _retry_async_structured[T: BaseModel](
    fn: Callable[[], Coroutine[Any, Any, T]], *, label: str = "call"
) -> T:
    max_retries = _retry_max_retries()
    for attempt in range(max_retries):
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
                    return await fn()
        except Exception as exc:
            status = getattr(exc, "code", None)
            transient = isinstance(
                exc,
                (
                    TimeoutError,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                ),
            ) or (isinstance(status, int) and (status in {408, 429} or 500 <= status < 600))
            if not transient or attempt == max_retries - 1:
                logger.error(
                    "%s async structured request failed after %s attempts", label, attempt + 1
                )
                raise
            delay = min(DEFAULT_TIMEOUT, max(0.0, settings.retry.retry_delay) * (2**attempt))
            logger.warning("%s async attempt %s failed; retrying in %ss", label, attempt + 1, delay)
            await asyncio.sleep(delay)
    raise RuntimeError("Unexpected error in retry logic")
