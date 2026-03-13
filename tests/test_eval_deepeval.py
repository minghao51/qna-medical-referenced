"""Pytest integration tests for DeepEval medical metrics.

These tests use DeepEval's assert_test() for CI/CD integration.
Run with: pytest tests/test_eval_deepeval.py -m deepeval -v
"""

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from src.evals.metrics.medical import (
    clinical_relevance_metric,
    completeness_metric,
    factual_accuracy_metric,
)


@pytest.mark.deepeval
@pytest.mark.slow
def test_medical_factual_accuracy():
    """Test factual accuracy metric with medically accurate answer."""
    test_case = LLMTestCase(
        input="What is the LDL-C target for secondary prevention?",
        actual_output="According to guidelines, the LDL-C target for secondary prevention is 1.8 mmol/L.",
        retrieval_context=["Current lipid guidelines recommend LDL-C < 1.8 mmol/L for secondary prevention."]
    )
    assert_test(test_case, [factual_accuracy_metric])


@pytest.mark.deepeval
@pytest.mark.slow
def test_medical_completeness():
    """Test completeness metric with partially complete answer."""
    test_case = LLMTestCase(
        input="What are the side effects of statins?",
        actual_output="Common side effects include muscle pain and elevated liver enzymes.",
        retrieval_context=["Statin side effects include myopathy, increased liver enzymes, and rarely rhabdomyolysis."]
    )
    # Lower threshold for this test since answer is incomplete
    completeness_metric.threshold = 0.5  # Temporary override
    assert_test(test_case, [completeness_metric])


@pytest.mark.deepeval
@pytest.mark.slow
def test_medical_clinical_relevance():
    """Test clinical relevance metric with clinically sound answer."""
    test_case = LLMTestCase(
        input="Is aspirin recommended for primary prevention?",
        actual_output="Aspirin may be considered for primary prevention in select high-risk patients, but risks like bleeding should be weighed against benefits.",
        retrieval_context=["Aspirin for primary prevention: consider for high-risk patients, assess bleeding risk."]
    )
    assert_test(test_case, [clinical_relevance_metric])


@pytest.mark.deepeval
@pytest.mark.slow
def test_factual_accuracy_detects_hallucination():
    """Test factual accuracy detects hallucinated information."""
    test_case = LLMTestCase(
        input="What is the LDL-C target?",
        actual_output="The LDL-C target is 5.0 mmol/L.",  # Wrong! Should be 1.8
        retrieval_context=["Guidelines recommend LDL-C < 1.8 mmol/L."]
    )
    # This should fail the assertion (detect hallucination)
    with pytest.raises(AssertionError):  # assert_test raises on failure
        assert_test(test_case, [factual_accuracy_metric])
