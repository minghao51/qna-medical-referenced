"""Tests for medical evaluation metrics.

Tests the custom medical metrics built with DeepEval's GEval framework,
verifying proper initialization and model tiering.
"""

from deepeval.test_case import LLMTestCase

from src.evals.metrics.medical import (
    answer_relevancy_metric,
    clarity_metric,
    clinical_relevance_metric,
    completeness_metric,
    factual_accuracy_metric,
    faithfulness_metric,
)


def test_metrics_are_initialized():
    """Test all metrics are properly initialized."""
    # Custom GEval metrics
    assert factual_accuracy_metric.name == "Factual Accuracy"
    assert factual_accuracy_metric.threshold == 0.8

    assert completeness_metric.name == "Completeness"
    assert completeness_metric.threshold == 0.75

    assert clinical_relevance_metric.name == "Clinical Relevance"
    assert clinical_relevance_metric.threshold == 0.8

    assert clarity_metric.name == "Clarity"
    assert clarity_metric.threshold == 0.70

    # Built-in metrics
    assert answer_relevancy_metric.threshold == 0.7
    assert faithfulness_metric.threshold == 0.8


def test_metrics_use_correct_models():
    """Test lightweight and heavyweight models are assigned correctly."""
    # Clarity uses lightweight (simple classification)
    assert clarity_metric.model.model == "qwen3.5-35b-a3b"

    # Factual accuracy uses heavyweight (CoT reasoning)
    assert factual_accuracy_metric.model.model == "qwen3.5-flash"


def test_factual_accuracy_metric_measures():
    """Test factual accuracy metric can measure a test case."""
    test_case = LLMTestCase(
        input="What is the LDL-C target for secondary prevention?",
        actual_output="The LDL-C target is 1.8 mmol/L for secondary prevention.",
        retrieval_context=["Guidelines recommend LDL-C < 1.8 mmol/L for secondary prevention."],
    )

    factual_accuracy_metric.measure(test_case)

    assert factual_accuracy_metric.score is not None
    assert 0 <= factual_accuracy_metric.score <= 1
    # Good answer should score high
    assert factual_accuracy_metric.score > 0.5


def test_clarity_metric_uses_lightweight_model():
    """Test clarity metric uses lightweight model."""
    test_case = LLMTestCase(
        input="Explain cholesterol.",
        actual_output="Cholesterol is a waxy substance found in blood.",
        retrieval_context=[],
    )

    clarity_metric.measure(test_case)

    assert clarity_metric.score is not None
    # Verify it used the lightweight model
    assert "qwen3.5-35b-a3b" in clarity_metric.model.get_model_name()
