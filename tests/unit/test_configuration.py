"""Tests for configuration management."""

from src.config import settings


def test_retrieval_config_defaults():
    """Test retrieval config has sensible defaults."""
    assert settings.retrieval.retrieval_overfetch_multiplier == 4
    assert settings.retrieval.max_chunks_per_source_page == 2
    assert settings.retrieval.max_chunks_per_source == 3
    assert settings.retrieval.mmr_lambda == 0.75
    assert settings.retrieval.rrf_search_mode == "rrf_hybrid"


def test_hype_config_defaults():
    """Test HyPE configuration defaults."""
    assert settings.hyde.hype_enabled is False
    assert settings.hyde.hype_sample_rate == 0.1
    assert settings.hyde.hype_max_chunks == 500
    assert settings.hyde.hype_questions_per_chunk == 2


def test_hyde_config_defaults():
    """Test HyDE configuration defaults."""
    assert settings.hyde.hyde_enabled is False
    assert settings.hyde.hyde_max_length == 200


def test_medical_expansion_defaults():
    """Test medical expansion seam defaults."""
    assert settings.retrieval.medical_expansion_enabled is False
    assert settings.retrieval.medical_expansion_provider == "noop"


def test_cors_origins_parsing():
    """Test CORS origins are parsed correctly."""
    origins = settings.api.cors_allowed_origins
    assert isinstance(origins, str)
    assert len(origins) > 0
    assert all(isinstance(origin, str) for origin in origins.split(","))


def test_is_development():
    """Test environment detection."""
    assert settings.is_development is True


def test_model_names():
    """Test model name configuration."""
    assert settings.llm.model_name
    assert settings.llm.embedding_model
    assert settings.llm.judge_model_light
    assert settings.llm.judge_model_heavy


def test_api_configuration():
    """Test API configuration."""
    assert settings.api.api_keys is None or isinstance(settings.api.api_keys, str)
    assert isinstance(settings.api.rate_limit_per_minute, int)
    assert settings.api.rate_limit_per_minute >= 0


def test_storage_paths():
    """Test storage path configuration."""
    assert settings.storage.data_dir
    assert settings.vector_dir
    assert settings.storage.collection_name


def test_deepeval_configuration():
    """Test DeepEval configuration."""
    assert settings.deepeval.deepeval_query_concurrency > 0
    assert settings.deepeval.deepeval_metric_concurrency > 0
    assert settings.deepeval.deepeval_metric_timeout_seconds > 0
    assert settings.deepeval.deepeval_cache_dir
