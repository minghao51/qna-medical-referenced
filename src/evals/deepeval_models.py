"""DeepEval-compatible model wrappers for Qwen and LiteLLM providers.

Provides judge models for DeepEval's LLM-as-a-judge framework with
provider selection based on the LLM_PROVIDER setting.
"""

import os
from typing import Any

from deepeval.models import DeepEvalBaseLLM
from openai import AsyncOpenAI, OpenAI

from src.config.settings import settings


class QwenModel(DeepEvalBaseLLM):
    """Qwen model wrapper for DeepEval.

    Implements the DeepEvalBaseLLM interface to allow Qwen models
    to be used as evaluators in DeepEval metrics.

    Attributes:
        model: Model identifier (e.g., "qwen3.5-flash", "qwen3.5-35b-a3b")
        client: OpenAI-compatible client pointing to Dashscope API
    """

    model: str  # type: ignore[assignment]

    def __init__(self, model: str):
        self.model = model
        self.model_name = model
        self.client = OpenAI(
            api_key=settings.llm.dashscope_api_key,
            base_url=settings.llm.qwen_base_url,
            timeout=settings.deepeval.deepeval_metric_timeout_seconds,
            max_retries=2,
        )
        self.async_client = AsyncOpenAI(
            api_key=settings.llm.dashscope_api_key,
            base_url=settings.llm.qwen_base_url,
            timeout=settings.deepeval.deepeval_metric_timeout_seconds,
            max_retries=2,
        )

    def load_model(self) -> "QwenModel":
        return self

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.llm.judge_temperature,
            max_tokens=settings.llm.judge_max_tokens,
        )
        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
        return ""

    async def a_generate(self, prompt: str) -> str:
        response = await self.async_client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.llm.judge_temperature,
            max_tokens=settings.llm.judge_max_tokens,
        )
        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
        return ""

    def get_model_name(self) -> str:
        return self.model_name

    def supports_json_mode(self) -> bool:
        return False

    def supports_structured_outputs(self) -> bool:
        return False

    def supports_temperature(self) -> bool:
        return True


class LiteLLMJudgeModel(DeepEvalBaseLLM):
    """LiteLLM/OpenRouter model wrapper for DeepEval.

    Implements the DeepEvalBaseLLM interface using litellm.completion()
    and litellm.acompletion() for provider-agnostic evaluation.
    """

    model: str  # type: ignore[assignment]

    def __init__(self, model: str):
        self.model = model
        self.model_name = model
        if settings.llm.openrouter_api_key and not os.environ.get("OPENROUTER_API_KEY"):
            os.environ["OPENROUTER_API_KEY"] = settings.llm.openrouter_api_key

    def load_model(self) -> "LiteLLMJudgeModel":
        return self

    def generate(self, prompt: str) -> str:
        import litellm

        response: Any = litellm.completion(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.llm.judge_temperature,
            max_tokens=settings.llm.judge_max_tokens,
        )
        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
        return ""

    async def a_generate(self, prompt: str) -> str:
        import litellm

        response: Any = await litellm.acompletion(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.llm.judge_temperature,
            max_tokens=settings.llm.judge_max_tokens,
        )
        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
        return ""

    def get_model_name(self) -> str:
        return self.model_name

    def supports_json_mode(self) -> bool:
        return False

    def supports_structured_outputs(self) -> bool:
        return False

    def supports_temperature(self) -> bool:
        return True


def get_light_model() -> QwenModel | LiteLLMJudgeModel:
    if settings.llm.provider == "litellm":
        model_name = settings.llm.judge_model_light_litellm
        if not model_name.startswith("openrouter/"):
            model_name = f"openrouter/{model_name}"
        return LiteLLMJudgeModel(model_name)
    return QwenModel(settings.llm.judge_model_light)


def get_heavy_model() -> QwenModel | LiteLLMJudgeModel:
    if settings.llm.provider == "litellm":
        model_name = settings.llm.judge_model_heavy_litellm
        if not model_name.startswith("openrouter/"):
            model_name = f"openrouter/{model_name}"
        return LiteLLMJudgeModel(model_name)
    return QwenModel(settings.llm.judge_model_heavy)
