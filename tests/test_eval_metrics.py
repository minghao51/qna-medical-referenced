from src.evals.metrics import (
    hit_rate_at_k,
    ndcg_at_k,
    percentile,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_rank_metrics_basic():
    rel = [0, 1, 0, 1]
    assert hit_rate_at_k(rel) == 1.0
    assert precision_at_k(rel, 4) == 0.5
    assert recall_at_k(rel, total_relevant=2) == 1.0
    assert reciprocal_rank(rel) == 0.5
    assert 0 < ndcg_at_k(rel, 4) <= 1.0


def test_percentile_interpolates():
    vals = [10, 20, 30, 40]
    assert percentile(vals, 0) == 10
    assert percentile(vals, 50) == 25
    assert percentile(vals, 100) == 40
