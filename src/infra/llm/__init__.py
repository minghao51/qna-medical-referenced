from src.config import settings
from src.infra.llm.gemini_client import GeminiClient
from src.infra.llm.litellm_client import LiteLLMClient
from src.infra.llm.qwen_client import QwenClient
from src.infra.llm.qwen_client import get_client as _qwen_get_client


def get_client():
    if settings.llm.provider == "litellm":
        return LiteLLMClient()
    if settings.llm.provider == "gemini":
        return GeminiClient()
    return _qwen_get_client()


__all__ = ["GeminiClient", "LiteLLMClient", "QwenClient", "get_client"]
