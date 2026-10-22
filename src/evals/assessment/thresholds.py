"""Threshold helpers for evaluation runs."""

from __future__ import annotations

import math
from typing import Any

from .l6_contract import (
    REQUIRED_ANSWER_METRICS,
    REQUIRED_RETRIEVAL_METRICS,
    RETRIEVAL_METRIC_CONTRACT_VERSION,
)

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
    "l6.metric_error_rate": {"op": "max", "value": 0.10},
}


def flatten_stage_aggregates(step_metrics: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for stage_key, stage_data in step_metrics.items():
        agg = stage_data.get("aggregate", {})
        for key, value in agg.items():
            flattened[f"{stage_key}.{key}"] = value
    return flattened


def is_threshold_pass(metric_value: Any, threshold_spec: Any) -> tuple[bool, str, float]:
    op = str(threshold_spec.get("op", "min")) if isinstance(threshold_spec, dict) else "min"
    raw_threshold = (
        threshold_spec.get("value", 0) if isinstance(threshold_spec, dict) else threshold_spec
    )
    try:
        threshold_value = float(raw_threshold)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Threshold requires a finite value and a min/max operator") from None
    if op not in {"min", "max"} or not math.isfinite(threshold_value):
        raise ValueError("Threshold requires a finite value and a min/max operator")
    metric_num = _finite_number(metric_value)
    if metric_num is None:
        return False, op, threshold_value
    if op == "max":
        return metric_num <= threshold_value, op, threshold_value
    return metric_num >= threshold_value, op, threshold_value


def evaluate_thresholds(
    step_metrics: dict[str, Any],
    retrieval_metrics: dict[str, Any],
    l6_answer_quality_metrics: dict[str, Any],
    thresholds: dict[str, Any],
) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    lookup = flatten_stage_aggregates(step_metrics)
    for key, value in retrieval_metrics.items():
        if not isinstance(value, dict):
            lookup[f"l6.{key}"] = value
    for key, value in l6_answer_quality_metrics.items():
        if isinstance(value, dict) and "mean" in value:
            lookup[f"l6.{key}_mean"] = value.get("mean")
            if "error_rate" in value:
                lookup[f"l6.{key}_error_rate"] = value.get("error_rate")
        elif not isinstance(value, dict):
            lookup[f"l6.{key}"] = value
    for key, threshold in thresholds.items():
        required = not isinstance(threshold, dict) or threshold.get("required", True)
        metric_value = lookup.get(key)
        # This declared index check is boolean; answer-quality scores are not.
        metric_num = (
            float(metric_value)
            if key == "l5.embedding_dim_consistent" and isinstance(metric_value, bool)
            else _finite_number(metric_value)
        )
        passed, op, threshold_value = is_threshold_pass(metric_num, threshold)
        if key not in lookup and not required:
            continue
        if not passed:
            failed.append(
                {
                    "metric": key,
                    "value": metric_num,
                    "threshold_op": op,
                    "threshold_value": threshold_value,
                    "reason": (
                        "missing_required_metric"
                        if key not in lookup
                        else "invalid_metric"
                        if metric_num is None
                        else "quality_threshold"
                    ),
                }
            )
    return failed


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _count(value: Any, expected: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= expected:
        return value
    return 0


def measurement_summary(
    *,
    expected: int,
    retrieval_metrics: dict[str, Any],
    answer_metrics: dict[str, Any],
    include_answer_eval: bool,
    execution_mode: str = "diagnostic",
) -> dict[str, Any]:
    """Summarize denominators; benchmark mode requires the versioned evidence contract."""
    if execution_mode == "benchmark":
        retrieval_expected = retrieval_metrics.get("retrieval_expected_case_count")
        retrieval_measured_raw = retrieval_metrics.get("retrieval_measured_case_count")
        retrieval_failed_raw = retrieval_metrics.get("retrieval_failed_case_count")
        retrieval_excluded_raw = retrieval_metrics.get("retrieval_excluded_case_count")
        count_fields_valid = all(
            isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= expected
            for value in (
                retrieval_expected,
                retrieval_measured_raw,
                retrieval_failed_raw,
                retrieval_excluded_raw,
            )
        )
        retrieved = _count(retrieval_measured_raw, expected)
        retrieval_failed = _count(retrieval_failed_raw, expected)
        retrieval_excluded = _count(retrieval_excluded_raw, expected)
        retrieval_version = retrieval_metrics.get("retrieval_metric_contract_version")
        metric_status = {
            key: _finite_number(retrieval_metrics.get(key)) is not None
            for key in REQUIRED_RETRIEVAL_METRICS
        }
        retrieval_complete = (
            expected > 0
            and count_fields_valid
            and retrieval_expected == expected
            and retrieved == expected
            and retrieval_failed == 0
            and retrieval_excluded == 0
            and retrieval_version == RETRIEVAL_METRIC_CONTRACT_VERSION
            and all(metric_status.values())
        )
    else:
        retrieved = _count(retrieval_metrics.get("query_count"), expected)
        retrieval_expected = expected
        retrieval_failed = max(0, expected - retrieved)
        retrieval_excluded = 0
        retrieval_version = retrieval_metrics.get("retrieval_metric_contract_version")
        metric_status = {}
        retrieval_complete = expected > 0 and retrieved == expected
    suites: dict[str, Any] = {
        "retrieval": {
            "status": "complete" if retrieval_complete else "incomplete",
            "expected": expected,
            "measured": retrieved,
            "failed": retrieval_failed,
            "excluded": retrieval_excluded,
            "unmeasured": max(0, expected - retrieved),
            "coverage": retrieved / expected if expected else None,
            "metric_contract_version": retrieval_version,
            "required_metrics": metric_status,
        },
        "answer": {"status": "not_applicable", "required": False},
    }
    answer_complete = True
    if include_answer_eval:
        completed = _count(answer_metrics.get("query_count_complete"), expected)
        metrics: dict[str, Any] = {}
        for key in REQUIRED_ANSWER_METRICS:
            payload = answer_metrics.get(key, {})
            payload = payload if isinstance(payload, dict) else {}
            measured = _count(payload.get("count"), expected)
            valid = _finite_number(payload.get("mean")) is not None
            metrics[key] = {
                "expected": expected,
                "measured": measured,
                "failed": _count(payload.get("error_count"), expected),
                "coverage": measured / expected if expected else None,
                "status": "complete"
                if expected > 0 and measured == expected and valid
                else "incomplete",
            }
        answer_complete = (
            expected > 0
            and completed == expected
            and answer_metrics.get("query_count") == expected
            and answer_metrics.get("status") == "ok"
            and all(
                item["status"] == "complete" and item["failed"] == 0 for item in metrics.values()
            )
        )
        suites["answer"] = {
            "status": "complete" if answer_complete else "incomplete",
            "required": True,
            "expected": expected,
            "measured": completed,
            "unmeasured": expected - completed,
            "coverage": completed / expected if expected else None,
            "metrics": metrics,
        }
    return {
        "status": "complete" if retrieval_complete and answer_complete else "incomplete",
        "minimum_coverage": 1.0,
        "suites": suites,
    }
