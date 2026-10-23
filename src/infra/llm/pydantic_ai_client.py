"""Pydantic AI generation adapter for OpenCode Go (opt-in provider ``pydantic-ai``).

Implements the existing :class:`src.infra.llm.interfaces.LLMClient` protocol on
``OpenAIChatModel`` + ``OpenAIProvider`` (pydantic-ai-slim 2.31.0). Resources
(one owned ``httpx.AsyncClient``, one SDK/model instance, one ``Agent`` per
output path) are built once per client and reused for the client's lifetime;
the app lifespan closes them via :meth:`PydanticAIClient.aclose` (pydantic-ai
does not close an injected ``httpx.AsyncClient``).

Material differences and confounds versus the Qwen baseline:

- Identity headers (R05/D03): every request carries an honest application
  ``User-Agent`` (pydantic-ai otherwise sends ``pydantic-ai/<version>``) and,
  when a conversation id is bound via
  :mod:`src.infra.llm.conversation_context`, an opaque stable
  ``x-opencode-session``. Headers are request-scoped ``ModelSettings``; the
  shared client/model are never mutated. No impersonation or fabricated tool
  traffic.
- Prompt representation: agent ``instructions`` carry ``SYSTEM_PROMPT`` and the
  user prompt is ``USER_PROMPT_TEMPLATE.format(...)`` — the effective wire
  message text matches ``build_medical_messages`` exactly, but the request is
  assembled by pydantic-ai rather than the OpenAI SDK directly. Note the
  framework maps the ``max_tokens`` setting to the ``max_completion_tokens``
  wire field for models without a known profile (same number, different field
  name); the OpenCode Go gateway's acceptance of that field name is untested
  until the live smoke.
- Structured output: default mode is tool-based structured output (a
  ``final_result`` tool call) instead of Qwen's ``response_format
  json_object`` plus client-side validation. ``native-json-schema`` sends
  ``response_format {type: json_schema}``. The mode is explicit and fails
  closed; invalid model output triggers pydantic-ai's bounded output retries
  and then surfaces as an error (usage for those attempts is recorded).
- Streaming uses ``stream_text(delta=True, debounce_by=None)``: pydantic-ai
  debounces deltas by 0.1s by default, which would group SSE chunks.
- Sync methods raise ``RuntimeError`` when called inside a running event loop
  (``run_sync`` cannot run there); callers must use the async variants. This
  is a material difference from ``QwenClient``, whose sync client works from
  worker threads either way.
- Retry layering: the wrapped ``AsyncOpenAI`` client is built with
  ``max_retries=0`` and the configured timeout so the adapter's
  ``settings.retry``-bounded loop is the only retry layer and
  ``pydantic_ai_timeout_seconds`` is effective (the SDK's defaults of 2 HTTP
  retries and a 600s request timeout would otherwise multiply attempts and
  shadow the owned-client timeout). This mirrors ``QwenClient``'s per-call
  ``with_options(max_retries=0, timeout=...)`` overrides.
- OpenCode Go route support for tools/JSON-schema/SSE is documented but not
  verified until the separately approved live smoke (P4-D).
"""

import asyncio
import logging
import math
import time
import uuid
from contextlib import nullcontext
from typing import Any, TypeVar, cast

import httpx
from openai import APIConnectionError, AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent, ModelSettings, NativeOutput, ToolOutput
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from src.config import settings
from src.infra.llm.conversation_context import get_conversation_id, opaque_session_id
from src.infra.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from src.infra.telemetry import (
    ErrorCode,
    Operation,
    start_telemetry_operation,
    telemetry_operation,
)
from src.infra.usage import begin_usage_call, finish_usage_call, usage_call

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

USER_AGENT = "qna-medical-referenced/0.1.0 (pydantic-ai 2.31.0 adapter)"
SESSION_HEADER = "x-opencode-session"


def _is_transient(exc: Exception) -> bool:
    """Classify mapped pydantic-ai/openai and httpx/timeout errors like QwenClient.

    Status-bearing errors (pydantic-ai ``ModelHTTPError`` maps every ``APIStatusError``
    with status >= 400) are classified by status only: 408/429/5xx transient, other
    4xx not. ``ModelAPIError`` without a status code covers connection-level
    failures (``APIConnectionError`` mapping), which stay transient.
    """
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status in {408, 429} or 500 <= status < 600
    return isinstance(
        exc,
        (
            TimeoutError,
            APIConnectionError,
            ModelAPIError,
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
        ),
    )


class PydanticAIClient:
    def __init__(
        self,
        model: str | None = None,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
        raw_prompt: bool = False,
    ):
        resolved_model = model if model is not None else settings.llm.pydantic_ai_model
        if not isinstance(resolved_model, str) or not resolved_model.strip():
            raise ValueError("LLM model must be a non-empty identifier when provided")
        self.model = resolved_model
        # Optional overrides let the DeepEval judge wrapper reuse this adapter's
        # single retry/usage implementation with judge settings and a verbatim
        # prompt instead of the chat system prompt and user template. Overrides
        # carry the same bounds as the settings fields they replace.
        if temperature is not None and (
            isinstance(temperature, bool)
            or not isinstance(temperature, (int, float))
            or not math.isfinite(temperature)
            or not 0.0 <= temperature <= 2.0
        ):
            raise ValueError("temperature override must be a finite value from 0 through 2")
        if max_tokens is not None and (
            isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1
        ):
            raise ValueError("max_tokens override must be a positive integer")
        if timeout_seconds is not None and (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or not 0.0 < timeout_seconds <= 600.0
        ):
            raise ValueError(
                "timeout_seconds override must be a finite value above 0 and at most 600"
            )
        self._temperature = (
            settings.llm.pydantic_ai_temperature if temperature is None else float(temperature)
        )
        self._max_tokens = (
            settings.llm.pydantic_ai_max_tokens if max_tokens is None else int(max_tokens)
        )
        self._raw_prompt = bool(raw_prompt)
        self._timeout = (
            settings.llm.pydantic_ai_timeout_seconds
            if timeout_seconds is None
            else float(timeout_seconds)
        )
        # One app-owned HTTP client for the client's lifetime; closed by aclose().
        self._http_client = httpx.AsyncClient(timeout=self._timeout)
        # The documented openai_client overload keeps SDK-level HTTP retries at
        # zero so the adapter loop is the only bounded retry layer (see module
        # docstring); the SDK wraps the owned httpx client without closing it.
        self._openai_client = AsyncOpenAI(
            base_url=settings.llm.pydantic_ai_base_url,
            api_key=settings.llm.pydantic_ai_api_key.get_secret_value(),
            http_client=self._http_client,
            max_retries=0,
            timeout=self._timeout,
        )
        provider = OpenAIProvider(openai_client=self._openai_client)
        self._model = OpenAIChatModel(self.model, provider=provider)
        self._text_agent: Agent[object, str] = Agent(
            self._model, instructions=None if self._raw_prompt else SYSTEM_PROMPT
        )
        self._structured_agents: dict[tuple[type[BaseModel], str], Agent[Any, Any]] = {}

    async def aclose(self) -> None:
        """Close the owned HTTP client on its owning loop; pydantic-ai will not."""
        await self._http_client.aclose()

    def _reject_running_loop(self, method: str, async_alternative: str) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        raise RuntimeError(
            f"PydanticAIClient.{method} cannot run inside a running event loop; "
            f"use {async_alternative} instead"
        )

    def _user_prompt(self, prompt: str, context: str) -> str:
        if self._raw_prompt:
            return prompt
        return USER_PROMPT_TEMPLATE.format(context=context, prompt=prompt)

    def _request_settings(self) -> ModelSettings:
        headers = {"User-Agent": USER_AGENT}
        conversation_id = get_conversation_id()
        if conversation_id is not None:
            headers[SESSION_HEADER] = opaque_session_id(conversation_id)
        return ModelSettings(
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            extra_headers=headers,
        )

    def _structured_agent(self, response_model: type[T]) -> Agent[object, T]:
        mode = settings.llm.pydantic_ai_structured_output_mode
        cached = self._structured_agents.get((response_model, mode))
        if cached is not None:
            return cast("Agent[object, T]", cached)
        if mode == "tool":
            output_type: Any = ToolOutput(response_model)
        elif mode == "native-json-schema":
            output_type = NativeOutput([response_model])
        else:
            raise ValueError(f"Unsupported pydantic-ai structured output mode: {mode!r}")
        agent: Agent[object, T] = Agent(
            self._model, output_type=output_type, instructions=SYSTEM_PROMPT
        )
        self._structured_agents[(response_model, mode)] = cast("Agent[Any, Any]", agent)
        return agent

    def generate(self, prompt: str, context: str = "") -> str:
        self._reject_running_loop("generate", "a_generate")
        # max_retries is the existing total-attempt setting, not extra retries.
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
                    with usage_call(provider="pydantic-ai") as usage:
                        run_result = self._text_agent.run_sync(
                            self._user_prompt(prompt, context),
                            model_settings=self._request_settings(),
                        )
                        if usage is not None:
                            usage.record_response(run_result)
                output = run_result.output
                if not output:
                    raise ValueError("Empty response from Pydantic AI adapter")
                return str(output)
            except Exception as exc:
                if not _is_transient(exc) or attempt == max_attempts - 1:
                    if _is_transient(exc):
                        logger.error("Pydantic AI request failed after %s attempts", max_attempts)
                    raise
                delay = min(self._timeout, max(0.0, settings.retry.retry_delay) * (2**attempt))
                logger.warning("Pydantic AI attempt %s failed; retrying in %ss", attempt + 1, delay)
                time.sleep(delay)
        raise RuntimeError("Unexpected error in retry logic")

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
                async with asyncio.timeout(self._timeout):
                    with retry_span:
                        with usage_call(provider="pydantic-ai") as usage:
                            run_result = await self._text_agent.run(
                                self._user_prompt(prompt, context),
                                model_settings=self._request_settings(),
                            )
                            if usage is not None:
                                usage.record_response(run_result)
                output = run_result.output
                if not output:
                    raise ValueError("Empty response from Pydantic AI adapter")
                return str(output)
            except Exception as exc:
                if not _is_transient(exc) or attempt == max_attempts - 1:
                    if _is_transient(exc):
                        logger.error(
                            "Pydantic AI async request failed after %s attempts", max_attempts
                        )
                    raise
                delay = min(self._timeout, max(0.0, settings.retry.retry_delay) * (2**attempt))
                logger.warning(
                    "Pydantic AI async attempt %s failed; retrying in %ss", attempt + 1, delay
                )
                await asyncio.sleep(delay)
        raise RuntimeError("Unexpected error in async retry logic")

    async def a_generate_stream(self, prompt: str, context: str = ""):
        # max_retries is the existing total-attempt setting, not extra retries.
        max_attempts = max(1, int(settings.retry.max_retries))
        emitted = False
        for attempt in range(max_attempts):
            usage = begin_usage_call(provider="pydantic-ai")
            stream_completed = False
            try:
                async with self._text_agent.run_stream(
                    self._user_prompt(prompt, context),
                    model_settings=self._request_settings(),
                ) as result:
                    async for delta in result.stream_text(delta=True, debounce_by=None):
                        emitted = True
                        yield delta
                    if usage is not None:
                        usage.record_response(result)
                stream_completed = True
                return
            except Exception as exc:
                transient = _is_transient(exc)
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
                delay = min(self._timeout, max(0.0, settings.retry.retry_delay) * (2**attempt))
                logger.warning(
                    "Pydantic AI stream attempt %s failed; retrying in %ss", attempt + 1, delay
                )
                await asyncio.sleep(delay)
            finally:
                finish_usage_call(usage, failed=not stream_completed)

    def generate_structured(self, prompt: str, response_model: type[T], context: str = "") -> T:
        self._reject_running_loop("generate_structured", "a_generate_structured")
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
                    with usage_call(provider="pydantic-ai") as usage:
                        run_result = self._structured_agent(response_model).run_sync(
                            self._user_prompt(prompt, context),
                            model_settings=self._request_settings(),
                        )
                        if usage is not None:
                            usage.record_response(run_result)
                output: T = run_result.output
                return output
            except Exception as exc:
                if not _is_transient(exc) or attempt == max_attempts - 1:
                    if _is_transient(exc):
                        logger.error(
                            "Pydantic AI structured request failed after %s attempts",
                            max_attempts,
                        )
                    raise
                delay = min(self._timeout, max(0.0, settings.retry.retry_delay) * (2**attempt))
                logger.warning(
                    "Pydantic AI structured attempt %s failed; retrying in %ss",
                    attempt + 1,
                    delay,
                )
                time.sleep(delay)
        raise RuntimeError("Unexpected error in structured retry logic")

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
                async with asyncio.timeout(self._timeout):
                    with retry_span:
                        with usage_call(provider="pydantic-ai") as usage:
                            run_result = await self._structured_agent(response_model).run(
                                self._user_prompt(prompt, context),
                                model_settings=self._request_settings(),
                            )
                            if usage is not None:
                                usage.record_response(run_result)
                output: T = run_result.output
                return output
            except Exception as exc:
                if not _is_transient(exc) or attempt == max_attempts - 1:
                    if _is_transient(exc):
                        logger.error(
                            "Pydantic AI async structured request failed after %s attempts",
                            max_attempts,
                        )
                    raise
                delay = min(self._timeout, max(0.0, settings.retry.retry_delay) * (2**attempt))
                logger.warning(
                    "Pydantic AI async structured attempt %s failed; retrying in %ss",
                    attempt + 1,
                    delay,
                )
                await asyncio.sleep(delay)
        raise RuntimeError("Unexpected error in async structured retry logic")


def get_client() -> PydanticAIClient:
    return PydanticAIClient()
