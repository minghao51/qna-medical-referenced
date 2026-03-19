"""Tests for synthetic data generator."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.evals.synthetic.generator import generate_synthetic_dataset


def test_synthetic_generator_structure():
    """Test that generator function is properly structured."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_medical.txt"

    # Mock both Synthesizer and ContextConstructionConfig to avoid needing API keys
    with (
        patch("src.evals.synthetic.generator.Synthesizer") as mock_synthesizer_class,
        patch("src.evals.synthetic.generator.ContextConstructionConfig"),
    ):
        mock_synthesizer = MagicMock()
        mock_synthesizer_class.return_value = mock_synthesizer
        mock_goldens = [MagicMock(), MagicMock()]
        mock_synthesizer.generate_goldens_from_docs.return_value = mock_goldens

        goldens = generate_synthetic_dataset(
            document_paths=[fixture_path], num_questions=2, output_path="/tmp/test_synthetic.json"
        )

        # Verify synthesizer was called correctly
        mock_synthesizer.generate_goldens_from_docs.assert_called_once()
        mock_synthesizer.save_as.assert_called_once()
        _, kwargs = mock_synthesizer.generate_goldens_from_docs.call_args
        assert "context_construction_config" in kwargs

        assert goldens == mock_goldens


def test_synthetic_generator_with_missing_file():
    """Test generator handles missing file gracefully."""
    with patch("src.evals.synthetic.generator.ContextConstructionConfig"):
        with pytest.raises((FileNotFoundError, Exception)):
            generate_synthetic_dataset(document_paths=["nonexistent.txt"])
