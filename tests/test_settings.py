from src.config.settings import Settings


def test_settings_defaults():
    settings = Settings(
        gemini_api_key="test-key",
    )
    assert settings.model_name == "gemini-2.0-flash"
    assert settings.embedding_model == "gemini-embedding-001"
    assert settings.collection_name == "medical_docs"
    assert settings.max_message_length == 2000
    assert settings.rate_limit_per_minute == 60


def test_settings_custom_values():
    settings = Settings(
        gemini_api_key="test-key",
        model_name="gemini-pro",
        max_message_length=5000,
    )
    assert settings.model_name == "gemini-pro"
    assert settings.max_message_length == 5000
