"""Weights & Biases tracking helpers for experiment runs."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_L6_ANSWER_QUALITY_METRIC_NAMES = (
    "factual_accuracy",
    "completeness",
    "clinical_relevance",
    "clarity",
    "answer_relevancy",
    "faithfulness",
)


def _define_wandb_metrics(run: Any) -> None:
    """Define metric behavior for wandb UI organization."""
    # Primary metrics - prominent display with summary behavior
    run.define_metric("retrieval/hit_rate", summary="max")
    run.define_metric("retrieval/mrr", summary="max")
    run.define_metric("retrieval/ndcg", summary="max")
    run.define_metric("retrieval/latency_p50_ms", summary="min")
    for metric_name in _L6_ANSWER_QUALITY_METRIC_NAMES:
        run.define_metric(f"l6_answer_quality/{metric_name}_mean", summary="max")
        run.define_metric(f"l6_answer_quality/{metric_name}_error_rate", summary="min")
    run.define_metric("l6_answer_quality/query_count", hidden=True)
    run.define_metric("l6_answer_quality/query_count_scored", hidden=True)
    run.define_metric("l6_answer_quality/metric_error_rate", summary="min")
    run.define_metric("l6_answer_quality/metric_evaluations_failed", hidden=True)

    # Hide debug metrics from auto-generated charts
    run.define_metric("retrieval/by_difficulty/*/query_count", hidden=True)
    run.define_metric("retrieval/by_task_type/*", hidden=True)
    run.define_metric("retrieval/by_expected_source_type/*", hidden=True)
    run.define_metric("retrieval/by_semantic_case/*", hidden=True)
    run.define_metric("retrieval/contribution_analysis/*", hidden=True)
    run.define_metric("steps/*/_*", hidden=True)
    run.define_metric("steps/*/source_distribution", hidden=True)
    run.define_metric("steps/*/dedupe_effect_estimate", hidden=True)
    run.define_metric("steps/*/page_classification_distribution", hidden=True)


def _extract_primary_metrics(
    retrieval: dict[str, Any],
    l6_answer_quality: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Extract primary metrics for prominent dashboard display."""
    metrics = {}

    # Retrieval quality
    for key in ["hit_rate_at_k", "mrr", "ndcg_at_k", "latency_p50_ms", "latency_p95_ms"]:
        if key in retrieval:
            clean_key = key.replace("_at_k", "")
            metrics[f"retrieval/{clean_key}"] = retrieval[key]

    # L6 answer quality (if enabled)
    if l6_answer_quality.get("status") != "skipped":
        for metric_name in _L6_ANSWER_QUALITY_METRIC_NAMES:
            metric_payload = l6_answer_quality.get(metric_name)
            if isinstance(metric_payload, dict) and "mean" in metric_payload:
                metrics[f"l6_answer_quality/{metric_name}_mean"] = metric_payload["mean"]
                metrics[f"l6_answer_quality/{metric_name}_error_rate"] = metric_payload.get(
                    "error_rate", 0.0
                )
        if "query_count" in l6_answer_quality:
            metrics["l6_answer_quality/query_count"] = l6_answer_quality["query_count"]
        if "query_count_scored" in l6_answer_quality:
            metrics["l6_answer_quality/query_count_scored"] = l6_answer_quality["query_count_scored"]
        if "metric_error_rate" in l6_answer_quality:
            metrics["l6_answer_quality/metric_error_rate"] = l6_answer_quality["metric_error_rate"]
        if "metric_evaluations_failed" in l6_answer_quality:
            metrics["l6_answer_quality/metric_evaluations_failed"] = l6_answer_quality[
                "metric_evaluations_failed"
            ]

    # Pipeline health
    metrics["summary/duration_s"] = summary.get("duration_s")
    metrics["summary/failed_thresholds"] = summary.get("failed_thresholds_count", 0)

    return metrics


def _extract_secondary_metrics(retrieval: dict[str, Any]) -> dict[str, Any]:
    """Extract secondary metrics for detailed analysis."""
    metrics = {}

    # Secondary retrieval metrics
    for key in [
        "precision_at_k",
        "recall_at_k",
        "source_hit_rate",
        "exact_chunk_hit_rate",
        "evidence_hit_rate",
    ]:
        if key in retrieval:
            metrics[f"retrieval/{key}"] = retrieval[key]

    # Difficulty breakdowns
    by_difficulty = retrieval.get("by_difficulty", {})
    for difficulty, metrics_dict in by_difficulty.items():
        if "hit_rate_at_k" in metrics_dict:
            metrics[f"retrieval/by_difficulty/{difficulty}/hit_rate"] = metrics_dict[
                "hit_rate_at_k"
            ]

    # Category breakdowns
    by_category = retrieval.get("by_query_category", {})
    for category, metrics_dict in by_category.items():
        if "hit_rate_at_k" in metrics_dict:
            metrics[f"retrieval/by_category/{category}/hit_rate"] = metrics_dict["hit_rate_at_k"]

    return metrics


def _extract_debug_metrics(
    retrieval: dict[str, Any],
    step_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Extract debug metrics (hidden from charts but stored)."""
    metrics = {}

    # Nested breakdowns (query counts, detailed stats)
    for breakdown_type in [
        "by_difficulty",
        "by_task_type",
        "by_expected_source_type",
        "by_semantic_case",
    ]:
        breakdown = retrieval.get(breakdown_type, {})
        for category, metrics_dict in breakdown.items():
            for metric_name, value in metrics_dict.items():
                if metric_name != "hit_rate_at_k":  # Already in secondary
                    if isinstance(value, (int, float, bool)):
                        metrics[f"retrieval/{breakdown_type}/{category}/{metric_name}"] = value

    # Contribution analysis
    contrib = retrieval.get("contribution_analysis", {})
    for key, value in contrib.items():
        if isinstance(value, (int, float)):
            metrics[f"retrieval/contribution_analysis/{key}"] = value

    # Step metrics - flatten with quality histogram handling
    for step_name, step_data in step_metrics.items():
        aggregate = step_data.get("aggregate", {})
        for metric_name, value in aggregate.items():
            if metric_name == "chunk_quality_histogram" and isinstance(value, dict):
                for quality_level, count in value.items():
                    if isinstance(count, (int, float, bool)):
                        metrics[f"steps/{step_name}/quality_histogram/{quality_level}"] = count
                continue
            if isinstance(value, (int, float, bool)):
                metrics[f"steps/{step_name}/{metric_name}"] = value

    return metrics


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
    l6_answer_quality_metrics: dict[str, Any],
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
        # Define metric behavior for UI organization
        _define_wandb_metrics(run)

        # Extract metrics in tiers for better dashboard organization
        metrics: dict[str, Any] = {}
        metrics.update(
            _extract_primary_metrics(
                retrieval_metrics, l6_answer_quality_metrics, summary
            )
        )
        metrics.update(_extract_secondary_metrics(retrieval_metrics))
        metrics.update(_extract_debug_metrics(retrieval_metrics, step_metrics))
        metrics["thresholds/failed_count"] = len(failed_thresholds)
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
