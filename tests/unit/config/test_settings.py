import pytest
from pydantic import ValidationError

from src.config.settings import Settings


def test_settings_defaults():
    """Test schema defaults without depending on local environment overrides."""
    llm_defaults = Settings.model_fields["llm"].default_factory()
    api_defaults = Settings.model_fields["api"].default_factory()
    storage_defaults = Settings.model_fields["storage"].default_factory()

    assert llm_defaults.model_name == "qwen3.5-flash"
    assert llm_defaults.embedding_model == "text-embedding-v4"
    assert llm_defaults.embedding_batch_size == 10
    assert storage_defaults.collection_name == "medical_docs"
    assert api_defaults.max_message_length == 2000
    assert api_defaults.rate_limit_per_minute == 60
    assert api_defaults.anonymous_chat_rate_limit_per_minute == 12
    assert api_defaults.rate_limit_bypass_key_ids == ""
    assert api_defaults.rate_limit_bypass_roles == ""
    assert api_defaults.anonymous_browser_cookie_name == "anon_browser_id"
    assert api_defaults.chat_session_cookie_name == "chat_session_id"
    assert api_defaults.chat_session_cookie_max_age_seconds == 60 * 60 * 24 * 30
    assert api_defaults.chat_history_ttl_seconds == 60 * 60 * 24 * 30
    assert api_defaults.chat_history_max_messages_per_session == 100
    assert api_defaults.trust_proxy_headers is False


def test_settings_custom_values(monkeypatch):
    settings = Settings(
        _env_file=None,
        llm={"dashscope_api_key": "test-key", "model_name": "qwen-plus"},
        api={"max_message_length": 5000},
    )

    assert settings.llm.model_name == "qwen-plus"
    assert settings.api.max_message_length == 5000
    assert settings.llm.dashscope_api_key.get_secret_value() == "test-key"


def test_settings_nested_attribute_access(monkeypatch):
    settings = Settings(_env_file=None, llm={"dashscope_api_key": "nested-test-key"})

    assert settings.llm.dashscope_api_key.get_secret_value() == "nested-test-key"


def test_settings_supports_nested_app_env_overrides(monkeypatch):
    monkeypatch.setenv("APP__LLM__MODEL_NAME", "env-override-model")
    monkeypatch.setenv("APP__API__MAX_MESSAGE_LENGTH", "4321")

    settings = Settings(_env_file=None)

    assert settings.llm.model_name == "env-override-model"
    assert settings.api.max_message_length == 4321


def test_llm_config_pydantic_ai_settings_bounds():
    """Pydantic AI provider settings reject invalid values explicitly (R05)."""
    import pytest
    from pydantic import ValidationError

    from src.config.settings import LLMConfig

    valid = LLMConfig()
    assert valid.provider == "qwen"  # default flip is not part of this slice
    assert valid.pydantic_ai_temperature == 0.7
    assert valid.pydantic_ai_max_tokens == 2048
    assert valid.pydantic_ai_timeout_seconds == 30.0
    assert valid.pydantic_ai_structured_output_mode == "tool"

    with pytest.raises(ValidationError):
        LLMConfig(pydantic_ai_temperature=-0.1)
    with pytest.raises(ValidationError):
        LLMConfig(pydantic_ai_temperature=2.1)
    with pytest.raises(ValidationError):
        LLMConfig(pydantic_ai_max_tokens=0)
    with pytest.raises(ValidationError):
        LLMConfig(pydantic_ai_timeout_seconds=0.0)
    with pytest.raises(ValidationError):
        LLMConfig(pydantic_ai_timeout_seconds=600.5)
    with pytest.raises(ValidationError):
        LLMConfig(pydantic_ai_structured_output_mode="json_object")


def test_settings_accept_exact_pydantic_ai_bounds_via_app_env(monkeypatch):
    """Exact documented bounds load through APP__ env overrides and are stored as given."""
    monkeypatch.setenv("APP__LLM__PYDANTIC_AI_TEMPERATURE", "0.0")
    monkeypatch.setenv("APP__LLM__PYDANTIC_AI_TIMEOUT_SECONDS", "600.0")

    settings = Settings(_env_file=None)

    assert settings.llm.pydantic_ai_temperature == 0.0
    assert settings.llm.pydantic_ai_timeout_seconds == 600.0

    monkeypatch.setenv("APP__LLM__PYDANTIC_AI_TEMPERATURE", "2.0")

    upper = Settings(_env_file=None)

    assert upper.llm.pydantic_ai_temperature == 2.0
    assert upper.llm.pydantic_ai_timeout_seconds == 600.0


def test_settings_reject_out_of_bounds_pydantic_ai_values_via_app_env(monkeypatch):
    """Out-of-bounds APP__ env overrides fail Settings validation."""
    cases = [
        ("APP__LLM__PYDANTIC_AI_TEMPERATURE", "2.1"),
        ("APP__LLM__PYDANTIC_AI_TEMPERATURE", "-0.1"),
        ("APP__LLM__PYDANTIC_AI_TIMEOUT_SECONDS", "600.1"),
        ("APP__LLM__PYDANTIC_AI_TIMEOUT_SECONDS", "0"),
    ]
    for name, value in cases:
        monkeypatch.setenv(name, value)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)
        monkeypatch.delenv(name)
