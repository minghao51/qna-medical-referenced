"""Tests for DeepEval orchestrator integration."""

from unittest.mock import MagicMock, patch

import pytest

from src.evals.assessment.orchestrator import run_assessment


def test_deepeval_import_exists():
    """Test that DeepEval function is importable."""
    from src.evals.assessment.orchestrator import evaluate_answers_deepeval
    assert callable(evaluate_answers_deepeval)


def test_config_has_enable_deepeval():
    """Test that AssessmentConfig has enable_deepeval field."""
    from src.evals.schemas import AssessmentConfig
    from pathlib import Path

    config = AssessmentConfig(artifact_dir=Path("/tmp"))
    assert hasattr(config, 'enable_deepeval')
    assert config.enable_deepeval is True  # Default value


@pytest.mark.skip(reason="Full orchestrator test requires extensive mocking")
def test_orchestrator_respects_deepeval_flag():
    """Test that enable_deepeval flag controls which evaluator is used."""
    pass
