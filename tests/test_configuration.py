"""Tests for configuration management."""

from src.config import settings


def test_retrieval_config_defaults():
    """Test retrieval config has sensible defaults."""
    assert settings.retrieval_overfetch_multiplier == 4
    assert settings.max_chunks_per_source_page == 2
    assert settings.max_chunks_per_source == 3
    assert settings.mmr_lambda == 0.75
    assert settings.rrf_search_mode == "rrf_hybrid"


def test_hype_config_defaults():
    """Test HyPE configuration defaults."""
    assert settings.hype_enabled is False
    assert settings.hype_sample_rate == 0.1
    assert settings.hype_max_chunks == 500
    assert settings.hype_questions_per_chunk == 2


def test_hyde_config_defaults():
    """Test HyDE configuration defaults."""
    assert settings.hyde_enabled is False
    assert settings.hyde_max_length == 200


def test_cors_origins_parsing():
    """Test CORS origins are parsed correctly."""
    origins = settings.cors_origins
    assert isinstance(origins, list)
    assert len(origins) > 0
    assert all(isinstance(origin, str) for origin in origins)


def test_is_development():
    """Test environment detection."""
    # Default should be development
    assert settings.is_development is True


def test_model_names():
    """Test model name configuration."""
    assert settings.model_name
    assert settings.embedding_model
    assert settings.judge_model_light
    assert settings.judge_model_heavy


def test_api_configuration():
    """Test API configuration."""
    assert settings.api_keys is None or isinstance(settings.api_keys, str)
    assert isinstance(settings.rate_limit_per_minute, int)
    assert settings.rate_limit_per_minute >= 0


def test_storage_paths():
    """Test storage path configuration."""
    assert settings.data_dir
    assert settings.vector_dir
    assert settings.collection_name


def test_deepeval_configuration():
    """Test DeepEval configuration."""
    assert settings.deepeval_query_concurrency > 0
    assert settings.deepeval_metric_concurrency > 0
    assert settings.deepeval_metric_timeout_seconds > 0
    assert settings.deepeval_cache_dir
