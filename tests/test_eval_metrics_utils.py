"""Unit tests for eval metrics utilities."""

import math

import pytest

from src.evals.metrics._utils import (
    hit_rate_at_k,
    mean,
    ndcg_at_k,
    percentile,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


class TestMean:
    def test_basic(self):
        assert mean([1, 2, 3, 4, 5]) == 3.0

    def test_single_value(self):
        assert mean([42.0]) == 42.0

    def test_floats(self):
        assert mean([0.1, 0.2, 0.3]) == pytest.approx(0.2)

    def test_empty_returns_zero(self):
        assert mean([]) == 0.0


class TestPercentile:
    def test_median(self):
        assert percentile([1, 2, 3, 4, 5], 50) == pytest.approx(3.0)

    def test_p99(self):
        values = list(range(1, 101))
        result = percentile(values, 99)
        assert result >= 98

    def test_p0(self):
        assert percentile([10, 20, 30], 0) == pytest.approx(10.0)

    def test_p100(self):
        assert percentile([10, 20, 30], 100) == pytest.approx(30.0)

    def test_single_value(self):
        assert percentile([5.0], 50) == pytest.approx(5.0)


class TestHitRateAtK:
    def test_all_relevant(self):
        assert hit_rate_at_k([1, 1, 1]) == 1.0

    def test_none_relevant(self):
        assert hit_rate_at_k([0, 0, 0]) == 0.0

    def test_first_relevant(self):
        assert hit_rate_at_k([1, 0, 0]) == 1.0

    def test_empty(self):
        assert hit_rate_at_k([]) == 0.0


class TestPrecisionAtK:
    def test_perfect(self):
        assert precision_at_k([1, 1, 1], k=3) == pytest.approx(1.0)

    def test_half(self):
        assert precision_at_k([1, 0, 1, 0], k=4) == pytest.approx(0.5)

    def test_k_none_uses_full(self):
        assert precision_at_k([1, 0]) == pytest.approx(0.5)

    def test_empty(self):
        assert precision_at_k([]) == 0.0


class TestRecallAtK:
    def test_full_recall(self):
        assert recall_at_k([1, 1, 1], total_relevant=3) == pytest.approx(1.0)

    def test_partial(self):
        assert recall_at_k([1, 0, 0], total_relevant=3) == pytest.approx(1 / 3)

    def test_zero_total(self):
        assert recall_at_k([0, 0], total_relevant=0) == 0.0


class TestReciprocalRank:
    def test_first_position(self):
        assert reciprocal_rank([1, 0, 0]) == pytest.approx(1.0)

    def test_second_position(self):
        assert reciprocal_rank([0, 1, 0]) == pytest.approx(0.5)

    def test_third_position(self):
        assert reciprocal_rank([0, 0, 1]) == pytest.approx(1 / 3)

    def test_none_relevant(self):
        assert reciprocal_rank([0, 0, 0]) == 0.0

    def test_empty(self):
        assert reciprocal_rank([]) == 0.0


class TestNdcgAtK:
    def test_perfect_ranking(self):
        assert ndcg_at_k([1, 1, 1]) == pytest.approx(1.0)

    def test_worst_ranking(self):
        assert ndcg_at_k([0, 0, 0]) == pytest.approx(0.0)

    def test_graded(self):
        result = ndcg_at_k([3, 2, 1])
        assert 0.0 < result <= 1.0
