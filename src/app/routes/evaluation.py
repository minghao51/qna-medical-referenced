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

logger = logging.getLogger(__name__)

router = APIRouter()

EVALS_DIR = Path("data/evals")
LATEST_POINTER = Path("data/evals/latest_run.txt")


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
    runs = sorted(EVALS_DIR.glob("??????T??????Z_*"), reverse=True)
    return runs[0] if runs else None


def _get_all_runs() -> list[dict[str, Any]]:
    """Get all evaluation runs with basic metadata.

    Returns:
        List of dictionaries containing run_dir, status, duration_s,
        and failed_thresholds_count for each run
    """
    if not EVALS_DIR.exists():
        return []
    runs = sorted(EVALS_DIR.glob("??????T??????Z_*"), reverse=True)
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
                    }
                )
            except Exception:
                result.append({"run_dir": str(run_dir.name), "status": "error"})
    return result


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
def get_evaluation_history(limit: int = 10) -> dict[str, Any]:
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
    if not EVALS_DIR.exists():
        return {"runs": [], "metrics": []}

    runs = sorted(EVALS_DIR.glob("??????T??????Z_*"), reverse=True)[:limit]

    result_runs = []
    metrics_tracking = {
        "hit_rate_at_k": [],
        "mrr": [],
        "ndcg_at_k": [],
        "latency_p50_ms": [],
        "latency_p95_ms": [],
        "failed_thresholds": [],
        "duration_s": [],
    }

    for run_dir in runs:
        summary_path = run_dir / "summary.json"
        retrieval_path = run_dir / "retrieval_metrics.json"

        run_data: dict[str, Any] = {
            "run_dir": str(run_dir.name),
            "timestamp": run_dir.name.split("_")[0] if "_" in run_dir.name else "",
        }

        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text())
                run_data["status"] = summary.get("status")
                run_data["duration_s"] = summary.get("duration_s", 0)
                run_data["failed_thresholds_count"] = summary.get("failed_thresholds_count", 0)

                metrics_tracking["failed_thresholds"].append(
                    summary.get("failed_thresholds_count", 0)
                )
                metrics_tracking["duration_s"].append(summary.get("duration_s", 0))
            except Exception:
                pass

        if retrieval_path.exists():
            try:
                retrieval = json.loads(retrieval_path.read_text())
                run_data["retrieval_metrics"] = {
                    "hit_rate_at_k": retrieval.get("hit_rate_at_k", 0),
                    "mrr": retrieval.get("mrr", 0),
                    "ndcg_at_k": retrieval.get("ndcg_at_k", 0),
                    "latency_p50_ms": retrieval.get("latency_p50_ms", 0),
                    "latency_p95_ms": retrieval.get("latency_p95_ms", 0),
                }

                metrics_tracking["hit_rate_at_k"].append(retrieval.get("hit_rate_at_k", 0))
                metrics_tracking["mrr"].append(retrieval.get("mrr", 0))
                metrics_tracking["ndcg_at_k"].append(retrieval.get("ndcg_at_k", 0))
                metrics_tracking["latency_p50_ms"].append(retrieval.get("latency_p50_ms", 0))
                metrics_tracking["latency_p95_ms"].append(retrieval.get("latency_p95_ms", 0))
            except Exception:
                pass

        result_runs.append(run_data)

    return {
        "runs": result_runs,
        "summary": {
            "total_runs": len(result_runs),
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
            "avg_duration": sum(metrics_tracking["duration_s"])
            / len(metrics_tracking["duration_s"])
            if metrics_tracking["duration_s"]
            else 0,
        },
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

    ablation_path = run_dir / "ablation_results.json"
    if not ablation_path.exists():
        return {"ablation_runs": [], "message": "No ablation results available"}

    try:
        return json.loads(ablation_path.read_text())
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
