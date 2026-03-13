"""Threshold helpers for evaluation runs."""

from __future__ import annotations

from typing import Any

DEFAULT_THRESHOLDS: dict[str, dict[str, Any]] = {
    "l1.markdown_empty_rate": {"op": "max", "value": 0.10},
    "l2.empty_page_rate": {"op": "max", "value": 0.20},
    "l3.duplicate_chunk_rate": {"op": "max", "value": 0.05},
    "l5.embedding_dim_consistent": {"op": "min", "value": 1.0},
    "l6.exact_chunk_hit_rate_high_conf": {"op": "min", "value": 0.40},
    "l6.evidence_hit_rate_high_conf": {"op": "min", "value": 0.50},
    "l6.hit_rate_at_k_high_conf": {"op": "min", "value": 0.70},
    "l6.mrr_high_conf": {"op": "min", "value": 0.40},
    "l6.topic_false_positive_rate": {"op": "max", "value": 0.35},
    "l6.duplicate_source_ratio_mean": {"op": "max", "value": 0.60},
    # L6: Answer Quality (DeepEval metrics)
    "l6.factual_accuracy_mean": {"op": "min", "value": 0.8},
    "l6.completeness_mean": {"op": "min", "value": 0.75},
    "l6.clinical_relevance_mean": {"op": "min", "value": 0.8},
    "l6.clarity_mean": {"op": "min", "value": 0.70},
    "l6.answer_relevancy_mean": {"op": "min", "value": 0.7},
    "l6.faithfulness_mean": {"op": "min", "value": 0.8},
}


def flatten_stage_aggregates(step_metrics: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for stage_key, stage_data in step_metrics.items():
        agg = stage_data.get("aggregate", {})
        for key, value in agg.items():
            flattened[f"{stage_key}.{key}"] = value
    return flattened


def is_threshold_pass(metric_value: Any, threshold_spec: Any) -> tuple[bool, str, float]:
    if isinstance(threshold_spec, dict):
        op = str(threshold_spec.get("op", "min"))
        threshold_value = float(threshold_spec.get("value", 0))
    else:
        op = "min"
        threshold_value = float(threshold_spec)
    try:
        metric_num = (
            1.0 if metric_value is True else 0.0 if metric_value is False else float(metric_value)
        )
        if op == "max":
            return metric_num <= threshold_value, op, threshold_value
        return metric_num >= threshold_value, op, threshold_value
    except Exception:
        return False, op, threshold_value


def evaluate_thresholds(
    step_metrics: dict[str, Any], retrieval_metrics: dict[str, Any], thresholds: dict[str, Any]
) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    lookup = flatten_stage_aggregates(step_metrics)
    for key, value in retrieval_metrics.items():
        if not isinstance(value, dict):
            lookup[f"l6.{key}"] = value
    for key, threshold in thresholds.items():
        if key not in lookup:
            continue
        metric_value = lookup[key]
        passed, op, threshold_value = is_threshold_pass(metric_value, threshold)
        if not passed:
            failed.append(
                {
                    "metric": key,
                    "value": metric_value,
                    "threshold_op": op,
                    "threshold_value": threshold_value,
                }
            )
    return failed
