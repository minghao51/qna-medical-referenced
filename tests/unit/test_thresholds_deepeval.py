"""Tests for DeepEval threshold handling."""

from src.evals.assessment.thresholds import evaluate_thresholds


def test_evaluate_thresholds_includes_l6_answer_quality_metric_means():
    failed = evaluate_thresholds(
        step_metrics={},
        retrieval_metrics={"hit_rate_at_k": 1.0},
        l6_answer_quality_metrics={
            "query_count": 1,
            "metric_error_rate": 0.0,
            "factual_accuracy": {"mean": 0.5, "count": 1},
            "clarity": {"mean": 0.9, "count": 1},
        },
        thresholds={
            "l6.factual_accuracy_mean": {"op": "min", "value": 0.8},
            "l6.clarity_mean": {"op": "min", "value": 0.7},
        },
    )

    assert len(failed) == 1
    assert failed[0]["metric"] == "l6.factual_accuracy_mean"


def test_evaluate_thresholds_includes_l6_error_rates():
    failed = evaluate_thresholds(
        step_metrics={},
        retrieval_metrics={},
        l6_answer_quality_metrics={
            "metric_error_rate": 0.25,
            "faithfulness": {"mean": 0.92, "count": 3, "error_rate": 0.34},
        },
        thresholds={
            "l6.metric_error_rate": {"op": "max", "value": 0.10},
            "l6.faithfulness_error_rate": {"op": "max", "value": 0.20},
        },
    )

    assert {item["metric"] for item in failed} == {
        "l6.metric_error_rate",
        "l6.faithfulness_error_rate",
    }
