from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import litellm
import pytest

from src.evals.deepeval_models import LiteLLMJudgeModel, get_heavy_model, get_light_model


def _response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_litellm_judge_model_init():
    model = LiteLLMJudgeModel("openrouter/google/gemma-4-31b-it")
    assert model.model == "openrouter/google/gemma-4-31b-it"
    assert model.model_name == "openrouter/google/gemma-4-31b-it"


def test_litellm_judge_model_implements_interface():
    model = LiteLLMJudgeModel("openrouter/test-model")
    assert hasattr(model, "load_model")
    assert hasattr(model, "generate")
    assert hasattr(model, "a_generate")
    assert hasattr(model, "get_model_name")
    assert model.supports_temperature() is True
    assert model.supports_json_mode() is False
    assert model.supports_structured_outputs() is False


def test_litellm_judge_model_generate(monkeypatch):
    model = LiteLLMJudgeModel("openrouter/test-model")
    mock_completion = MagicMock(return_value=_response("judge verdict"))
    monkeypatch.setattr(litellm, "completion", mock_completion)

    result = model.generate("Rate this answer")
    assert result == "judge verdict"
    call_kwargs = mock_completion.call_args
    assert call_kwargs.kwargs["temperature"] == 0.0


@pytest.mark.asyncio
async def test_litellm_judge_model_a_generate(monkeypatch):
    model = LiteLLMJudgeModel("openrouter/test-model")
    mock_acompletion = AsyncMock(return_value=_response("async verdict"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await model.a_generate("Rate this answer")
    assert result == "async verdict"


def test_get_light_model_returns_litellm_when_configured(monkeypatch):
    monkeypatch.setattr("src.evals.deepeval_models.settings.llm_provider", "litellm")
    monkeypatch.setattr(
        "src.evals.deepeval_models.settings.judge_model_light_litellm",
        "google/gemma-4-31b-it",
    )

    model = get_light_model()
    assert isinstance(model, LiteLLMJudgeModel)
    assert model.model == "openrouter/google/gemma-4-31b-it"


def test_get_heavy_model_returns_litellm_when_configured(monkeypatch):
    monkeypatch.setattr("src.evals.deepeval_models.settings.llm_provider", "litellm")
    monkeypatch.setattr(
        "src.evals.deepeval_models.settings.judge_model_heavy_litellm",
        "google/gemma-4-31b-it",
    )

    model = get_heavy_model()
    assert isinstance(model, LiteLLMJudgeModel)
    assert model.model == "openrouter/google/gemma-4-31b-it"


def test_get_light_model_returns_qwen_by_default():
    from src.evals.deepeval_models import QwenModel

    model = get_light_model()
    assert isinstance(model, QwenModel)


def test_get_heavy_model_returns_qwen_by_default():
    from src.evals.deepeval_models import QwenModel

    model = get_heavy_model()
    assert isinstance(model, QwenModel)


def test_litellm_judge_model_preserves_openrouter_prefix(monkeypatch):
    monkeypatch.setattr("src.evals.deepeval_models.settings.llm_provider", "litellm")
    monkeypatch.setattr(
        "src.evals.deepeval_models.settings.judge_model_light_litellm",
        "openrouter/google/gemma-4-31b-it",
    )

    model = get_light_model()
    assert model.model == "openrouter/google/gemma-4-31b-it"
