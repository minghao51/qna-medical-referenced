"""Helpers for querying Weights & Biases run history."""

from __future__ import annotations

import importlib
import logging
import time
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)
_CACHE: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}


def _to_plain_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    if hasattr(value, "items"):
        return {str(key): _to_plain_data(item) for key, item in value.items()}
    return value


def _get_metric(summary: dict[str, Any], key: str, default: Any = 0) -> Any:
    return summary.get(key, default)


def _cache_ttl_seconds() -> int:
    return max(0, int(getattr(settings, "wandb_cache_ttl_seconds", 60)))


def _cache_get(key: tuple[Any, ...]) -> dict[str, Any] | None:
    ttl = _cache_ttl_seconds()
    if ttl <= 0:
        return None
    entry = _CACHE.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if time.time() >= expires_at:
        _CACHE.pop(key, None)
        return None
    return dict(value)


def _cache_set(key: tuple[Any, ...], value: dict[str, Any]) -> dict[str, Any]:
    ttl = _cache_ttl_seconds()
    if ttl > 0:
        _CACHE[key] = (time.time() + ttl, dict(value))
    return value


def clear_wandb_cache() -> None:
    _CACHE.clear()


def _normalize_wandb_run(run: Any, *, project: str, entity: str | None = None) -> dict[str, Any]:
    summary = _to_plain_data(getattr(run, "summary", {}) or {})
    config = _to_plain_data(getattr(run, "config", {}) or {})
    experiment = dict(config.get("experiment", {}) or {})
    manifest = dict(config.get("manifest", {}) or {})
    retrieval = _to_plain_data(summary.get("retrieval_metrics", {}) or {})
    if not retrieval:
        retrieval = {
            "hit_rate_at_k": _get_metric(summary, "retrieval/hit_rate"),
            "mrr": _get_metric(summary, "retrieval/mrr"),
            "ndcg_at_k": _get_metric(summary, "retrieval/ndcg"),
            "latency_p50_ms": _get_metric(summary, "retrieval/latency_p50_ms"),
            "latency_p95_ms": _get_metric(summary, "retrieval/latency_p95_ms"),
            "precision_at_k": _get_metric(summary, "retrieval/precision_at_k"),
            "recall_at_k": _get_metric(summary, "retrieval/recall_at_k"),
        }
    tracking = {
        "wandb": {
            "enabled": True,
            "status": "logged",
            "project": project,
            "entity": entity,
            "run_id": getattr(run, "id", None),
            "run_name": getattr(run, "name", None),
            "run_url": getattr(run, "url", None),
        }
    }
    return {
        "run_dir": getattr(run, "name", None) or getattr(run, "id", "wandb-run"),
        "timestamp": getattr(run, "created_at", None) or "",
        "status": summary.get("status", getattr(run, "state", "unknown")),
        "duration_s": summary.get("summary/duration_s", summary.get("duration_s")),
        "failed_thresholds_count": summary.get(
            "summary/failed_thresholds",
            summary.get("failed_thresholds_count", 0),
        ),
        "retrieval_metrics": retrieval,
        "source": "wandb",
        "experiment_name": experiment.get("metadata", {}).get("name")
        or manifest.get("experiment", {}).get("variant"),
        "variant_name": experiment.get("variant_name")
        or manifest.get("experiment", {}).get("variant"),
        "index_config_hash": manifest.get("experiment", {}).get("index_config_hash"),
        "wandb_url": getattr(run, "url", None),
        "wandb_run_id": getattr(run, "id", None),
        "tracking": tracking,
        "manifest": manifest,
        "summary": summary,
        "config": config,
    }


def fetch_wandb_runs(
    *,
    project: str,
    entity: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    project_name = str(project or "").strip()
    if not project_name:
        return {"runs": [], "status": "disabled", "warning": "wandb project not configured"}
    cache_key = ("runs", project_name, entity or "", int(limit))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        wandb = importlib.import_module("wandb")
    except Exception as exc:
        logger.warning("W&B history requested but wandb is unavailable: %s", exc)
        return {"runs": [], "status": "error", "warning": f"wandb import failed: {exc}"}

    target_path = f"{entity}/{project_name}" if entity else project_name
    try:
        api = wandb.Api()
        runs = api.runs(target_path, per_page=limit, order="-created_at")
    except Exception as exc:
        logger.warning("Failed to query W&B runs for %s: %s", target_path, exc)
        return {"runs": [], "status": "error", "warning": str(exc)}

    normalized_runs = [
        _normalize_wandb_run(run, project=project_name, entity=entity) for run in runs
    ]

    return _cache_set(
        cache_key,
        {
            "runs": normalized_runs,
            "status": "ok",
            "project": project_name,
            "entity": entity,
        },
    )


def fetch_wandb_run(
    *,
    project: str,
    entity: str | None = None,
    run_id: str | None = None,
    run_name: str | None = None,
) -> dict[str, Any]:
    project_name = str(project or "").strip()
    if not project_name:
        return {"status": "disabled", "warning": "wandb project not configured"}
    cache_key = ("run", project_name, entity or "", run_id or "", run_name or "")
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        wandb = importlib.import_module("wandb")
    except Exception as exc:
        logger.warning("W&B run requested but wandb is unavailable: %s", exc)
        return {"status": "error", "warning": f"wandb import failed: {exc}"}

    target_path = f"{entity}/{project_name}" if entity else project_name
    try:
        api = wandb.Api()
        candidate_runs = api.runs(target_path, per_page=100, order="-created_at")
    except Exception as exc:
        logger.warning("Failed to query W&B run list for %s: %s", target_path, exc)
        return {"status": "error", "warning": str(exc)}

    for run in candidate_runs:
        if run_id and getattr(run, "id", None) == run_id:
            return _cache_set(
                cache_key,
                {
                    "status": "ok",
                    "run": _normalize_wandb_run(run, project=project_name, entity=entity),
                },
            )
        if run_name and getattr(run, "name", None) == run_name:
            return _cache_set(
                cache_key,
                {
                    "status": "ok",
                    "run": _normalize_wandb_run(run, project=project_name, entity=entity),
                },
            )
    return {"status": "not_found", "warning": "wandb run not found"}
