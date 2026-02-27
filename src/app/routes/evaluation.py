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
    if LATEST_POINTER.exists():
        run_dir = Path(LATEST_POINTER.read_text().strip())
        if run_dir.exists():
            return run_dir
    runs = sorted(EVALS_DIR.glob("??????T??????Z_*"), reverse=True)
    return runs[0] if runs else None


def _get_all_runs() -> list[dict[str, Any]]:
    if not EVALS_DIR.exists():
        return []
    runs = sorted(EVALS_DIR.glob("??????T??????Z_*"), reverse=True)
    result = []
    for run_dir in runs:
        summary_path = run_dir / "summary.json"
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text())
                result.append({
                    "run_dir": str(run_dir.name),
                    "status": summary.get("status"),
                    "duration_s": summary.get("duration_s"),
                    "failed_thresholds_count": summary.get("failed_thresholds_count"),
                })
            except Exception:
                result.append({"run_dir": str(run_dir.name), "status": "error"})
    return result


@router.get("/evaluation/latest")
def get_latest_evaluation() -> dict[str, Any]:
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


@router.get("/evaluation/runs")
def get_evaluation_runs() -> list[dict[str, Any]]:
    return _get_all_runs()


@router.get("/evaluation/history")
def get_evaluation_history(limit: int = 10) -> dict[str, Any]:
    """Get historical evaluation metrics for trending analysis."""
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
        "duration_s": []
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
                
                metrics_tracking["failed_thresholds"].append(summary.get("failed_thresholds_count", 0))
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
            "avg_hit_rate": sum(metrics_tracking["hit_rate_at_k"]) / len(metrics_tracking["hit_rate_at_k"]) if metrics_tracking["hit_rate_at_k"] else 0,
            "avg_mrr": sum(metrics_tracking["mrr"]) / len(metrics_tracking["mrr"]) if metrics_tracking["mrr"] else 0,
            "avg_latency_p50": sum(metrics_tracking["latency_p50_ms"]) / len(metrics_tracking["latency_p50_ms"]) if metrics_tracking["latency_p50_ms"] else 0,
            "avg_duration": sum(metrics_tracking["duration_s"]) / len(metrics_tracking["duration_s"]) if metrics_tracking["duration_s"] else 0,
        }
    }


@router.get("/evaluation/steps/{stage}")
def get_step_metrics(stage: str) -> dict[str, Any]:
    run_dir = _get_latest_run_dir()
    if not run_dir:
        raise HTTPException(status_code=404, detail="No evaluation runs found")

    valid_stages = ["l0", "l1", "l2", "l3", "l4", "l5"]
    if stage.lower() not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {valid_stages}")

    step_metrics_path = run_dir / "step_metrics.json"
    if not step_metrics_path.exists():
        raise HTTPException(status_code=404, detail="Step metrics not found")

    step_metrics = json.loads(step_metrics_path.read_text())
    return step_metrics.get(stage.lower(), {"error": "Stage not found in metrics"})
