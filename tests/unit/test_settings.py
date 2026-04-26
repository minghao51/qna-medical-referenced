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
    monkeypatch.delenv("MODEL_NAME", raising=False)
    settings = Settings(
        _env_file=None,
        dashscope_api_key="test-key",
        model_name="qwen-plus",
        max_message_length=5000,
    )

    assert settings.llm.model_name == "qwen-plus"
    assert settings.api.max_message_length == 5000
    assert settings.llm.dashscope_api_key == "test-key"


def test_settings_nested_attribute_access(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    settings = Settings(_env_file=None, llm={"dashscope_api_key": "nested-test-key"})

    assert settings.llm.dashscope_api_key == "nested-test-key"


def test_settings_supports_nested_app_env_overrides(monkeypatch):
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.setenv("APP__LLM__MODEL_NAME", "env-override-model")
    monkeypatch.setenv("APP__API__MAX_MESSAGE_LENGTH", "4321")

    settings = Settings(_env_file=None)

    assert settings.llm.model_name == "env-override-model"
    assert settings.api.max_message_length == 4321
