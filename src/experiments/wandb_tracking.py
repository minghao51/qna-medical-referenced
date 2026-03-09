"""Weights & Biases tracking helpers for experiment runs."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _flatten_numeric(prefix: str, value: Any, output: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten_numeric(child_prefix, child, output)
        return
    if isinstance(value, bool):
        output[prefix] = int(value)
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        output[prefix] = value


def _wandb_tracking_config(experiment: dict[str, Any] | None) -> dict[str, Any]:
    return dict(((experiment or {}).get("tracking") or {}).get("wandb") or {})


def _resolve_run_name(experiment: dict[str, Any] | None, run_dir: Path) -> str:
    metadata = dict((experiment or {}).get("metadata", {}))
    variant_name = (experiment or {}).get("variant_name")
    base_name = str(metadata.get("name") or run_dir.name).strip() or run_dir.name
    if variant_name and variant_name != base_name:
        return f"{base_name}/{variant_name}"
    return base_name


def log_assessment_to_wandb(
    *,
    experiment: dict[str, Any] | None,
    summary: dict[str, Any],
    manifest: dict[str, Any],
    step_metrics: dict[str, Any],
    retrieval_metrics: dict[str, Any],
    rag_metrics: dict[str, Any],
    run_dir: str | Path,
    failed_thresholds: list[dict[str, Any]],
) -> dict[str, Any]:
    tracking_cfg = _wandb_tracking_config(experiment)
    if not tracking_cfg.get("enabled"):
        return {"enabled": False, "status": "disabled"}

    run_path = Path(run_dir)
    try:
        wandb = importlib.import_module("wandb")
    except Exception as exc:
        logger.warning("W&B tracking requested but unavailable: %s", exc)
        return {
            "enabled": True,
            "status": "error",
            "error": f"wandb import failed: {exc}",
        }

    run = None
    artifact = None
    try:
        run = wandb.init(
            project=tracking_cfg.get("project"),
            entity=tracking_cfg.get("entity"),
            group=tracking_cfg.get("group"),
            job_type=tracking_cfg.get("job_type") or "pipeline_eval",
            tags=tracking_cfg.get("tags") or [],
            notes=tracking_cfg.get("notes"),
            mode=tracking_cfg.get("mode") or "online",
            name=_resolve_run_name(experiment, run_path),
            config={
                "experiment": experiment or {},
                "manifest": manifest,
            },
        )
        metrics: dict[str, Any] = {}
        _flatten_numeric("summary", summary, metrics)
        _flatten_numeric("retrieval", retrieval_metrics, metrics)
        _flatten_numeric("rag", rag_metrics, metrics)
        _flatten_numeric(
            "steps", {k: v.get("aggregate", {}) for k, v in step_metrics.items()}, metrics
        )
        metrics["thresholds.failed_count"] = len(failed_thresholds)
        if metrics:
            run.log(metrics)
        if tracking_cfg.get("log_artifacts", True):
            artifact = wandb.Artifact(
                name=f"{run_path.name}-artifacts",
                type="evaluation-run",
                metadata={
                    "run_dir": run_path.name,
                    "status": summary.get("status"),
                    "failed_thresholds_count": len(failed_thresholds),
                },
            )
            artifact.add_dir(str(run_path))
            run.log_artifact(artifact)
        return {
            "enabled": True,
            "status": "logged",
            "project": tracking_cfg.get("project"),
            "entity": tracking_cfg.get("entity"),
            "group": tracking_cfg.get("group"),
            "job_type": tracking_cfg.get("job_type") or "pipeline_eval",
            "mode": tracking_cfg.get("mode") or "online",
            "run_name": getattr(run, "name", None),
            "run_id": getattr(run, "id", None),
            "run_url": getattr(run, "url", None),
            "artifact_name": getattr(artifact, "name", None) if artifact else None,
        }
    except Exception as exc:
        logger.warning("W&B logging failed for %s: %s", run_path, exc)
        return {
            "enabled": True,
            "status": "error",
            "project": tracking_cfg.get("project"),
            "entity": tracking_cfg.get("entity"),
            "error": str(exc),
        }
    finally:
        if run is not None:
            try:
                run.finish()
            except Exception:
                logger.debug("Failed to finish W&B run cleanly", exc_info=True)
