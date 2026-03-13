"""Qwen model wrapper for DeepEval integration.

This module provides a DeepEval-compatible wrapper for Qwen models,
enabling use of Alibaba's Qwen LLMs as judges in DeepEval's LLM-as-a-judge
framework. Supports model tiering for cost optimization.
"""

from deepeval.models import DeepEvalBaseLLM
from openai import OpenAI

from src.config.settings import settings


class QwenModel(DeepEvalBaseLLM):
    """Qwen model wrapper for DeepEval.

    Implements the DeepEvalBaseLLM interface to allow Qwen models
    to be used as evaluators in DeepEval metrics.

    Attributes:
        model: Model identifier (e.g., "qwen3.5-flash", "qwen3.5-35b-a3b")
        client: OpenAI-compatible client pointing to Dashscope API
    """

    def __init__(self, model: str):
        """Initialize the Qwen model wrapper.

        Args:
            model: Model identifier string
        """
        self.model = model
        self.client = OpenAI(api_key=settings.dashscope_api_key, base_url=settings.qwen_base_url)

    def load_model(self):
        """Load and return the model.

        Returns:
            Model identifier string
        """
        return self.model

    def generate(self, prompt: str) -> str:
        """Generate text synchronously.

        Args:
            prompt: Input prompt for the model

        Returns:
            Generated text response
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.judge_temperature,
        )
        if response.choices and response.choices[0].message.content:
            return response.choices[0].message.content
        return ""

    async def a_generate(self, prompt: str) -> str:
        """Generate text asynchronously.

        Args:
            prompt: Input prompt for the model

        Returns:
            Generated text response
        """
        # For now, wrap sync call. Can be optimized later with async client.
        return self.generate(prompt)

    def get_model_name(self) -> str:
        """Get the model name.

        Returns:
            Model identifier string
        """
        return self.model


def get_light_model() -> QwenModel:
    """Factory function for lightweight judge model.

    Returns:
        QwenModel instance configured with lightweight model (qwen3.5-35b-a3b)
    """
    return QwenModel(settings.judge_model_light)


def get_heavy_model() -> QwenModel:
    """Factory function for heavyweight judge model.

    Returns:
        QwenModel instance configured with heavyweight model (qwen3.5-flash)
    """
    return QwenModel(settings.judge_model_heavy)
