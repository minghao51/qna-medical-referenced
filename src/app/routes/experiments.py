"""Experiment listing and results API endpoints.

Read-only endpoints for browsing experiment YAML configs and their
JSON output reports stored under experiments/.
"""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from src.experiments.config import load_experiment_file

logger = logging.getLogger(__name__)

router = APIRouter()

EXPERIMENTS_DIR = Path("experiments")
OUTPUTS_DIR = EXPERIMENTS_DIR / "outputs"


def _find_yaml_configs() -> list[Path]:
    yaml_files: list[Path] = []
    if not EXPERIMENTS_DIR.is_dir():
        return yaml_files
    for child in sorted(EXPERIMENTS_DIR.iterdir()):
        if child.suffix in (".yaml", ".yml"):
            yaml_files.append(child)
    if (EXPERIMENTS_DIR / "v1").is_dir():
        for child in sorted((EXPERIMENTS_DIR / "v1").iterdir()):
            if child.suffix in (".yaml", ".yml"):
                yaml_files.append(child)
    return yaml_files


def _find_output_reports() -> list[Path]:
    reports: list[Path] = []
    if not OUTPUTS_DIR.is_dir():
        return reports
    for child in sorted(OUTPUTS_DIR.iterdir()):
        if child.suffix == ".json" and child.name.endswith("_report.json"):
            reports.append(child)
    return reports


@router.get(
    "/experiments",
    summary="List experiment configs and output reports",
)
def list_experiments() -> dict[str, Any]:
    output_reports = _find_output_reports()
    configs: list[dict[str, Any]] = []
    for path in _find_yaml_configs():
        try:
            parsed = load_experiment_file(path)
            configs.append(
                {
                    "file": str(path),
                    "experiment_id": path.stem,
                    "name": parsed.get("metadata", {}).get("name", path.stem),
                    "description": parsed.get("metadata", {}).get("description", ""),
                    "variant_count": len(parsed.get("variants", [])),
                    "primary_metric": (
                        parsed.get("evaluation", {}).get("primary_metric", "ndcg@k")
                    ),
                    "has_results": any(r.name == f"{path.stem}_report.json" for r in output_reports),
                }
            )
        except Exception:
            logger.warning("Failed to parse experiment config %s", path, exc_info=True)

    reports: list[dict[str, Any]] = []
    for path in _find_output_reports():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            reports.append(
                {
                    "file": str(path),
                    "experiment_name": data.get("experiment_name", path.stem),
                    "timestamp": data.get("timestamp", ""),
                    "winner": data.get("winner", {}).get("name"),
                    "any_target_met": data.get("any_target_met"),
                }
            )
        except Exception:
            logger.warning("Failed to parse report %s", path, exc_info=True)

    return {"configs": configs, "reports": reports}


@router.get(
    "/experiments/{experiment_name}/results",
    summary="Get experiment results",
)
def get_experiment_results(experiment_name: str) -> dict[str, Any]:
    report_path = OUTPUTS_DIR / f"{experiment_name}_report.json"
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/experiments/{experiment_name}/config",
    summary="Get parsed experiment config",
)
def get_experiment_config(experiment_name: str) -> dict[str, Any]:
    candidates = [
        EXPERIMENTS_DIR / f"{experiment_name}.yaml",
        EXPERIMENTS_DIR / f"{experiment_name}.yml",
        EXPERIMENTS_DIR / "v1" / f"{experiment_name}.yaml",
        EXPERIMENTS_DIR / "v1" / f"{experiment_name}.yml",
    ]
    for path in candidates:
        if path.is_file():
            return load_experiment_file(path)
    raise HTTPException(status_code=404, detail="Experiment config not found")
