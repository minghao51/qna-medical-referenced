"""Tests for dependency injection container."""

from src.infra.di import ServiceContainer, get_container, reset_container


def test_service_container_singleton():
    """Test container maintains singleton instances."""
    container = ServiceContainer()

    # First call creates instance
    vs1 = container.get_vector_store()
    assert vs1 is not None

    # Second call returns same instance
    vs2 = container.get_vector_store()
    assert vs1 is vs2


def test_service_container_config_change():
    """Test container creates new instance when config changes."""
    container = ServiceContainer()

    # Get with default config
    vs1 = container.get_vector_store()

    # Get with different config
    vs2 = container.get_vector_store({"collection_name": "test"})

    # Should be different instances due to config change
    assert vs1 is not vs2


def test_service_container_reset():
    """Test container can be reset (for testing)."""
    container = ServiceContainer()

    # Get instance
    vs1 = container.get_vector_store()
    assert vs1 is not None

    # Reset
    container.reset()

    # Get new instance after reset
    vs2 = container.get_vector_store()
    assert vs2 is not None

    # Should be different instances
    assert vs1 is not vs2


def test_global_container():
    """Test global container accessor."""
    # Reset to ensure clean state
    reset_container()

    container = get_container()
    assert container is not None

    # Should return same instance
    container2 = get_container()
    assert container is container2

    # Cleanup
    reset_container()


def test_llm_client_singleton():
    """Test LLM client singleton behavior."""
    container = ServiceContainer()

    client1 = container.get_llm_client()
    assert client1 is not None

    client2 = container.get_llm_client()
    assert client1 is client2


def test_retrieval_config():
    """Test retrieval configuration from settings."""
    container = ServiceContainer()

    config = container.get_retrieval_config()
    assert isinstance(config, dict)
    assert "overfetch_multiplier" in config
    assert "max_chunks_per_source" in config
    assert "mmr_lambda" in config
    assert "search_mode" in config


def test_html_processor_config():
    """Test HTML processor configuration."""
    container = ServiceContainer()

    config = container.get_html_processor_config()
    assert isinstance(config, dict)
    assert "extractor_strategy" in config
    assert "page_classification_enabled" in config
    assert "extractor_mode" in config
