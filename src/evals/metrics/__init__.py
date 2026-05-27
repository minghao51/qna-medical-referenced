"""Evaluation metrics for RAG systems."""

# Re-export utility functions from the old metrics.py
from src.evals.metrics._utils import (
    hit_rate_at_k,
    mean,
    ndcg_at_k,
    percentile,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

_MEDICAL_EXPORTS = {"METRIC_SPECS", "MetricSpec", "create_medical_metrics"}


def __getattr__(name: str):
    if name in _MEDICAL_EXPORTS:
        from src.evals.metrics import medical

        return getattr(medical, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "METRIC_SPECS",
    # Medical metrics
    "MetricSpec",
    "create_medical_metrics",
    "hit_rate_at_k",
    # Utility functions
    "mean",
    "ndcg_at_k",
    "percentile",
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
]
