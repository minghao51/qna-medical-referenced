"""Read-only experiment config and archived-report inspection endpoints."""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request

from src.config.paths import PROJECT_ROOT
from src.experiments.config import load_experiment_file

logger = logging.getLogger(__name__)

router = APIRouter()

EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"
OUTPUTS_DIR = EXPERIMENTS_DIR / "outputs"
_MAX_FILE_BYTES = 5 * 1024 * 1024
_KNOWN_CONFIG_REFS = {"medical_semantic_chunking_exp": "medical_semantic_exp"}
_REPORT_BY_CONFIG = {config: report for report, config in _KNOWN_CONFIG_REFS.items()}
_EXPERIMENT_NAME_RE = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9._-]*$")


def _require_authenticated_request(request: Request) -> None:
    if getattr(request.state, "auth", None) is None:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")


def _validate_experiment_name(name: str) -> None:
    if not name or name in {".", ".."} or not _EXPERIMENT_NAME_RE.fullmatch(name):
        raise HTTPException(
            status_code=400,
            detail="Invalid experiment name. Only alphanumeric characters, dots, underscores, and hyphens are allowed.",
        )


def _safe_file(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_file() and path.resolve().is_relative_to(root.resolve())
    except (OSError, RuntimeError):
        return False


def _read_bounded(path: Path, root: Path) -> tuple[bytes | None, str | None]:
    if not _safe_file(path, root):
        return None, "missing"
    try:
        with path.open("rb") as handle:
            data = handle.read(_MAX_FILE_BYTES + 1)
    except OSError:
        return None, "unavailable"
    return (None, "oversized") if len(data) > _MAX_FILE_BYTES else (data, None)


def _report_schema(data: Any) -> str | None:
    if not isinstance(data, dict) or not isinstance(data.get("experiment_name"), str):
        return None
    if not isinstance(data.get("winner"), (dict, type(None))):
        return None
    if not isinstance(data.get("any_target_met"), (bool, type(None))):
        return None
    if not isinstance(data.get("timestamp"), str):
        return None
    for key, expected in (("baseline", dict), ("variants", list), ("config", dict)):
        if not isinstance(data.get(key), expected):
            return None
    return "legacy_feature_addition"


def _report_entry(path: Path) -> dict[str, Any]:
    report_id = path.name.removesuffix("_report.json")
    raw, problem = _read_bounded(path, OUTPUTS_DIR)
    entry: dict[str, Any] = {
        "file": f"outputs/{path.name}",
        "report_id": report_id,
        "schema_kind": "unsupported",
        "report_sha256": None,
        "config_ref": _KNOWN_CONFIG_REFS.get(report_id),
        "availability": "unavailable",
    }
    if not _EXPERIMENT_NAME_RE.fullmatch(report_id):
        entry["error"] = "invalid_report_id"
        return entry
    if raw is None:
        entry["error"] = problem or "unavailable"
        return entry
    entry["report_sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        entry["error"] = "malformed"
        return entry
    schema_kind = _report_schema(data)
    if schema_kind is None:
        entry["availability"] = "unsupported"
        return entry
    winner = data.get("winner")
    entry.update(
        schema_kind=schema_kind,
        availability="available",
        experiment_name=data.get("experiment_name", report_id),
        timestamp=data.get("timestamp", ""),
        winner=winner.get("name") if isinstance(winner, dict) else None,
        any_target_met=data.get("any_target_met"),
    )
    return entry


def _find_yaml_configs() -> list[Path]:
    if not EXPERIMENTS_DIR.is_dir():
        return []
    roots = [EXPERIMENTS_DIR, EXPERIMENTS_DIR / "v1"]
    return [
        child
        for root in roots
        if root.is_dir()
        for child in sorted(root.iterdir())
        if child.suffix in (".yaml", ".yml")
        and _EXPERIMENT_NAME_RE.fullmatch(child.stem)
        and _safe_file(child, EXPERIMENTS_DIR)
    ]


def _find_output_reports() -> list[Path]:
    if not OUTPUTS_DIR.is_dir():
        return []
    return [
        child
        for child in sorted(OUTPUTS_DIR.iterdir())
        if child.suffix == ".json" and child.name.endswith("_report.json")
    ]


def _associated_report_ids(config_id: str) -> set[str]:
    alias = _REPORT_BY_CONFIG.get(config_id)
    return {config_id, alias} if alias else {config_id}


def _config_entry(path: Path, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    experiment_id = path.stem
    entry: dict[str, Any] = {
        "file": str(path.relative_to(EXPERIMENTS_DIR)),
        "experiment_id": experiment_id,
        "name": experiment_id,
        "description": "",
        "variant_count": 0,
        "primary_metric": None,
        "has_results": any(
            reports.get(report_id, {}).get("availability") == "available"
            for report_id in _associated_report_ids(experiment_id)
        ),
        "availability": "error",
    }
    raw, problem = _read_bounded(path, EXPERIMENTS_DIR)
    if raw is None:
        entry["error"] = problem or "unavailable"
        return entry
    try:
        parsed = load_experiment_file(path, raw_text=raw.decode("utf-8"))
    except Exception:
        logger.warning("Failed to parse experiment config %s", experiment_id)
        entry["error"] = "malformed_config"
        return entry
    metadata = parsed.get("metadata", {})
    evaluation = parsed.get("evaluation", {})
    entry.update(
        name=metadata.get("name", experiment_id),
        description=metadata.get("description", ""),
        variant_count=len(parsed.get("variants", [])),
        primary_metric=evaluation.get("primary_metric"),
        availability="available",
    )
    return entry


@router.get("/experiments", summary="List experiment configs and output reports")
def list_experiments(request: Request) -> dict[str, Any]:
    _require_authenticated_request(request)
    reports = {
        path.name.removesuffix("_report.json"): _report_entry(path)
        for path in _find_output_reports()
    }
    configs = [_config_entry(path, reports) for path in _find_yaml_configs()]
    return {"configs": configs, "reports": list(reports.values())}


@router.get("/experiments/{experiment_name}/results", summary="Get experiment results")
def get_experiment_results(experiment_name: str, request: Request) -> dict[str, Any]:
    _require_authenticated_request(request)
    _validate_experiment_name(experiment_name)
    raw, problem = _read_bounded(OUTPUTS_DIR / f"{experiment_name}_report.json", OUTPUTS_DIR)
    if problem in {"missing", "unavailable"}:
        raise HTTPException(status_code=404, detail="Report not found")
    if problem:
        raise HTTPException(status_code=422, detail="Report unavailable")
    if raw is None:
        raise HTTPException(status_code=404, detail="Report not found")
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Report unavailable") from exc
    schema_kind = _report_schema(data)
    if schema_kind is None:
        raise HTTPException(status_code=422, detail="Report schema unsupported")
    data = cast(dict[str, Any], data)
    data["_artifact"] = {
        "report_id": experiment_name,
        "report_sha256": hashlib.sha256(raw).hexdigest(),
        "schema_kind": schema_kind,
        "availability": "available",
        "config_ref": _KNOWN_CONFIG_REFS.get(experiment_name),
        "config_binding": (
            "explicit_archive_association" if experiment_name in _KNOWN_CONFIG_REFS else None
        ),
        "case_records_availability": "not_exposed_by_report_api",
        "comparable": False,
    }
    return data


@router.get("/experiments/{experiment_name}/config", summary="Get parsed experiment config")
def get_experiment_config(experiment_name: str, request: Request) -> dict[str, Any]:
    _require_authenticated_request(request)
    _validate_experiment_name(experiment_name)
    for path in [
        EXPERIMENTS_DIR / f"{experiment_name}.yaml",
        EXPERIMENTS_DIR / f"{experiment_name}.yml",
        EXPERIMENTS_DIR / "v1" / f"{experiment_name}.yaml",
        EXPERIMENTS_DIR / "v1" / f"{experiment_name}.yml",
    ]:
        raw, _ = _read_bounded(path, EXPERIMENTS_DIR)
        if raw is None:
            continue
        return load_experiment_file(path, raw_text=raw.decode("utf-8"))
    raise HTTPException(status_code=404, detail="Experiment config not found")
