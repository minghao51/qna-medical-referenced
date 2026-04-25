from src.config.settings import Settings


def test_settings_defaults():
    """Test schema defaults without depending on local environment overrides."""
    assert Settings.model_fields["model_name"].default == "qwen3.5-flash"
    assert Settings.model_fields["embedding_model"].default == "text-embedding-v4"
    assert Settings.model_fields["embedding_batch_size"].default == 10
    assert Settings.model_fields["collection_name"].default == "medical_docs"
    assert Settings.model_fields["max_message_length"].default == 2000
    assert Settings.model_fields["rate_limit_per_minute"].default == 60
    assert Settings.model_fields["anonymous_chat_rate_limit_per_minute"].default == 12
    assert Settings.model_fields["rate_limit_bypass_key_ids"].default == ""
    assert Settings.model_fields["rate_limit_bypass_roles"].default == ""
    assert Settings.model_fields["anonymous_browser_cookie_name"].default == "anon_browser_id"
    assert Settings.model_fields["chat_session_cookie_name"].default == "chat_session_id"
    assert Settings.model_fields["chat_session_cookie_max_age_seconds"].default == 60 * 60 * 24 * 30
    assert Settings.model_fields["chat_history_ttl_seconds"].default == 60 * 60 * 24 * 30
    assert Settings.model_fields["trust_proxy_headers"].default is False


def test_settings_custom_values():
    settings = Settings(
        _env_file=None,
        dashscope_api_key="test-key",
        model_name="qwen-plus",
        max_message_length=5000,
    )
    assert settings.model_name == "qwen-plus"
    assert settings.max_message_length == 5000
