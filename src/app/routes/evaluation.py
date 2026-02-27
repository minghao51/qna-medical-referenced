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
