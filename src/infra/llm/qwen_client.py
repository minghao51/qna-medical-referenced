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
from typing import Any, TypeVar, cast

from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel

from src.config import settings
from src.infra.llm.prompts import build_medical_messages

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


def retry_with_backoff(func):
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        max_retries = settings.retry.max_retries
        initial_delay = settings.retry.retry_delay
        last_exception: Exception | None = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = initial_delay * (2**attempt)
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed: {e}")
        if last_exception:
            raise last_exception
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

    @retry_with_backoff
    def generate(self, prompt: str, context: str = "") -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=build_medical_messages(prompt, context),
            temperature=0.7,
            max_tokens=2048,
        )

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Empty response from Qwen API")
        return str(content)

    async def a_generate(self, prompt: str, context: str = "") -> str:
        max_retries = settings.retry.max_retries
        initial_delay = settings.retry.retry_delay
        last_exception: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = await self.async_client.chat.completions.create(
                    model=self.model,
                    messages=build_medical_messages(prompt, context),
                    temperature=0.7,
                    max_tokens=2048,
                )

                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("Empty response from Qwen API")
                return str(content)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = initial_delay * (2**attempt)
                    logger.warning(
                        "Async attempt %s failed: %s. Retrying in %ss...",
                        attempt + 1,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("All %s async attempts failed: %s", max_retries, e)
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in async retry logic")

    async def a_generate_stream(self, prompt: str, context: str = ""):
        max_retries = settings.retry.max_retries
        initial_delay = settings.retry.retry_delay
        last_exception: Exception | None = None
        for attempt in range(max_retries):
            try:
                stream = await self.async_client.chat.completions.create(
                    model=self.model,
                    messages=build_medical_messages(prompt, context),
                    temperature=0.7,
                    max_tokens=2048,
                    stream=True,
                )

                stream_iter = stream if hasattr(stream, "__aiter__") else None
                if stream_iter is None:
                    raise RuntimeError("Expected async stream response from Qwen API")
                async for chunk in stream_iter:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = initial_delay * (2**attempt)
                    logger.warning(
                        "Stream attempt %s failed: %s. Retrying in %ss...",
                        attempt + 1,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("All %s stream attempts failed: %s", max_retries, e)
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in stream retry logic")

    def generate_structured(self, prompt: str, response_model: type[T], context: str = "") -> T:
        @retry_with_backoff
        def _inner() -> T:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=build_medical_messages(prompt, context),
                temperature=0.7,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from Qwen API")
            return response_model.model_validate_json(content)

        return cast(T, _inner())

    async def a_generate_structured(
        self, prompt: str, response_model: type[T], context: str = ""
    ) -> T:
        max_retries = settings.retry.max_retries
        initial_delay = settings.retry.retry_delay
        last_exception: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = await self.async_client.chat.completions.create(
                    model=self.model,
                    messages=build_medical_messages(prompt, context),
                    temperature=0.7,
                    max_tokens=2048,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("Empty response from Qwen API")
                return response_model.model_validate_json(content)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = initial_delay * (2**attempt)
                    logger.warning(
                        "Async structured attempt %s failed: %s. Retrying in %ss...",
                        attempt + 1,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("All %s async structured attempts failed: %s", max_retries, e)
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in async structured retry logic")


def get_client() -> QwenClient:
    return QwenClient()
