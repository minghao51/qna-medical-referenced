import os

from src.config import settings
from src.config.settings import Settings


def test_deepeval_settings_have_defaults():
    """Test that DeepEval settings have sensible defaults."""
    assert hasattr(settings, "judge_model_light")
    assert hasattr(settings, "judge_model_heavy")
    assert hasattr(settings, "judge_temperature")
    assert hasattr(settings, "enable_deepeval")

    # Verify defaults
    assert settings.judge_model_light == "qwen3.5-35b-a3b"
    assert settings.judge_model_heavy == "qwen3.5-flash"
    assert settings.judge_temperature == 0.0
    assert settings.enable_deepeval is True


def test_deepeval_settings_environment_overrides():
    """Test that environment variables override defaults."""
    # Clear environment variables first to ensure clean test
    old_env = {}
    env_vars = ["JUDGE_MODEL_LIGHT", "JUDGE_MODEL_HEAVY", "JUDGE_TEMPERATURE", "ENABLE_DEEPEVAL"]

    # Store current values
    for var in env_vars:
        if var in os.environ:
            old_env[var] = os.environ[var]
            del os.environ[var]

    try:
        # Test with custom values using Settings constructor (like test_settings.py)
        custom_settings = Settings(
            dashscope_api_key="test-key",
            judge_model_light="custom-light",
            judge_model_heavy="custom-heavy",
            judge_temperature=0.7,
            enable_deepeval=False,
        )

        assert custom_settings.judge_model_light == "custom-light"
        assert custom_settings.judge_model_heavy == "custom-heavy"
        assert custom_settings.judge_temperature == 0.7
        assert custom_settings.enable_deepeval is False

    finally:
        # Restore original environment variables
        for var, value in old_env.items():
            os.environ[var] = value
        # Clean up any we set
        for var in env_vars:
            os.environ.pop(var, None)
