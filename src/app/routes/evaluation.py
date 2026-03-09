"""Evaluation and metrics API endpoints.

This module provides endpoints for accessing evaluation results, metrics,
and historical trending data. Evaluation runs assess the quality of the
RAG pipeline using LLM-based judges and retrieval metrics.

Endpoints:
    - GET /evaluation/latest - Get latest evaluation run results
    - GET /evaluation/runs - List all evaluation runs
    - GET /evaluation/history - Get historical trending metrics
    - GET /evaluation/steps/{stage} - Get metrics for a specific pipeline stage

Example:
    Get latest evaluation:
        curl http://localhost:8001/evaluation/latest

    Get evaluation history:
        curl http://localhost:8001/evaluation/history?limit=20

    Get step metrics:
        curl http://localhost:8001/evaluation/steps/l2
"""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from src.experiments.wandb_history import fetch_wandb_run, fetch_wandb_runs

logger = logging.getLogger(__name__)

router = APIRouter()

EVALS_DIR = Path("data/evals")
LATEST_POINTER = Path("data/evals/latest_run.txt")


def _list_run_dirs() -> list[Path]:
    if not EVALS_DIR.exists():
        return []
    return sorted(
        [
            path
            for path in EVALS_DIR.iterdir()
            if path.is_dir() and "_" in path.name and path.name[0].isdigit()
        ],
        reverse=True,
    )


def _get_latest_run_dir() -> Path | None:
    """Get the latest evaluation run directory.

    First tries to read from the latest_run.txt pointer file.
    If that doesn't exist, falls back to finding the most recent directory
    by timestamp.

    Returns:
        Path to the latest run directory, or None if no runs exist
    """
    if LATEST_POINTER.exists():
        run_dir = Path(LATEST_POINTER.read_text().strip())
        if run_dir.exists():
            return run_dir
    runs = _list_run_dirs()
    return runs[0] if runs else None


def _get_all_runs() -> list[dict[str, Any]]:
    """Get all evaluation runs with basic metadata.

    Returns:
        List of dictionaries containing run_dir, status, duration_s,
        and failed_thresholds_count for each run
    """
    if not EVALS_DIR.exists():
        return []
    runs = _list_run_dirs()
    result = []
    for run_dir in runs:
        summary_path = run_dir / "summary.json"
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text())
                result.append(
                    {
                        "run_dir": str(run_dir.name),
                        "status": summary.get("status"),
                        "duration_s": summary.get("duration_s"),
                        "failed_thresholds_count": summary.get("failed_thresholds_count"),
                        "source": "local",
                        "tracking": summary.get("tracking", {}),
                    }
                )
            except Exception:
                result.append({"run_dir": str(run_dir.name), "status": "error", "source": "local"})
    return result


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _read_failed_thresholds(run_dir: Path) -> list[dict[str, Any]]:
    summary = _read_json_if_exists(run_dir / "summary.json")
    explicit = summary.get("failed_thresholds")
    if isinstance(explicit, list):
        return [item for item in explicit if isinstance(item, dict)]

    step_findings = _read_json_if_exists(run_dir / "step_findings.json")
    findings = step_findings if isinstance(step_findings, list) else []
    threshold_findings = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        if finding.get("stage") != "threshold":
            continue
        threshold_findings.append(
            {
                "metric": finding.get("metric"),
                "value": finding.get("value"),
                "threshold_op": finding.get("threshold_op"),
                "threshold_value": finding.get("threshold_value"),
                "message": finding.get("message"),
                "severity": finding.get("severity"),
            }
        )
    return threshold_findings


def _normalize_ablation_payload(payload: Any) -> dict[str, Any]:
    """Convert ablation data into the frontend's expected response shape."""
    if isinstance(payload, dict) and isinstance(payload.get("ablation_runs"), list):
        return payload

    if not isinstance(payload, dict):
        return {"ablation_runs": [], "message": "No ablation results available"}

    preferred_baselines = ("legacy_hybrid", "hybrid_rrf", "rrf_hybrid")
    baseline_strategy = next(
        (strategy for strategy in preferred_baselines if strategy in payload),
        next(iter(payload), None),
    )

    ablation_runs = []
    for strategy, metrics in payload.items():
        if not isinstance(metrics, dict):
            continue
        ablation_runs.append(
            {
                "strategy": strategy,
                "hit_rate_at_k": metrics.get("hit_rate_at_k", 0),
                "mrr": metrics.get("mrr", 0),
                "ndcg_at_k": metrics.get("ndcg_at_k", 0),
                "latency_p50_ms": metrics.get("latency_p50_ms"),
                "is_baseline": strategy == baseline_strategy,
            }
        )

    return {"ablation_runs": ablation_runs}


def _tracking_target_from_latest_local() -> tuple[str | None, str | None]:
    run_dir = _get_latest_run_dir()
    if not run_dir:
        return None, None
    manifest = _read_json_if_exists(run_dir / "manifest.json")
    summary = _read_json_if_exists(run_dir / "summary.json")
    summary_tracking = dict((summary.get("tracking") or {}).get("wandb") or {})
    if summary_tracking.get("project"):
        return summary_tracking.get("project"), summary_tracking.get("entity")
    experiment_cfg = (
        ((manifest.get("config") or {}).get("experiment_config") or {}).get("tracking") or {}
    ).get("wandb") or {}
    if experiment_cfg.get("project"):
        return experiment_cfg.get("project"), experiment_cfg.get("entity")
    return None, None


def _local_history_runs(limit: int) -> list[dict[str, Any]]:
    runs = _list_run_dirs()[:limit]
    result_runs = []
    for run_dir in runs:
        summary = _read_json_if_exists(run_dir / "summary.json")
        retrieval = _read_json_if_exists(run_dir / "retrieval_metrics.json")
        manifest = _read_json_if_exists(run_dir / "manifest.json")
        experiment_cfg = dict(((manifest.get("config") or {}).get("experiment_config")) or {})
        result_runs.append(
            {
                "run_dir": str(run_dir.name),
                "timestamp": run_dir.name.split("_")[0] if "_" in run_dir.name else "",
                "status": summary.get("status"),
                "duration_s": summary.get("duration_s", 0),
                "failed_thresholds_count": summary.get("failed_thresholds_count", 0),
                "retrieval_metrics": {
                    "hit_rate_at_k": retrieval.get("hit_rate_at_k", 0),
                    "mrr": retrieval.get("mrr", 0),
                    "ndcg_at_k": retrieval.get("ndcg_at_k", 0),
                    "latency_p50_ms": retrieval.get("latency_p50_ms", 0),
                    "latency_p95_ms": retrieval.get("latency_p95_ms", 0),
                    "precision_at_k": retrieval.get("precision_at_k", 0),
                    "recall_at_k": retrieval.get("recall_at_k", 0),
                },
                "source": "local",
                "experiment_name": (experiment_cfg.get("metadata") or {}).get("name"),
                "variant_name": experiment_cfg.get("variant_name"),
                "index_config_hash": (manifest.get("experiment") or {}).get("index_config_hash"),
                "wandb_url": (((summary.get("tracking") or {}).get("wandb") or {}).get("run_url")),
                "wandb_run_id": (
                    ((summary.get("tracking") or {}).get("wandb") or {}).get("run_id")
                ),
                "tracking": summary.get("tracking", {}),
            }
        )
    return result_runs


def _aggregate_history_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    metrics_tracking = {
        "hit_rate_at_k": [],
        "mrr": [],
        "ndcg_at_k": [],
        "latency_p50_ms": [],
        "latency_p95_ms": [],
        "duration_s": [],
    }
    source_breakdown: dict[str, int] = {}
    for run in runs:
        source = str(run.get("source") or "unknown")
        source_breakdown[source] = source_breakdown.get(source, 0) + 1
        retrieval = dict(run.get("retrieval_metrics") or {})
        for key in ("hit_rate_at_k", "mrr", "ndcg_at_k", "latency_p50_ms", "latency_p95_ms"):
            value = retrieval.get(key)
            if isinstance(value, (int, float)):
                metrics_tracking[key].append(value)
        duration = run.get("duration_s")
        if isinstance(duration, (int, float)):
            metrics_tracking["duration_s"].append(duration)
    return {
        "total_runs": len(runs),
        "avg_hit_rate": sum(metrics_tracking["hit_rate_at_k"])
        / len(metrics_tracking["hit_rate_at_k"])
        if metrics_tracking["hit_rate_at_k"]
        else 0,
        "avg_mrr": sum(metrics_tracking["mrr"]) / len(metrics_tracking["mrr"])
        if metrics_tracking["mrr"]
        else 0,
        "avg_latency_p50": sum(metrics_tracking["latency_p50_ms"])
        / len(metrics_tracking["latency_p50_ms"])
        if metrics_tracking["latency_p50_ms"]
        else 0,
        "avg_duration": sum(metrics_tracking["duration_s"]) / len(metrics_tracking["duration_s"])
        if metrics_tracking["duration_s"]
        else 0,
        "sources": source_breakdown,
    }


def _resolved_wandb_target(
    wandb_project: str | None = None, wandb_entity: str | None = None
) -> tuple[str | None, str | None]:
    resolved_project = wandb_project
    resolved_entity = wandb_entity
    if not resolved_project:
        resolved_project, resolved_entity = _tracking_target_from_latest_local()
        if wandb_entity:
            resolved_entity = wandb_entity
    return resolved_project, resolved_entity


@router.get(
    "/evaluation/latest",
    summary="Get latest evaluation results",
    description="Retrieve all metrics and results from the most recent evaluation run",
)
def get_latest_evaluation() -> dict[str, Any]:
    """Get the latest evaluation run results.

    Returns comprehensive data from the latest evaluation run including
    summary metrics, step-level metrics, retrieval metrics, and manifest.

    Returns:
        Dictionary containing:
            - run_dir: Name of the evaluation run directory
            - summary: Overall run status and metrics (if available)
            - step_metrics: Per-stage pipeline metrics (if available)
            - retrieval_metrics: Retrieval quality metrics (if available)
            - manifest: Run configuration and metadata (if available)

    Raises:
        HTTPException(404): If no evaluation runs exist

    Example:
        GET /evaluation/latest

        Response:
        {
            "run_dir": "250228T120000Z_abc123",
            "summary": {
                "status": "passed",
                "duration_s": 45.2,
                "failed_thresholds_count": 0
            },
            "retrieval_metrics": {
                "hit_rate_at_k": 0.85,
                "mrr": 0.72,
                "ndcg_at_k": 0.78
            }
        }
    """
    run_dir = _get_latest_run_dir()
    if not run_dir:
        raise HTTPException(status_code=404, detail="No evaluation runs found")

    summary_path = run_dir / "summary.json"
    step_metrics_path = run_dir / "step_metrics.json"
    retrieval_metrics_path = run_dir / "retrieval_metrics.json"
    manifest_path = run_dir / "manifest.json"

    result = {"run_dir": str(run_dir.name)}

    if summary_path.exists():
        result["summary"] = json.loads(summary_path.read_text())
    if step_metrics_path.exists():
        result["step_metrics"] = json.loads(step_metrics_path.read_text())
    if retrieval_metrics_path.exists():
        result["retrieval_metrics"] = json.loads(retrieval_metrics_path.read_text())
    if manifest_path.exists():
        result["manifest"] = json.loads(manifest_path.read_text())
    result["failed_thresholds"] = _read_failed_thresholds(run_dir)

    return result


@router.get(
    "/evaluation/runs",
    summary="List all evaluation runs",
    description="Get a list of all evaluation runs with basic metadata",
)
def get_evaluation_runs() -> list[dict[str, Any]]:
    """Get all evaluation runs with summary information.

    Returns a lightweight list of all runs with status and duration
    metadata. Useful for displaying a run history in a UI.

    Returns:
        List of dictionaries containing:
            - run_dir: Name of the evaluation run directory
            - status: Run status ("passed", "failed", "error")
            - duration_s: Run duration in seconds
            - failed_thresholds_count: Number of failed threshold checks

    Example:
        GET /evaluation/runs

        Response:
        [
            {
                "run_dir": "250228T120000Z_abc123",
                "status": "passed",
                "duration_s": 45.2,
                "failed_thresholds_count": 0
            },
            {
                "run_dir": "250228T110000Z_def456",
                "status": "failed",
                "duration_s": 38.1,
                "failed_thresholds_count": 2
            }
        ]
    """
    return _get_all_runs()


@router.get(
    "/evaluation/history",
    summary="Get evaluation trending metrics",
    description="Get historical evaluation metrics for trending analysis and performance monitoring",
)
def get_evaluation_history(
    limit: int = 10,
    source: str = "local",
    wandb_project: str | None = None,
    wandb_entity: str | None = None,
) -> dict[str, Any]:
    """Get historical evaluation metrics for trending analysis.

    Aggregates metrics across multiple evaluation runs to show trends
    over time. Computes averages for key metrics like hit rate, MRR,
    and latency.

    Args:
        limit: Maximum number of recent runs to include (default: 10)

    Returns:
        Dictionary containing:
            - runs: List of run data with timestamps and metrics
            - summary: Aggregated averages across all runs

    Example:
        GET /evaluation/history?limit=20

        Response:
        {
            "runs": [
                {
                    "run_dir": "250228T120000Z_abc123",
                    "timestamp": "250228T120000Z",
                    "status": "passed",
                    "retrieval_metrics": {
                        "hit_rate_at_k": 0.85,
                        "mrr": 0.72
                    }
                }
            ],
            "summary": {
                "total_runs": 10,
                "avg_hit_rate": 0.82,
                "avg_mrr": 0.70,
                "avg_latency_p50": 150
            }
        }
    """
    source_mode = str(source or "local").strip().lower()
    if source_mode not in {"local", "wandb", "all"}:
        raise HTTPException(status_code=400, detail="source must be one of: local, wandb, all")

    local_runs = _local_history_runs(limit) if source_mode in {"local", "all"} else []
    resolved_project, resolved_entity = _resolved_wandb_target(wandb_project, wandb_entity)
    warnings: list[str] = []
    wandb_result: dict[str, Any] = {"runs": [], "status": "disabled"}
    if source_mode in {"wandb", "all"}:
        wandb_result = fetch_wandb_runs(
            project=resolved_project or "",
            entity=resolved_entity,
            limit=limit,
        )
        if wandb_result.get("warning"):
            warnings.append(str(wandb_result["warning"]))

    result_runs = list(local_runs)
    result_runs.extend(list(wandb_result.get("runs", [])))
    result_runs = sorted(
        result_runs, key=lambda run: str(run.get("timestamp") or ""), reverse=True
    )[:limit]
    response = {
        "runs": result_runs,
        "summary": _aggregate_history_summary(result_runs),
        "sources": {
            "mode": source_mode,
            "wandb": {
                "status": wandb_result.get("status"),
                "project": wandb_result.get("project", resolved_project),
                "entity": wandb_result.get("entity", resolved_entity),
            },
        },
    }
    if warnings:
        response["warnings"] = warnings
    return response


@router.get("/evaluation/wandb/run/{run_ref}")
def get_wandb_evaluation_run(
    run_ref: str,
    wandb_project: str | None = None,
    wandb_entity: str | None = None,
) -> dict[str, Any]:
    resolved_project, resolved_entity = _resolved_wandb_target(wandb_project, wandb_entity)
    result = fetch_wandb_run(
        project=resolved_project or "",
        entity=resolved_entity,
        run_id=run_ref,
        run_name=run_ref,
    )
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"W&B run not found: {run_ref}")
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("warning", "Failed to load W&B run"))
    if result.get("status") == "disabled":
        raise HTTPException(
            status_code=400, detail=result.get("warning", "W&B project not configured")
        )

    run = dict(result.get("run") or {})
    return {
        "run_dir": run.get("run_dir", run_ref),
        "summary": {
            "run_dir": run.get("run_dir", run_ref),
            "duration_s": run.get("duration_s"),
            "retrieval_metrics": run.get("retrieval_metrics", {}),
            "rag_metrics": (run.get("summary") or {}).get("rag_metrics", {}),
            "failed_thresholds_count": run.get("failed_thresholds_count", 0),
            "status": run.get("status", "unknown"),
            "tracking": run.get("tracking", {}),
        },
        "retrieval_metrics": run.get("retrieval_metrics", {}),
        "manifest": run.get("manifest", {}),
        "source": "wandb",
        "tracking": run.get("tracking", {}),
        "wandb_run_id": run.get("wandb_run_id"),
        "wandb_url": run.get("wandb_url"),
    }


@router.get(
    "/evaluation/run/{run_dir}",
    summary="Get specific evaluation run",
    description="Get all metrics and results from a specific evaluation run",
)
def get_evaluation_run(run_dir: str) -> dict[str, Any]:
    """Get a specific evaluation run by directory name.

    Returns comprehensive data from the specified evaluation run including
    summary metrics, step-level metrics, retrieval metrics, and manifest.

    Args:
        run_dir: Name of the evaluation run directory

    Returns:
        Dictionary containing:
            - run_dir: Name of the evaluation run directory
            - summary: Overall run status and metrics (if available)
            - step_metrics: Per-stage pipeline metrics (if available)
            - retrieval_metrics: Retrieval quality metrics (if available)
            - manifest: Run configuration and metadata (if available)

    Raises:
        HTTPException(404): If run directory doesn't exist

    Example:
        GET /evaluation/run/250228T120000Z_abc123
    """
    target_dir = EVALS_DIR / run_dir
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run directory not found: {run_dir}")

    result = {"run_dir": run_dir}

    summary_path = target_dir / "summary.json"
    step_metrics_path = target_dir / "step_metrics.json"
    retrieval_metrics_path = target_dir / "retrieval_metrics.json"
    manifest_path = target_dir / "manifest.json"

    if summary_path.exists():
        result["summary"] = json.loads(summary_path.read_text())
    if step_metrics_path.exists():
        result["step_metrics"] = json.loads(step_metrics_path.read_text())
    if retrieval_metrics_path.exists():
        result["retrieval_metrics"] = json.loads(retrieval_metrics_path.read_text())
    if manifest_path.exists():
        result["manifest"] = json.loads(manifest_path.read_text())
    result["failed_thresholds"] = _read_failed_thresholds(target_dir)

    return result


@router.get(
    "/evaluation/ablation",
    summary="Get ablation study results",
    description="Get retrieval strategy comparison from ablation study",
)
def get_ablation_results() -> dict[str, Any]:
    """Get ablation study results comparing different retrieval strategies.

    Returns results from ablation studies that compare different retrieval
    approaches (e.g., hybrid vs. semantic-only vs. keyword-only).

    Returns:
        Dictionary containing:
            - ablation_runs: List of ablation results with metrics
            - is_baseline: Which run was the baseline

    Raises:
        HTTPException(404): If no evaluation runs or ablation data exists

    Example:
        GET /evaluation/ablation

        Response:
        {
            "ablation_runs": [
                {
                    "strategy": "hybrid_rrf",
                    "hit_rate_at_k": 0.85,
                    "mrr": 0.72,
                    "ndcg_at_k": 0.78,
                    "latency_p50_ms": 150,
                    "is_baseline": true
                },
                {
                    "strategy": "semantic_only",
                    "hit_rate_at_k": 0.80,
                    "mrr": 0.68,
                    "ndcg_at_k": 0.75,
                    "latency_p50_ms": 120
                }
            ]
        }
    """
    run_dir = _get_latest_run_dir()
    if not run_dir:
        raise HTTPException(status_code=404, detail="No evaluation runs found")

    candidate_paths = [
        run_dir / "ablation_results.json",
        run_dir / "retrieval_ablations.json",
    ]
    ablation_path = next((path for path in candidate_paths if path.exists()), None)
    if not ablation_path:
        return {"ablation_runs": [], "message": "No ablation results available"}

    try:
        return _normalize_ablation_payload(json.loads(ablation_path.read_text()))
    except Exception as e:
        logger.error(f"Failed to load ablation results: {e}")
        return {"ablation_runs": [], "error": str(e)}


@router.get(
    "/evaluation/steps/{stage}/records",
    summary="Get detailed records for a stage",
    description="Get detailed records for debugging and drill-down",
)
def get_step_records(stage: str, limit: int = 100) -> dict[str, Any]:
    """Get detailed records for a specific pipeline stage.

    Returns individual records for a stage, useful for debugging
    and understanding which specific documents/chunks have issues.

    Args:
        stage: Pipeline stage identifier (l0, l1, l2, l3, l4, l5)
        limit: Maximum number of records to return (default: 100)

    Returns:
        Dictionary containing:
            - stage: Stage name
            - records: Array of detailed records
            - total_count: Total number of records available

    Raises:
        HTTPException(404): If no evaluation runs exist
        HTTPException(400): If stage name is invalid

    Example:
        GET /evaluation/steps/l3/records?limit=50
    """
    run_dir = _get_latest_run_dir()
    if not run_dir:
        raise HTTPException(status_code=404, detail="No evaluation runs found")

    valid_stages = ["l0", "l1", "l2", "l3", "l4", "l5"]
    if stage.lower() not in valid_stages:
        raise HTTPException(
            status_code=400, detail=f"Invalid stage. Must be one of: {valid_stages}"
        )

    step_metrics_path = run_dir / "step_metrics.json"
    if not step_metrics_path.exists():
        raise HTTPException(status_code=404, detail="Step metrics not found")

    step_metrics = json.loads(step_metrics_path.read_text())
    stage_data = step_metrics.get(stage.lower(), {})
    records = stage_data.get("records", [])

    return {"stage": stage, "records": records[:limit], "total_count": len(records)}


@router.get(
    "/evaluation/steps/{stage}",
    summary="Get pipeline stage metrics",
    description="Get detailed metrics for a specific pipeline stage (L0-L5)",
)
def get_step_metrics(stage: str) -> dict[str, Any]:
    """Get metrics for a specific pipeline stage.

    Retrieves detailed step-level metrics for the specified pipeline stage.
    Stages are labeled L0 through L5 representing different processing steps.

    Args:
        stage: Pipeline stage identifier (l0, l1, l2, l3, l4, l5)

    Returns:
        Dictionary containing stage-specific metrics including
        timing, document counts, and quality assessments

    Raises:
        HTTPException(404): If no evaluation runs exist
        HTTPException(400): If stage name is invalid
        HTTPException(404): If step metrics file doesn't exist

    Example:
        GET /evaluation/steps/l2

        Response:
        {
            "input_doc_count": 100,
            "output_doc_count": 95,
            "timing_ms": 250,
            "quality_score": 0.92
        }
    """
    run_dir = _get_latest_run_dir()
    if not run_dir:
        raise HTTPException(status_code=404, detail="No evaluation runs found")

    valid_stages = ["l0", "l1", "l2", "l3", "l4", "l5"]
    if stage.lower() not in valid_stages:
        raise HTTPException(
            status_code=400, detail=f"Invalid stage. Must be one of: {valid_stages}"
        )

    step_metrics_path = run_dir / "step_metrics.json"
    if not step_metrics_path.exists():
        raise HTTPException(status_code=404, detail="Step metrics not found")

    step_metrics = json.loads(step_metrics_path.read_text())
    return step_metrics.get(stage.lower(), {"error": "Stage not found in metrics"})
