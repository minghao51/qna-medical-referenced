"""DeepEval-compatible model wrappers for Qwen, LiteLLM, and Gemini providers.

Provides judge models for DeepEval's LLM-as-a-judge framework with
provider selection based on the LLM_PROVIDER setting.
"""

import os
from typing import Any

from openai import AsyncOpenAI, OpenAI

from src.config.settings import settings

try:
    from deepeval.models import DeepEvalBaseLLM
except ModuleNotFoundError:

    class DeepEvalBaseLLM:  # type: ignore[no-redef]
        """Fallback base class when deepeval extra is not installed."""


if "DEEPEVAL_TELEMETRY_OPT_OUT" not in os.environ:
    os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"


class QwenModel(DeepEvalBaseLLM):
    """Qwen model wrapper for DeepEval.

    Implements the DeepEvalBaseLLM interface to allow Qwen models
    to be used as evaluators in DeepEval metrics.

    Attributes:
        model: Model identifier (e.g., "qwen3.5-flash", "qwen3.5-35b-a3b")
        client: OpenAI-compatible client pointing to Dashscope API
    """

    model: str

    def __init__(self, model: str):
        self.model = model
        self.model_name = model
        self.client = OpenAI(
            api_key=settings.llm.dashscope_api_key.get_secret_value(),
            base_url=settings.llm.qwen_base_url,
            timeout=settings.deepeval.deepeval_metric_timeout_seconds,
            max_retries=2,
        )
        self.async_client = AsyncOpenAI(
            api_key=settings.llm.dashscope_api_key.get_secret_value(),
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

    model: str

    def __init__(self, model: str):
        self.model = model
        self.model_name = model
        _openrouter_key = settings.llm.openrouter_api_key.get_secret_value()
        if _openrouter_key and not os.environ.get("OPENROUTER_API_KEY"):
            os.environ.setdefault("OPENROUTER_API_KEY", _openrouter_key)

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


class GeminiJudgeModel(DeepEvalBaseLLM):
    """Google Gemini model wrapper for DeepEval.

    Implements the DeepEvalBaseLLM interface using the google-genai SDK
    for Gemini-based evaluation.
    """

    model: str

    def __init__(self, model: str):
        from google import genai

        self.model = model
        self.model_name = model
        self.client = genai.Client(api_key=settings.llm.gemini_api_key.get_secret_value())

    def load_model(self) -> "GeminiJudgeModel":
        return self

    def generate(self, prompt: str) -> str:
        from google.genai import types

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=settings.llm.judge_temperature,
                max_output_tokens=settings.llm.judge_max_tokens,
            ),
        )
        if response.text:
            return str(response.text)
        return ""

    async def a_generate(self, prompt: str) -> str:
        from google.genai import types

        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=settings.llm.judge_temperature,
                max_output_tokens=settings.llm.judge_max_tokens,
            ),
        )
        if response.text:
            return str(response.text)
        return ""

    def get_model_name(self) -> str:
        return self.model_name

    def supports_json_mode(self) -> bool:
        return True

    def supports_structured_outputs(self) -> bool:
        return True

    def supports_temperature(self) -> bool:
        return True


def get_light_model() -> QwenModel | LiteLLMJudgeModel | GeminiJudgeModel:
    if settings.llm.provider == "litellm":
        model_name = settings.llm.judge_model_light_litellm
        if not model_name.startswith("openrouter/"):
            model_name = f"openrouter/{model_name}"
        return LiteLLMJudgeModel(model_name)
    if settings.llm.provider == "gemini":
        return GeminiJudgeModel(settings.llm.judge_model_light_gemini)
    return QwenModel(settings.llm.judge_model_light)


def get_heavy_model() -> QwenModel | LiteLLMJudgeModel | GeminiJudgeModel:
    if settings.llm.provider == "litellm":
        model_name = settings.llm.judge_model_heavy_litellm
        if not model_name.startswith("openrouter/"):
            model_name = f"openrouter/{model_name}"
        return LiteLLMJudgeModel(model_name)
    if settings.llm.provider == "gemini":
        return GeminiJudgeModel(settings.llm.judge_model_heavy_gemini)
    return QwenModel(settings.llm.judge_model_heavy)
