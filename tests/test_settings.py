from src.config.settings import Settings


def test_settings_defaults():
    settings = Settings(
        dashscope_api_key="test-key",
    )
    assert settings.model_name == "qwen3.5-flash"
    assert settings.embedding_model == "text-embedding-v4"
    assert settings.collection_name == "medical_docs"
    assert settings.max_message_length == 2000
    assert settings.rate_limit_per_minute == 60


def test_settings_custom_values():
    settings = Settings(
        dashscope_api_key="test-key",
        model_name="qwen-plus",
        max_message_length=5000,
    )
    assert settings.model_name == "qwen-plus"
    assert settings.max_message_length == 5000
