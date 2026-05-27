import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar, cast

from google import genai
from google.genai import types
from pydantic import BaseModel

from src.config import settings
from src.infra.llm.prompts import build_medical_messages

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_TIMEOUT = 30.0


def _to_gemini_contents(prompt: str, context: str) -> list[dict[str, Any]]:
    messages = build_medical_messages(prompt, context)
    return [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in messages]


class GeminiClient:
    def __init__(self, model: str | None = None):
        api_key = settings.llm.gemini_api_key.get_secret_value()
        self.client = genai.Client(api_key=api_key)
        self.model = model or settings.llm.gemini_model_name

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
        last_exception: Exception | None = None
        contents = _to_gemini_contents(prompt, context)
        for attempt in range(_retry_max_retries()):
            try:
                stream = await self.client.aio.models.generate_content_stream(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=2048,
                    ),
                )
                async for chunk in stream:
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as e:
                last_exception = e
                if attempt < _retry_max_retries() - 1:
                    delay = settings.retry.retry_delay * (2**attempt)
                    logger.warning(
                        "Stream attempt %s failed: %s. Retrying in %ss...", attempt + 1, e, delay
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("All %s stream attempts failed: %s", _retry_max_retries(), e)
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in stream retry logic")

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
        response = self.client.models.generate_content(
            model=self.model,
            contents=_to_gemini_contents(prompt, context),
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=2048,
            ),
        )
        if response.text is None:
            raise ValueError("Empty response from Gemini API")
        return str(response.text)

    async def _generate_async(self, prompt: str, context: str) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=_to_gemini_contents(prompt, context),
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=2048,
            ),
        )
        if response.text is None:
            raise ValueError("Empty response from Gemini API")
        return str(response.text)

    def _generate_structured_sync(self, prompt: str, response_model: type[T], context: str) -> T:
        response = self.client.models.generate_content(
            model=self.model,
            contents=_to_gemini_contents(prompt, context),
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=2048,
                response_mime_type="application/json",
                response_schema=response_model,
            ),
        )
        parsed = response.parsed
        if parsed is None:
            raise ValueError("Empty structured response from Gemini API")
        return cast(T, parsed)

    async def _generate_structured_async(
        self, prompt: str, response_model: type[T], context: str
    ) -> T:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=_to_gemini_contents(prompt, context),
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=2048,
                response_mime_type="application/json",
                response_schema=response_model,
            ),
        )
        parsed = response.parsed
        if parsed is None:
            raise ValueError("Empty structured response from Gemini API")
        return cast(T, parsed)


def _retry_max_retries() -> int:
    return int(settings.retry.max_retries)


def _retry_sync(fn: Callable[[], str], *, label: str = "call") -> str:
    max_retries = _retry_max_retries()
    last_exception: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = settings.retry.retry_delay * (2**attempt)
                logger.warning("Attempt %s failed: %s. Retrying in %ss...", attempt + 1, e, delay)
                time.sleep(delay)
            else:
                logger.error("All %s attempts failed: %s", max_retries, e)
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected error in retry logic")


async def _retry_async(fn: Callable[[], Coroutine[Any, Any, str]], *, label: str = "call") -> str:
    max_retries = _retry_max_retries()
    last_exception: Exception | None = None
    for attempt in range(max_retries):
        try:
            return await fn()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = settings.retry.retry_delay * (2**attempt)
                logger.warning(
                    "Async attempt %s failed: %s. Retrying in %ss...", attempt + 1, e, delay
                )
                await asyncio.sleep(delay)
            else:
                logger.error("All %s async attempts failed: %s", max_retries, e)
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected error in async retry logic")


def _retry_sync_structured[T: BaseModel](fn: Callable[[], T], *, label: str = "call") -> T:
    max_retries = _retry_max_retries()
    last_exception: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = settings.retry.retry_delay * (2**attempt)
                logger.warning("Attempt %s failed: %s. Retrying in %ss...", attempt + 1, e, delay)
                time.sleep(delay)
            else:
                logger.error("All %s attempts failed: %s", max_retries, e)
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected error in retry logic")


async def _retry_async_structured[T: BaseModel](
    fn: Callable[[], Coroutine[Any, Any, T]], *, label: str = "call"
) -> T:
    max_retries = _retry_max_retries()
    last_exception: Exception | None = None
    for attempt in range(max_retries):
        try:
            return await fn()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = settings.retry.retry_delay * (2**attempt)
                logger.warning(
                    "Async attempt %s failed: %s. Retrying in %ss...", attempt + 1, e, delay
                )
                await asyncio.sleep(delay)
            else:
                logger.error("All %s async attempts failed: %s", max_retries, e)
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected error in async retry logic")
