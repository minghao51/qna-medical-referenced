"""Tests for QwenModel wrapper for DeepEval."""

from src.config.settings import settings
from src.evals.deepeval_models import QwenModel, get_heavy_model, get_light_model


def test_qwen_model_initialization():
    """Test QwenModel can be initialized with a model name."""
    model = QwenModel("qwen3.5-flash")
    assert model.model == "qwen3.5-flash"
    assert model.client is not None


def test_qwen_model_implements_required_methods():
    """Test QwenModel implements all DeepEvalBaseLLM methods."""
    model = QwenModel("qwen3.5-flash")

    # Required methods
    assert hasattr(model, "load_model")
    assert hasattr(model, "generate")
    assert hasattr(model, "a_generate")
    assert hasattr(model, "get_model_name")


def test_qwen_model_generate():
    """Test QwenModel.generate() returns text."""
    model = QwenModel(settings.judge_model_light)
    response = model.generate("Say 'test successful'")
    assert "test" in response.lower()
    assert len(response) > 0


def test_get_light_model_returns_light_model():
    """Test factory returns model configured with light model."""
    model = get_light_model()
    assert model.model == settings.judge_model_light
    assert model.model == "qwen3.5-35b-a3b"


def test_get_heavy_model_returns_heavy_model():
    """Test factory returns model configured with heavy model."""
    model = get_heavy_model()
    assert model.model == settings.judge_model_heavy
    assert model.model == "qwen3.5-flash"


def test_qwen_model_handles_empty_response():
    """Test model handles empty API responses gracefully."""
    # This test documents current behavior
    # If API returns empty, we return empty string
    model = QwenModel(settings.judge_model_light)
    response = model.generate("")  # Edge case
    assert isinstance(response, str)
