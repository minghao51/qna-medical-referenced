"""Shared metric lookup utilities for experiment reporting."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats

_METRIC_ALIASES: dict[str, str] = {
    "ndcg@5": "ndcg_at_k",
    "ndcg@10": "ndcg_at_k",
    "ndcg@3": "ndcg_at_k",
    "hit_rate@5": "hit_rate_at_k",
    "precision@5": "precision_at_k",
    "recall@5": "recall_at_k",
}


def resolve_metric_key(metrics: dict[str, Any], name: str) -> Any:
    """Look up a metric by name, falling back to known aliases."""
    if name in metrics:
        return metrics[name]
    alias = _METRIC_ALIASES.get(name)
    if alias and alias in metrics:
        return metrics[alias]
    return None


def wilcoxon_test(
    system_a_scores: list[float] | np.ndarray,
    system_b_scores: list[float] | np.ndarray,
) -> tuple[float, float]:
    stat, p_value = stats.wilcoxon(system_b_scores, system_a_scores)
    return float(stat), float(p_value)


def bootstrap_ci(
    scores: list[float] | np.ndarray,
    confidence: float = 0.95,
    n_bootstrap: int = 10000,
) -> tuple[float, float]:
    arr = np.asarray(scores, dtype=float)
    boot_means = [
        np.mean(np.random.choice(arr, len(arr), replace=True)) for _ in range(n_bootstrap)
    ]
    lower = float(np.percentile(boot_means, (1 - confidence) / 2 * 100))
    upper = float(np.percentile(boot_means, (1 + confidence) / 2 * 100))
    return lower, upper
