import asyncio
import logging
import os
import time

import litellm

from src.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_DELAY = 1.0

SYSTEM_PROMPT = "You are a medical information assistant that provides educational information about lab tests and health screening results."

USER_PROMPT_TEMPLATE = """You are a helpful medical information assistant.
Based on the following reference information, answer the user's question.

Reference Information:
{context}

User Question: {prompt}

Instructions:
- Provide evidence-based information
- Always recommend consulting with a healthcare provider
- Include relevant reference ranges when applicable
- Mention potential controversies or limitations of tests
- Do not provide medical diagnoses
"""


def _resolve_model() -> str:
    if settings.litellm_model:
        return settings.litellm_model
    return f"openrouter/{settings.openrouter_model}"


def _ensure_api_key() -> None:
    if settings.openrouter_api_key and not os.environ.get("OPENROUTER_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key


def _build_messages(prompt: str, context: str = "") -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(context=context, prompt=prompt)},
    ]


class LiteLLMClient:
    def __init__(self, model: str | None = None):
        self.model = model or _resolve_model()
        _ensure_api_key()

    def generate(self, prompt: str, context: str = "") -> str:
        last_exception: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = litellm.completion(
                    model=self.model,
                    messages=_build_messages(prompt, context),
                    temperature=0.7,
                    max_tokens=2048,
                )
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("Empty response from LiteLLM")
                return content
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    delay = INITIAL_DELAY * (2**attempt)
                    logger.warning("Attempt %s failed: %s. Retrying in %ss...", attempt + 1, e, delay)
                    time.sleep(delay)
                else:
                    logger.error("All %s attempts failed: %s", MAX_RETRIES, e)
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in retry logic")

    async def a_generate(self, prompt: str, context: str = "") -> str:
        last_exception: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await litellm.acompletion(
                    model=self.model,
                    messages=_build_messages(prompt, context),
                    temperature=0.7,
                    max_tokens=2048,
                )
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("Empty response from LiteLLM")
                return content
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    delay = INITIAL_DELAY * (2**attempt)
                    logger.warning("Async attempt %s failed: %s. Retrying in %ss...", attempt + 1, e, delay)
                    await asyncio.sleep(delay)
                else:
                    logger.error("All %s async attempts failed: %s", MAX_RETRIES, e)
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in async retry logic")

    async def a_generate_stream(self, prompt: str, context: str = ""):
        last_exception: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                stream = await litellm.acompletion(
                    model=self.model,
                    messages=_build_messages(prompt, context),
                    temperature=0.7,
                    max_tokens=2048,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                return
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    delay = INITIAL_DELAY * (2**attempt)
                    logger.warning("Stream attempt %s failed: %s. Retrying in %ss...", attempt + 1, e, delay)
                    await asyncio.sleep(delay)
                else:
                    logger.error("All %s stream attempts failed: %s", MAX_RETRIES, e)
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in stream retry logic")
