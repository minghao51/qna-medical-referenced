import os

from src.config import settings
from src.config.settings import Settings


def test_deepeval_settings_have_defaults():
    """Test that DeepEval settings have sensible defaults."""
    assert hasattr(settings.llm, "judge_model_light")
    assert settings.llm.judge_model_light == "qwen3.5-35b-a3b"
    assert settings.llm.judge_model_heavy == "qwen3.5-flash"
    assert settings.llm.judge_temperature == 0.0


def test_deepeval_settings_environment_overrides():
    """Test that environment variables override defaults."""
    old_env = {}
    env_vars = ["JUDGE_MODEL_LIGHT", "JUDGE_MODEL_HEAVY", "JUDGE_TEMPERATURE"]

    for var in env_vars:
        if var in os.environ:
            old_env[var] = os.environ[var]
            del os.environ[var]

    try:
        for var in env_vars:
            os.environ.pop(var, None)

        custom_settings = Settings(
            _env_file=None,
            dashscope_api_key="test-key",
            judge_model_light="custom-light",
            judge_model_heavy="custom-heavy",
            judge_temperature=0.7,
        )

        assert custom_settings.llm.judge_model_light == "custom-light"
        assert custom_settings.llm.judge_model_heavy == "custom-heavy"
        assert custom_settings.llm.judge_temperature == 0.7

    finally:
        for var, value in old_env.items():
            os.environ[var] = value
        for var in env_vars:
            os.environ.pop(var, None)
