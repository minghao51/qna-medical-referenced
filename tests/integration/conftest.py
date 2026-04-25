import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(monkeypatch, tmp_path):
    """Create a TestClient with mocked deps for integration tests."""
    from src.app.factory import create_app

    monkeypatch.setattr("src.app.factory.validate_security_configuration", lambda: None)
    monkeypatch.setattr("src.app.factory.initialize_runtime_index_async", lambda: None)
    app = create_app()
    return TestClient(app)
