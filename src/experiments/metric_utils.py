"""Shared metric lookup utilities for experiment reporting."""

from __future__ import annotations

from typing import Any

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
