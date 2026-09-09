import threading
from unittest.mock import MagicMock, patch

from src.infra.di import (
    ServiceContainer,
    get_container,
    reset_container,
)


class TestServiceContainer:
    def test_initial_state(self):
        container = ServiceContainer()
        assert container.vector_store is None
        assert container.llm_client is None
        assert container.chat_history_store is None

    def test_get_html_processor_config_returns_defaults(self):
        container = ServiceContainer()
        config = container.get_html_processor_config()
        assert config["extractor_strategy"] == "trafilatura_bs"
        assert config["page_classification_enabled"] is True

    def test_get_html_processor_config_caches(self):
        container = ServiceContainer()
        config1 = container.get_html_processor_config()
        config2 = container.get_html_processor_config()
        assert config1 is config2

    def test_get_llm_client_creates_once(self):
        container = ServiceContainer()
        mock_client = MagicMock()
        with patch("src.infra.di.ServiceContainer.get_llm_client", return_value=mock_client):
            client = container.get_llm_client()
            assert client is mock_client

    def test_reset_clears_services(self):
        container = ServiceContainer()
        container.html_processor_config = {"key": "val"}
        with (
            patch("src.ingestion.indexing.chroma_store.ChromaVectorStoreFactory") as mock_factory,
            patch("src.infra.di.reset_runtime_state"),
        ):
            mock_factory.reset.return_value = None
            container.reset()
        assert container.vector_store is None
        assert container.llm_client is None
        assert container.chat_history_store is None
        assert container.html_processor_config == {}
        assert container.retrieval_config == {}

    def test_get_vector_store_with_config(self):
        container = ServiceContainer()
        mock_store = MagicMock()
        with patch("src.ingestion.indexing.chroma_store.ChromaVectorStoreFactory") as mock_factory:
            mock_factory.get_vector_store.return_value = mock_store
            result = container.get_vector_store({"collection": "test"})
            assert result is mock_store
            mock_factory.get_vector_store.assert_called_once()

    def test_get_vector_store_reuses_when_config_matches(self):
        container = ServiceContainer()
        mock_store = MagicMock()
        container.vector_store = mock_store
        container.vector_store_config = {"collection": "test"}
        result = container.get_vector_store({"collection": "test"})
        assert result is mock_store


class TestGetContainer:
    def test_returns_container_instance(self):
        reset_container()
        container = get_container()
        assert isinstance(container, ServiceContainer)

    def test_returns_same_instance(self):
        reset_container()
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2

    def test_thread_safety(self):
        reset_container()
        results = []

        def get_it():
            results.append(get_container())

        threads = [threading.Thread(target=get_it) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r is results[0] for r in results)


class TestResetContainer:
    def test_resets_global_container(self):
        c = get_container()
        reset_container()
        c2 = get_container()
        assert c is not c2

    def test_resets_none_container(self):
        reset_container()
        reset_container()


class TestContainerProxy:
    def test_repr(self):
        from src.infra.di import container

        repr_str = repr(container)
        assert "ServiceContainer" in repr_str

    def test_attribute_access_delegates(self):
        from src.infra.di import container

        config = container.get_html_processor_config()
        assert isinstance(config, dict)
        assert "extractor_strategy" in config
