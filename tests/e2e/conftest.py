import pytest


@pytest.fixture
def e2e_env_check():
    """Verify real API credentials are available for e2e tests."""
    import os

    if os.environ.get("ENABLE_REAL_API_TESTS") != "1":
        pytest.skip("Set ENABLE_REAL_API_TESTS=1 to run e2e tests")
