"""Weights & Biases tracking helpers for experiment runs."""

from __future__ import annotations

import importlib
import logging
import math
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

_SAFE_METRIC_NAMES = {
    "retrieval/hit_rate",
    "retrieval/mrr",
    "retrieval/ndcg",
    "retrieval/latency_p50_ms",
    "retrieval/latency_p95_ms",
    "retrieval/precision_at_k",
    "retrieval/recall_at_k",
    "retrieval/source_hit_rate",
    "retrieval/exact_chunk_hit_rate",
    "retrieval/evidence_hit_rate",
    "retrieval/hyde_enabled",
    "retrieval/hyde_queries_count",
    "retrieval/hyde_hit_rate",
    "retrieval/hyde_mrr",
    "retrieval/hyde_source_hit_rate",
    "l6_answer_quality/query_count",
    "l6_answer_quality/query_count_scored",
    "l6_answer_quality/metric_error_rate",
    "l6_answer_quality/metric_evaluations_failed",
    "summary/duration_s",
    "summary/failed_thresholds",
    "thresholds/failed_count",
    *{
        f"l6_answer_quality/{metric_name}_{suffix}"
        for metric_name in _L6_ANSWER_QUALITY_METRIC_NAMES
        for suffix in ("mean", "error_rate")
    },
}

_SAFE_ENUMS = {
    "ingestion": {
        "html_extractor_mode": {"auto"},
        "html_extractor_strategy": {"trafilatura_bs"},
        "pdf_extractor_strategy": {"pypdf_pdfplumber"},
        "pdf_table_extractor": {"heuristic"},
    },
    "retrieval": {"search_mode": {"rrf_hybrid", "semantic_only"}},
    "embedding_index": {"rebuild_policy": {"if_missing_or_stale"}},
}
_SAFE_BOOLEANS = {
    "ingestion": {
        "page_classification_enabled",
        "index_only_classified_pages",
        "structured_chunking_enabled",
    },
    "retrieval": {"enable_diversification"},
    "dataset": {"enable_llm_generation"},
    "evaluation": {
        "include_answer_eval",
        "disable_llm_judging",
        "fail_on_thresholds",
        "export_failed_generations",
        "run_retrieval_ablations",
        "run_diversity_sweep",
    },
}
_SAFE_NUMBERS = {
    "embedding_index": {
        "embedding_batch_size",
        "semantic_weight",
        "keyword_weight",
        "boost_weight",
    },
    "retrieval": {
        "top_k",
        "mmr_lambda",
        "overfetch_multiplier",
        "max_chunks_per_source_page",
        "max_chunks_per_source",
    },
    "dataset": {"max_synthetic_questions", "sample_docs_per_source_type", "seed"},
}


def _is_finite_number(value: Any) -> bool:
    return type(value) in (int, float) and (type(value) is int or math.isfinite(value))


def _safe_structural_config(experiment: dict[str, Any] | None) -> dict[str, Any]:
    """Select only fixed-name structural metadata with safe scalar values."""
    source = experiment if isinstance(experiment, dict) else {}
    safe: dict[str, Any] = {}
    schema_version = source.get("schema_version")
    if _is_finite_number(schema_version):
        safe["schema_version"] = schema_version

    for section in _SAFE_BOOLEANS.keys() | _SAFE_NUMBERS.keys() | _SAFE_ENUMS.keys():
        values = source.get(section)
        if not isinstance(values, dict):
            continue
        safe_values: dict[str, Any] = {}
        for key in _SAFE_BOOLEANS.get(section, set()):
            value = values.get(key)
            if type(value) is bool:
                safe_values[key] = value
        for key in _SAFE_NUMBERS.get(section, set()):
            value = values.get(key)
            if _is_finite_number(value):
                safe_values[key] = value
        for key, allowed_values in _SAFE_ENUMS.get(section, {}).items():
            value = values.get(key)
            if isinstance(value, str) and value in allowed_values:
                safe_values[key] = value
        if safe_values:
            safe[section] = safe_values
    return safe


def _safe_metric_payload(metrics: dict[str, Any]) -> dict[str, int | float | bool]:
    safe: dict[str, int | float | bool] = {}
    for name, value in metrics.items():
        if name not in _SAFE_METRIC_NAMES:
            continue
        if name == "retrieval/hyde_enabled" and type(value) is bool:
            safe[name] = value
        elif _is_finite_number(value):
            safe[name] = value
    return safe


def _safe_define_metric(run: Any, name: str, **kwargs: Any) -> None:
    try:
        run.define_metric(name, **kwargs)
    except Exception:
        logger.warning("Skipping unsupported W&B metric definition")


def _define_wandb_metrics(run: Any, verbosity: str = "standard") -> None:
    """Define metric behavior for wandb UI organization.

    Args:
        run: The wandb run object
        verbosity: One of 'critical', 'standard', or 'debug'
    """
    # Define all metrics that might be logged (safe to define even if not used)

    # Primary metrics - prominent display with summary behavior
    _safe_define_metric(run, "retrieval/hit_rate", summary="max")
    _safe_define_metric(run, "retrieval/mrr", summary="max")
    _safe_define_metric(run, "retrieval/ndcg", summary="max")
    _safe_define_metric(run, "retrieval/latency_p50_ms", summary="min")
    _safe_define_metric(run, "retrieval/latency_p95_ms", summary="min")

    # Secondary retrieval metrics
    _safe_define_metric(run, "retrieval/precision_at_k", summary="max")
    _safe_define_metric(run, "retrieval/recall_at_k", summary="max")
    _safe_define_metric(run, "retrieval/source_hit_rate", summary="max")
    _safe_define_metric(run, "retrieval/exact_chunk_hit_rate", summary="max")
    _safe_define_metric(run, "retrieval/evidence_hit_rate", summary="max")

    # HyDe (Hypothetical Document Embeddings) metrics
    _safe_define_metric(run, "retrieval/hyde_enabled", hidden=True)
    _safe_define_metric(run, "retrieval/hyde_queries_count", hidden=True)
    _safe_define_metric(run, "retrieval/hyde_hit_rate", summary="max")
    _safe_define_metric(run, "retrieval/hyde_mrr", summary="max")
    _safe_define_metric(run, "retrieval/hyde_source_hit_rate", summary="max")

    # Note: wandb doesn't support glob patterns in define_metric
    # Metrics will be auto-created when logged

    # L6 answer quality metrics (if enabled)
    for metric_name in _L6_ANSWER_QUALITY_METRIC_NAMES:
        _safe_define_metric(run, f"l6_answer_quality/{metric_name}_mean", summary="max")
        _safe_define_metric(run, f"l6_answer_quality/{metric_name}_error_rate", summary="min")
    _safe_define_metric(run, "l6_answer_quality/query_count", hidden=True)
    _safe_define_metric(run, "l6_answer_quality/query_count_scored", hidden=True)
    _safe_define_metric(run, "l6_answer_quality/metric_error_rate", summary="min")
    _safe_define_metric(run, "l6_answer_quality/metric_evaluations_failed", hidden=True)

    # Summary metrics
    _safe_define_metric(run, "summary/duration_s", summary="min")
    _safe_define_metric(run, "summary/failed_thresholds", summary="min")
    _safe_define_metric(run, "thresholds/failed_count", summary="min")

    # Note: wandb doesn't support glob patterns in define_metric
    # Additional metrics will be auto-created when logged in debug mode


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
            metrics["l6_answer_quality/query_count_scored"] = l6_answer_quality[
                "query_count_scored"
            ]
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
        "latency_p95_ms",
    ]:
        if key in retrieval:
            metrics[f"retrieval/{key}"] = retrieval[key]

    # Difficulty breakdowns (key for understanding performance across query types)
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

    # HyDe (Hypothetical Document Embeddings) metrics
    if retrieval.get("hyde_enabled"):
        metrics["retrieval/hyde_enabled"] = True
        metrics["retrieval/hyde_queries_count"] = retrieval.get("hyde_queries_count", 0)
        if retrieval.get("hyde_hit_rate") is not None:
            metrics["retrieval/hyde_hit_rate"] = retrieval["hyde_hit_rate"]
        if retrieval.get("hyde_mrr") is not None:
            metrics["retrieval/hyde_mrr"] = retrieval["hyde_mrr"]
        if retrieval.get("hyde_source_hit_rate") is not None:
            metrics["retrieval/hyde_source_hit_rate"] = retrieval["hyde_source_hit_rate"]

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


def _get_critical_metrics(
    retrieval: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Extract only the most critical metrics for high-level comparison."""
    metrics = {}

    # Core retrieval quality (5 metrics)
    metrics["retrieval/hit_rate"] = retrieval.get("hit_rate_at_k")
    metrics["retrieval/mrr"] = retrieval.get("mrr")
    metrics["retrieval/ndcg"] = retrieval.get("ndcg_at_k")
    metrics["retrieval/latency_p50_ms"] = retrieval.get("latency_p50_ms")

    # Pipeline health (2 metrics)
    metrics["summary/duration_s"] = summary.get("duration_s")
    metrics["summary/failed_thresholds"] = summary.get("failed_thresholds_count", 0)

    return metrics


def _wandb_tracking_config(experiment: dict[str, Any] | None) -> dict[str, Any]:
    return dict(((experiment or {}).get("tracking") or {}).get("wandb") or {})


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
    try:
        tracking_cfg = _wandb_tracking_config(experiment)
    except (TypeError, ValueError):
        return {"enabled": False, "status": "error", "error": "invalid tracking configuration"}
    if tracking_cfg.get("enabled") is not True:
        return {"enabled": False, "status": "disabled"}
    mode = tracking_cfg.get("mode", "online")
    if mode not in ("online", "offline", "disabled"):
        return {"enabled": True, "status": "error", "error": "invalid tracking mode"}

    run_path = Path(run_dir)
    artifact_export_enabled = tracking_cfg.get("log_artifacts") is True
    try:
        wandb = importlib.import_module("wandb")
    except Exception:
        logger.warning("W&B tracking requested but unavailable")
        return {
            "enabled": True,
            "status": "error",
            "error": "tracking unavailable",
            "artifact_export_enabled": artifact_export_enabled,
        }

    run = None
    try:
        verbosity = tracking_cfg.get("metrics_verbosity", "standard")
        if not isinstance(verbosity, str) or verbosity.lower() not in {
            "critical",
            "standard",
            "debug",
        }:
            verbosity = "standard"
        else:
            verbosity = verbosity.lower()

        # Do not forward the manifest or user-authored experiment fields to W&B.
        run = wandb.init(
            project=tracking_cfg.get("project"),
            entity=tracking_cfg.get("entity"),
            job_type="pipeline_eval",
            mode=mode,
            config={"structural_metadata": _safe_structural_config(experiment)},
        )

        _define_wandb_metrics(run, verbosity=verbosity)
        metrics: dict[str, Any] = {}

        if verbosity == "critical":
            metrics.update(_get_critical_metrics(retrieval_metrics, summary))
        elif verbosity == "standard":
            metrics.update(
                _extract_primary_metrics(retrieval_metrics, l6_answer_quality_metrics, summary)
            )
            metrics.update(_extract_secondary_metrics(retrieval_metrics))
        else:
            metrics.update(
                _extract_primary_metrics(retrieval_metrics, l6_answer_quality_metrics, summary)
            )
            metrics.update(_extract_secondary_metrics(retrieval_metrics))
            metrics.update(_extract_debug_metrics(retrieval_metrics, step_metrics))

        metrics["thresholds/failed_count"] = len(failed_thresholds)
        safe_metrics = _safe_metric_payload(metrics)
        if safe_metrics:
            run.log(safe_metrics)

        if artifact_export_enabled:
            logger.warning(
                "Legacy raw W&B artifact export explicitly enabled; this is not content-policy approval"
            )
            artifact = wandb.Artifact(name="pipeline-evaluation-artifacts", type="evaluation-run")
            artifact.add_dir(str(run_path))
            run.log_artifact(artifact)
        return {
            "enabled": True,
            "status": "logged",
            "artifact_export_enabled": artifact_export_enabled,
        }
    except Exception:
        logger.warning("W&B logging failed")
        return {
            "enabled": True,
            "status": "error",
            "error": "tracking failed",
            "artifact_export_enabled": artifact_export_enabled,
        }
    finally:
        if run is not None:
            try:
                run.finish()
            except Exception:
                logger.debug("Failed to finish W&B run cleanly")
