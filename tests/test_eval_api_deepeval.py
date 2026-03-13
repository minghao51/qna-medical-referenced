"""Tests for DeepEval evaluation API endpoints."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.app.factory import create_app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(create_app())


def test_answer_quality_endpoint_missing_file(client, tmp_path):
    """Test answer quality endpoint returns 404 when file missing."""
    with patch("src.app.routes.evaluation.EVALS_DIR", tmp_path):
        response = client.get("/evaluation/answer-quality/nonexistent_run")
        assert response.status_code == 404


def test_answer_quality_endpoint_loads_results(client, tmp_path):
    """Test answer quality endpoint loads results when file exists."""
    run_dir = tmp_path / "test_run"
    run_dir.mkdir()
    results_file = run_dir / "l6_answer_quality.jsonl"
    results_file.write_text('{"query": "test", "metrics": {}}\n{"query": "test2", "metrics": {}}')

    with patch("src.app.routes.evaluation.EVALS_DIR", tmp_path):
        response = client.get("/evaluation/answer-quality/test_run")
        assert response.status_code == 200
        data = response.json()
        assert data["run_dir"] == "test_run"
        assert len(data["results"]) == 2


@pytest.mark.skip(reason="Full evaluation test requires API keys and working metrics")
def test_evaluate_single_endpoint(client):
    """Test single answer evaluation endpoint."""
    # This test requires actual DeepEval metrics which need API keys
    pass


def test_l6_is_valid_stage():
    """Test that l6 is now a valid stage."""
    from src.app.routes.evaluation import VALID_STAGES
    assert "l6" in VALID_STAGES
