from src.config import settings
from src.infra.llm.gemini_client import GeminiClient
from src.infra.llm.litellm_client import LiteLLMClient
from src.infra.llm.pydantic_ai_client import PydanticAIClient
from src.infra.llm.qwen_client import QwenClient
from src.infra.llm.qwen_client import get_client as _qwen_get_client


def get_client(*, provider: str | None = None, model: str | None = None):
    """Construct an existing provider client, preserving configured defaults."""
    selected_provider = settings.llm.provider if provider is None else provider
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ValueError("LLM model must be a non-empty identifier when provided")
    if selected_provider == "litellm":
        return LiteLLMClient() if model is None else LiteLLMClient(model=model)
    if selected_provider == "gemini":
        return GeminiClient() if model is None else GeminiClient(model=model)
    if selected_provider == "pydantic-ai":
        return PydanticAIClient() if model is None else PydanticAIClient(model=model)
    if selected_provider == "qwen":
        if model is None:
            return _qwen_get_client()
        return QwenClient(model=model)
    raise ValueError(f"Unsupported LLM provider: {selected_provider!r}")


__all__ = ["GeminiClient", "LiteLLMClient", "PydanticAIClient", "QwenClient", "get_client"]
