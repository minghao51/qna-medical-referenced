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

# Medical-specific evaluation metrics
from src.evals.metrics.medical import METRIC_SPECS, MetricSpec, create_medical_metrics

__all__ = [
    # Utility functions
    "mean",
    "percentile",
    "hit_rate_at_k",
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
    "ndcg_at_k",
    # Medical metrics
    "MetricSpec",
    "METRIC_SPECS",
    "create_medical_metrics",
]
