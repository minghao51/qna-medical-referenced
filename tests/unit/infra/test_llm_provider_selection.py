from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.config.settings import LLMConfig


@pytest.mark.parametrize("provider", ["qwen", "gemini", "litellm"])
def test_llm_config_accepts_supported_providers(provider):
    assert LLMConfig(provider=provider).provider == provider


def test_llm_config_rejects_unknown_provider():
    with pytest.raises(ValidationError):
        LLMConfig(provider="unsupported-provider")


def test_client_factory_rejects_unknown_provider_without_qwen_fallback(monkeypatch):
    from src.infra import llm

    monkeypatch.setattr(
        llm,
        "settings",
        SimpleNamespace(llm=SimpleNamespace(provider="unsupported-provider")),
    )
    monkeypatch.setattr(
        llm,
        "_qwen_get_client",
        lambda: pytest.fail("unknown provider must not fall back to Qwen"),
    )

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        llm.get_client()


@pytest.mark.parametrize(
    ("provider", "client_name"),
    [("qwen", "QwenClient"), ("gemini", "GeminiClient"), ("litellm", "LiteLLMClient")],
)
def test_client_factory_accepts_explicit_supported_provider_and_model(
    monkeypatch, provider, client_name
):
    from src.infra import llm

    monkeypatch.setattr(
        llm,
        "settings",
        SimpleNamespace(llm=SimpleNamespace(provider="unsupported-default")),
    )
    monkeypatch.setattr(llm, client_name, lambda *, model: (provider, model))
    monkeypatch.setattr(
        llm,
        "_qwen_get_client",
        lambda: pytest.fail("explicit model must use the supported model constructor"),
    )

    assert llm.get_client(provider=provider, model="explicit-model") == (
        provider,
        "explicit-model",
    )


@pytest.mark.parametrize(
    ("provider", "client_name"),
    [("qwen", None), ("gemini", "GeminiClient"), ("litellm", "LiteLLMClient")],
)
def test_client_factory_preserves_configured_provider_defaults(monkeypatch, provider, client_name):
    from src.infra import llm

    expected = object()
    monkeypatch.setattr(llm, "settings", SimpleNamespace(llm=SimpleNamespace(provider=provider)))
    if client_name is None:
        monkeypatch.setattr(llm, "_qwen_get_client", lambda: expected)
    else:
        monkeypatch.setattr(llm, client_name, lambda: expected)

    assert llm.get_client() is expected


def test_client_factory_rejects_empty_explicit_model(monkeypatch):
    from src.infra import llm

    monkeypatch.setattr(llm, "settings", SimpleNamespace(llm=SimpleNamespace(provider="qwen")))

    with pytest.raises(ValueError, match="non-empty"):
        llm.get_client(model="  ")


def test_client_factory_rejects_unknown_explicit_provider(monkeypatch):
    from src.infra import llm

    monkeypatch.setattr(llm, "settings", SimpleNamespace(llm=SimpleNamespace(provider="qwen")))
    monkeypatch.setattr(
        llm,
        "_qwen_get_client",
        lambda: pytest.fail("unknown explicit provider must not use configured Qwen"),
    )

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        llm.get_client(provider="unsupported")
