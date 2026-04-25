"""Unit tests for threshold evaluation."""


from src.evals.assessment.thresholds import (
    DEFAULT_THRESHOLDS,
    evaluate_thresholds,
    flatten_stage_aggregates,
    is_threshold_pass,
)


class TestIsThresholdPass:
    def test_min_pass(self):
        passed, op, val = is_threshold_pass(0.8, {"op": "min", "value": 0.7})
        assert passed is True
        assert op == "min"
        assert val == 0.7

    def test_min_fail(self):
        passed, _op, _val = is_threshold_pass(0.5, {"op": "min", "value": 0.7})
        assert passed is False

    def test_max_pass(self):
        passed, _op, _val = is_threshold_pass(0.05, {"op": "max", "value": 0.10})
        assert passed is True

    def test_max_fail(self):
        passed, _op, _val = is_threshold_pass(0.15, {"op": "max", "value": 0.10})
        assert passed is False

    def test_exact_match_min(self):
        passed, _, _ = is_threshold_pass(0.7, {"op": "min", "value": 0.7})
        assert passed is True

    def test_exact_match_max(self):
        passed, _, _ = is_threshold_pass(0.10, {"op": "max", "value": 0.10})
        assert passed is True

    def test_bool_true(self):
        passed, _, _ = is_threshold_pass(True, {"op": "min", "value": 0.5})
        assert passed is True

    def test_bool_false(self):
        passed, _, _ = is_threshold_pass(False, {"op": "min", "value": 0.5})
        assert passed is False

    def test_scalar_threshold(self):
        passed, op, _val = is_threshold_pass(0.8, 0.7)
        assert passed is True
        assert op == "min"

    def test_non_numeric_fails(self):
        passed, _, _ = is_threshold_pass("not_a_number", {"op": "min", "value": 0.5})
        assert passed is False


class TestFlattenStageAggregates:
    def test_basic(self):
        step_metrics = {
            "l1": {"aggregate": {"markdown_empty_rate": 0.05}},
            "l3": {"aggregate": {"duplicate_chunk_rate": 0.02}},
        }
        result = flatten_stage_aggregates(step_metrics)
        assert result == {
            "l1.markdown_empty_rate": 0.05,
            "l3.duplicate_chunk_rate": 0.02,
        }

    def test_empty(self):
        assert flatten_stage_aggregates({}) == {}

    def test_missing_aggregate(self):
        result = flatten_stage_aggregates({"l1": {}})
        assert result == {}


class TestEvaluateThresholds:
    def test_all_pass(self):
        step_metrics = {
            "l1": {"aggregate": {"markdown_empty_rate": 0.05}},
            "l3": {"aggregate": {"duplicate_chunk_rate": 0.02}},
        }
        retrieval_metrics = {"exact_chunk_hit_rate_high_conf": 0.5}
        l6_metrics = {}
        failed = evaluate_thresholds(
            step_metrics, retrieval_metrics, l6_metrics, DEFAULT_THRESHOLDS
        )
        metric_names = [f["metric"] for f in failed]
        assert "l1.markdown_empty_rate" not in metric_names

    def test_failure_detected(self):
        step_metrics = {
            "l1": {"aggregate": {"markdown_empty_rate": 0.5}},
        }
        failed = evaluate_thresholds(step_metrics, {}, {}, DEFAULT_THRESHOLDS)
        metric_names = [f["metric"] for f in failed]
        assert "l1.markdown_empty_rate" in metric_names

    def test_empty_metrics(self):
        failed = evaluate_thresholds({}, {}, {}, DEFAULT_THRESHOLDS)
        assert failed == []

    def test_l6_answer_quality(self):
        l6_metrics = {
            "factual_accuracy": {"mean": 0.9, "error_rate": 0.0},
            "completeness": {"mean": 0.8},
        }
        failed = evaluate_thresholds({}, {}, l6_metrics, DEFAULT_THRESHOLDS)
        metric_names = [f["metric"] for f in failed]
        assert "l6.factual_accuracy_mean" not in metric_names
        assert "l6.completeness_mean" not in metric_names
