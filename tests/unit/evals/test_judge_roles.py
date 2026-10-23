from types import SimpleNamespace
from unittest.mock import MagicMock

import litellm
import pytest
from pydantic import SecretStr, ValidationError

from src.config.settings import LLMConfig, settings
from src.evals import deepeval_models


def _set_credentials(monkeypatch, *, qwen: str, gemini: str, litellm_key: str) -> None:
    monkeypatch.setattr(settings.llm, "dashscope_api_key", SecretStr(qwen))
    monkeypatch.setattr(settings.llm, "gemini_api_key", SecretStr(gemini))
    monkeypatch.setattr(settings.llm, "openrouter_api_key", SecretStr(litellm_key))


def _patch_fake_constructors(monkeypatch) -> None:
    for provider, class_name in (
        ("qwen", "QwenModel"),
        ("gemini", "GeminiJudgeModel"),
        ("litellm", "LiteLLMJudgeModel"),
    ):
        monkeypatch.setattr(
            deepeval_models,
            class_name,
            lambda model, provider=provider: SimpleNamespace(provider=provider, model=model),
        )


def test_judge_provider_defaults_to_legacy_generation_provider():
    config = LLMConfig()

    assert config.provider == "qwen"
    assert config.judge_provider is None
    assert config.model_name == "qwen3.5-flash"


@pytest.mark.parametrize(
    ("generation_provider", "judge_provider"),
    [
        ("qwen", "gemini"),
        ("gemini", "qwen"),
        ("litellm", "gemini"),
        ("qwen", "litellm"),
        ("qwen", None),
        ("gemini", None),
        ("litellm", None),
    ],
)
@pytest.mark.parametrize(
    ("factory", "model_suffix"),
    [(deepeval_models.get_light_model, "light"), (deepeval_models.get_heavy_model, "heavy")],
)
def test_judge_factory_selects_independent_or_inherited_provider(
    monkeypatch, generation_provider, judge_provider, factory, model_suffix
):
    selected_provider = judge_provider or generation_provider
    _set_credentials(
        monkeypatch,
        qwen="synthetic-qwen-credential" if selected_provider == "qwen" else "",
        gemini="synthetic-gemini-credential" if selected_provider == "gemini" else "",
        litellm_key="synthetic-litellm-credential" if selected_provider == "litellm" else "",
    )
    _patch_fake_constructors(monkeypatch)
    monkeypatch.setattr(settings.llm, "provider", generation_provider)
    monkeypatch.setattr(settings.llm, "judge_provider", judge_provider)
    monkeypatch.setattr(settings.llm, f"judge_model_{model_suffix}", f"qwen-{model_suffix}")
    monkeypatch.setattr(
        settings.llm, f"judge_model_{model_suffix}_gemini", f"gemini-{model_suffix}"
    )
    monkeypatch.setattr(
        settings.llm, f"judge_model_{model_suffix}_litellm", f"openrouter/litellm-{model_suffix}"
    )

    assert deepeval_models.resolve_judge_provider() == selected_provider

    model = factory()
    expected_model = {
        "qwen": f"qwen-{model_suffix}",
        "gemini": f"gemini-{model_suffix}",
        "litellm": f"openrouter/litellm-{model_suffix}",
    }[selected_provider]
    assert model.provider == selected_provider
    assert model.model == expected_model


@pytest.mark.parametrize(
    ("selected_provider", "generation_provider", "setting_name"),
    [
        ("qwen", "gemini", "APP__LLM__DASHSCOPE_API_KEY"),
        ("gemini", "qwen", "APP__LLM__GEMINI_API_KEY"),
        ("litellm", "qwen", "APP__LLM__OPENROUTER_API_KEY"),
    ],
)
def test_factory_requires_only_selected_judge_credential(
    monkeypatch, selected_provider, generation_provider, setting_name
):
    secret = "synthetic-credential-must-not-be-reported"
    _set_credentials(
        monkeypatch,
        qwen="" if selected_provider == "qwen" else secret,
        gemini="" if selected_provider == "gemini" else secret,
        litellm_key="" if selected_provider == "litellm" else secret,
    )
    monkeypatch.setattr(settings.llm, "provider", generation_provider)
    monkeypatch.setattr(settings.llm, "judge_provider", selected_provider)
    for class_name in ("QwenModel", "GeminiJudgeModel", "LiteLLMJudgeModel"):
        monkeypatch.setattr(
            deepeval_models,
            class_name,
            lambda model: pytest.fail("judge constructor called without its selected credential"),
        )

    with pytest.raises(ValueError) as exc_info:
        deepeval_models.get_light_model()

    assert setting_name in str(exc_info.value)
    assert secret not in str(exc_info.value)


def test_unknown_selected_judge_provider_fails_without_fallback(monkeypatch):
    monkeypatch.setattr(settings.llm, "provider", "qwen")
    monkeypatch.setattr(settings.llm, "judge_provider", "unsupported")

    with pytest.raises(ValueError, match="Unsupported judge provider"):
        deepeval_models.get_heavy_model()


def test_unknown_inherited_generation_provider_fails_without_qwen_fallback(monkeypatch):
    monkeypatch.setattr(settings.llm, "provider", "unsupported")
    monkeypatch.setattr(settings.llm, "judge_provider", None)

    with pytest.raises(ValueError, match="Unsupported judge provider"):
        deepeval_models.resolve_judge_provider()


def test_llm_config_rejects_unknown_selected_judge_provider():
    with pytest.raises(ValidationError):
        LLMConfig(judge_provider="unsupported")


def test_litellm_judge_passes_configured_key_per_call(monkeypatch):
    credential = "synthetic-litellm-credential"
    monkeypatch.setattr(settings.llm, "openrouter_api_key", SecretStr(credential))
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])
    completion = MagicMock(return_value=response)
    monkeypatch.setattr(litellm, "completion", completion)

    model = deepeval_models.LiteLLMJudgeModel("openrouter/test-model")
    assert model.generate("judge prompt") == "ok"
    assert completion.call_args.kwargs["api_key"] == credential


def test_pydantic_ai_judge_factory_selects_wrapper_and_judge_models(monkeypatch):
    monkeypatch.setattr(settings.llm, "provider", "qwen")
    monkeypatch.setattr(settings.llm, "judge_provider", "pydantic-ai")
    monkeypatch.setattr(settings.llm, "pydantic_ai_api_key", SecretStr("synthetic-judge-key"))
    monkeypatch.setattr(settings.llm, "judge_model_light_pydantic_ai", "judge-light-model")
    monkeypatch.setattr(settings.llm, "judge_model_heavy_pydantic_ai", "judge-heavy-model")
    monkeypatch.setattr(
        deepeval_models,
        "QwenModel",
        lambda model: pytest.fail("qwen judge must not be constructed for a pydantic-ai judge"),
    )
    from src.evals import pydantic_ai_judge

    constructed: list[str] = []

    def _fake_judge(model: str):
        constructed.append(model)
        return SimpleNamespace(provider="pydantic-ai", model=model, usage_role="judge")

    monkeypatch.setattr(pydantic_ai_judge, "PydanticAIJudgeModel", _fake_judge)

    light = deepeval_models.get_light_model()
    heavy = deepeval_models.get_heavy_model()

    assert constructed == ["judge-light-model", "judge-heavy-model"]
    assert light.usage_role == "judge_light"
    assert heavy.usage_role == "judge_heavy"


def test_pydantic_ai_judge_requires_its_own_credential(monkeypatch):
    monkeypatch.setattr(settings.llm, "provider", "qwen")
    monkeypatch.setattr(settings.llm, "judge_provider", "pydantic-ai")
    monkeypatch.setattr(settings.llm, "pydantic_ai_api_key", SecretStr("   "))

    with pytest.raises(ValueError) as exc_info:
        deepeval_models.get_light_model()

    assert "APP__LLM__PYDANTIC_AI_API_KEY" in str(exc_info.value)
