"""Tests for declarative DeepEval medical metric specs."""

import importlib

import pytest

pytestmark = pytest.mark.skipif(
    not importlib.util.find_spec("deepeval"),
    reason="deepeval not installed",
)


def _import_metrics():
    from src.evals.metrics.medical import METRIC_SPECS, create_medical_metrics

    return METRIC_SPECS, create_medical_metrics


def test_metric_specs_expose_stable_keys_and_factories():
    METRIC_SPECS, _ = _import_metrics()
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
    METRIC_SPECS, create_medical_metrics = _import_metrics()
    first = create_medical_metrics()
    second = create_medical_metrics()

    assert len(first) == len(METRIC_SPECS)
    assert len(second) == len(METRIC_SPECS)
    assert all(a is not b for a, b in zip(first, second, strict=True))
    assert [getattr(metric, "name", metric.__class__.__name__) for metric in first] == [
        spec.display_name for spec in METRIC_SPECS
    ]


def test_metric_specs_use_expected_models(monkeypatch):
    from src.config import settings

    monkeypatch.setattr(settings.llm, "judge_provider", "qwen")
    monkeypatch.setattr(settings.llm, "judge_model_light", "test-light-judge")
    monkeypatch.setattr(settings.llm, "judge_model_heavy", "test-heavy-judge")
    METRIC_SPECS, create_medical_metrics = _import_metrics()
    metrics = create_medical_metrics()
    metric_map = {spec.key: metric for spec, metric in zip(METRIC_SPECS, metrics, strict=True)}

    assert metric_map["clarity"].model.model_name == "test-light-judge"
    assert metric_map["factual_accuracy"].model.model_name == "test-heavy-judge"
    assert metric_map["answer_relevancy"].threshold == 0.7
    assert metric_map["faithfulness"].threshold == 0.8
