"""Pytest integration tests for DeepEval medical metrics."""

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from src.evals.metrics.medical import METRIC_SPECS


def _metric_for(key: str):
    return next(spec for spec in METRIC_SPECS if spec.key == key).create()


@pytest.mark.deepeval
@pytest.mark.slow
def test_medical_factual_accuracy():
    test_case = LLMTestCase(
        input="What is the LDL-C target for secondary prevention?",
        actual_output="According to guidelines, the LDL-C target for secondary prevention is 1.8 mmol/L.",
        retrieval_context=[
            "Current lipid guidelines recommend LDL-C < 1.8 mmol/L for secondary prevention."
        ],
    )

    assert_test(test_case, [_metric_for("factual_accuracy")])


@pytest.mark.deepeval
@pytest.mark.slow
def test_medical_completeness():
    test_case = LLMTestCase(
        input="What are the side effects of statins?",
        actual_output="Common side effects include muscle pain and elevated liver enzymes.",
        retrieval_context=[
            "Statin side effects include myopathy, increased liver enzymes, and rarely rhabdomyolysis."
        ],
    )

    metric = _metric_for("completeness")
    metric.threshold = 0.5
    assert_test(test_case, [metric])


@pytest.mark.deepeval
@pytest.mark.slow
def test_medical_clinical_relevance():
    test_case = LLMTestCase(
        input="Is aspirin recommended for primary prevention?",
        actual_output="Aspirin may be considered for primary prevention in select high-risk patients, but risks like bleeding should be weighed against benefits.",
        retrieval_context=[
            "Aspirin for primary prevention: consider for high-risk patients, assess bleeding risk."
        ],
    )

    assert_test(test_case, [_metric_for("clinical_relevance")])


@pytest.mark.deepeval
@pytest.mark.slow
def test_factual_accuracy_detects_hallucination():
    test_case = LLMTestCase(
        input="What is the LDL-C target?",
        actual_output="The LDL-C target is 5.0 mmol/L.",
        retrieval_context=["Guidelines recommend LDL-C < 1.8 mmol/L."],
    )

    with pytest.raises(AssertionError):
        assert_test(test_case, [_metric_for("factual_accuracy")])
