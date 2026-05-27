import os

from src.config import settings
from src.config.settings import Settings


def test_deepeval_settings_have_defaults():
    assert hasattr(settings.llm, "judge_model_light")
    assert settings.llm.judge_model_light == "qwen3.5-35b-a3b"
    assert settings.llm.judge_model_heavy == "qwen3.5-flash"
    assert settings.llm.judge_temperature == 0.0


def test_deepeval_settings_environment_overrides():
    env_vars = [
        "APP__LLM__JUDGE_MODEL_LIGHT",
        "APP__LLM__JUDGE_MODEL_HEAVY",
        "APP__LLM__JUDGE_TEMPERATURE",
    ]

    old_env = {}
    for var in env_vars:
        if var in os.environ:
            old_env[var] = os.environ[var]
            del os.environ[var]

    try:
        for var in env_vars:
            os.environ.pop(var, None)

        os.environ["APP__LLM__JUDGE_MODEL_LIGHT"] = "custom-light"
        os.environ["APP__LLM__JUDGE_MODEL_HEAVY"] = "custom-heavy"
        os.environ["APP__LLM__JUDGE_TEMPERATURE"] = "0.7"

        custom_settings = Settings(_env_file=None)

        assert custom_settings.llm.judge_model_light == "custom-light"
        assert custom_settings.llm.judge_model_heavy == "custom-heavy"
        assert custom_settings.llm.judge_temperature == 0.7

    finally:
        for var, value in old_env.items():
            os.environ[var] = value
        for var in env_vars:
            os.environ.pop(var, None)
