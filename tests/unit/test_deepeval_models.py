"""Tests for QwenModel wrapper for DeepEval."""

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.slow

from src.config.settings import settings
from src.evals.deepeval_models import QwenModel, get_heavy_model, get_light_model


def _response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_qwen_model_initialization():
    model = QwenModel("qwen3.5-flash")
    assert model.model == "qwen3.5-flash"
    assert model.client is not None
    assert model.async_client is not None


def test_qwen_model_implements_required_methods():
    model = QwenModel("qwen3.5-flash")

    assert hasattr(model, "load_model")
    assert hasattr(model, "generate")
    assert hasattr(model, "a_generate")
    assert hasattr(model, "get_model_name")
    assert model.supports_temperature() is True
    assert model.supports_json_mode() is False
    assert model.supports_structured_outputs() is False


def test_qwen_model_generate_uses_sync_client(monkeypatch):
    model = QwenModel(settings.judge_model_light)
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _response("test successful")

    monkeypatch.setattr(
        model.client.chat.completions,
        "create",
        fake_create,
    )

    response = model.generate("Say 'test successful'")
    assert response == "test successful"
    assert captured["max_tokens"] == settings.judge_max_tokens


@pytest.mark.asyncio
async def test_qwen_model_a_generate_uses_async_client(monkeypatch):
    model = QwenModel(settings.judge_model_light)
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _response("async success")

    monkeypatch.setattr(model.async_client.chat.completions, "create", fake_create)

    response = await model.a_generate("Say async success")
    assert response == "async success"
    assert captured["max_tokens"] == settings.judge_max_tokens


def test_get_light_model_returns_light_model():
    model = get_light_model()
    assert model.model == settings.judge_model_light
    assert model.model == "qwen3.5-35b-a3b"


def test_get_heavy_model_returns_heavy_model():
    model = get_heavy_model()
    assert model.model == settings.judge_model_heavy
    assert model.model == "qwen3.5-flash"
