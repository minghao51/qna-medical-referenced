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
from src.evals.metrics.medical import (
    answer_relevancy_metric,
    clarity_metric,
    clinical_relevance_metric,
    completeness_metric,
    factual_accuracy_metric,
    faithfulness_metric,
)

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
    "factual_accuracy_metric",
    "completeness_metric",
    "clinical_relevance_metric",
    "clarity_metric",
    "answer_relevancy_metric",
    "faithfulness_metric",
]
