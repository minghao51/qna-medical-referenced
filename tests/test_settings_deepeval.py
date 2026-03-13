from src.config import settings


def test_deepeval_settings_have_defaults():
    """Test that DeepEval settings have sensible defaults."""
    assert hasattr(settings, 'judge_model_light')
    assert hasattr(settings, 'judge_model_heavy')
    assert hasattr(settings, 'judge_temperature')
    assert hasattr(settings, 'enable_deepeval')

    # Verify defaults
    assert settings.judge_model_light == "qwen3.5-35b-a3b"
    assert settings.judge_model_heavy == "qwen3.5-flash"
    assert settings.judge_temperature == 0.0
    assert settings.enable_deepeval is True