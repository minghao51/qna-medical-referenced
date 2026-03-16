"""Tests for declarative DeepEval medical metric specs."""

from src.evals.metrics.medical import METRIC_SPECS, create_medical_metrics


def test_metric_specs_expose_stable_keys_and_factories():
    keys = [spec.key for spec in METRIC_SPECS]

    assert keys == [
        "factual_accuracy",
        "completeness",
        "clinical_relevance",
        "clarity",
        "answer_relevancy",
        "faithfulness",
    ]
    assert [spec.judge_tier for spec in METRIC_SPECS] == [
        "heavy",
        "heavy",
        "heavy",
        "light",
        "light",
        "heavy",
    ]


def test_create_medical_metrics_returns_fresh_instances():
    first = create_medical_metrics()
    second = create_medical_metrics()

    assert len(first) == len(METRIC_SPECS)
    assert len(second) == len(METRIC_SPECS)
    assert all(a is not b for a, b in zip(first, second, strict=True))
    assert [getattr(metric, "name", metric.__class__.__name__) for metric in first] == [
        spec.display_name for spec in METRIC_SPECS
    ]


def test_metric_specs_use_expected_models():
    metrics = create_medical_metrics()
    metric_map = {
        spec.key: metric for spec, metric in zip(METRIC_SPECS, metrics, strict=True)
    }

    assert metric_map["clarity"].model.model == "qwen3.5-35b-a3b"
    assert metric_map["factual_accuracy"].model.model == "qwen3.5-flash"
    assert metric_map["answer_relevancy"].threshold == 0.7
    assert metric_map["faithfulness"].threshold == 0.8
