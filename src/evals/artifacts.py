"""Artifact writing helpers for evaluation runs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUN_INDEX_FILENAME = "run_index.json"


def _slugify(name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    return value or "run"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        to_serializable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def to_serializable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_serializable(v) for k, v in asdict(value).items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_serializable(v) for v in value]
    if hasattr(value, "model_dump"):
        return to_serializable(value.model_dump())  # pydantic v2
    return value


def build_run_identity(*, config: Any, git_head: str | None) -> str:
    payload = {"config": config, "git_head": git_head}
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _run_index_path(base_dir: Path) -> Path:
    return Path(base_dir) / RUN_INDEX_FILENAME


def _load_run_index(base_dir: Path) -> dict[str, Any]:
    payload = _load_json_file(_run_index_path(base_dir))
    if not payload:
        return {"entries": {}}
    entries = payload.get("entries", {})
    if not isinstance(entries, dict):
        return {"entries": {}}
    return {"entries": entries}


def _write_run_index(base_dir: Path, payload: dict[str, Any]) -> Path:
    path = _run_index_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_serializable(payload), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _candidate_run_dirs(base_dir: Path) -> list[Path]:
    resolved_base_dir = Path(base_dir)
    latest_pointer = resolved_base_dir / "latest_run.txt"
    candidates: list[Path] = []
    if latest_pointer.exists():
        latest_dir = Path(latest_pointer.read_text(encoding="utf-8").strip())
        if not latest_dir.is_absolute():
            latest_dir = Path.cwd() / latest_dir
        candidates.append(latest_dir)
    if resolved_base_dir.exists():
        candidates.extend(
            sorted(
                (path for path in resolved_base_dir.iterdir() if path.is_dir()),
                key=lambda path: path.name,
                reverse=True,
            )
        )
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def write_latest_pointer(base_dir: Path, run_dir: Path) -> Path:
    pointer = Path(base_dir) / "latest_run.txt"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(run_dir), encoding="utf-8")
    return pointer


def update_run_index(
    base_dir: Path,
    *,
    run_identity: str,
    run_dir: Path,
    status: str = "completed",
) -> Path:
    payload = _load_run_index(base_dir)
    payload["entries"][run_identity] = {
        "run_dir": str(run_dir),
        "status": status,
    }
    return _write_run_index(base_dir, payload)


def find_reusable_run(base_dir: Path, run_identity: str) -> Path | None:
    index = _load_run_index(base_dir)
    indexed_entry = index.get("entries", {}).get(run_identity)
    if isinstance(indexed_entry, dict):
        indexed_run_dir = indexed_entry.get("run_dir")
        if indexed_run_dir:
            candidate = Path(indexed_run_dir)
            manifest = _load_json_file(candidate / "manifest.json")
            summary = _load_json_file(candidate / "summary.json")
            if manifest and summary and manifest.get("run_identity") == run_identity:
                return candidate
    for run_dir in _candidate_run_dirs(Path(base_dir)):
        manifest = _load_json_file(run_dir / "manifest.json")
        summary = _load_json_file(run_dir / "summary.json")
        if not manifest or not summary:
            continue
        existing_identity = manifest.get("run_identity")
        if not existing_identity:
            existing_identity = build_run_identity(
                config=manifest.get("config"),
                git_head=manifest.get("git_head"),
            )
        if existing_identity == run_identity:
            update_run_index(base_dir, run_identity=run_identity, run_dir=run_dir)
            return run_dir
    return None


class ArtifactStore:
    """Handles creation and persistence of evaluation artifacts."""

    def __init__(self, base_dir: Path, run_name: str | None = None):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        suffix = _slugify(run_name or "pipeline-quality-assessment")
        self.run_dir = self.base_dir / f"{timestamp}_{suffix}"
        self.run_dir.mkdir(parents=True, exist_ok=False)

    def path(self, relative_name: str) -> Path:
        return self.run_dir / relative_name

    def write_json(self, relative_name: str, data: Any) -> Path:
        path = self.path(relative_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(to_serializable(data), f, indent=2, ensure_ascii=False)
        return path

    def write_jsonl(self, relative_name: str, rows: list[Any]) -> Path:
        path = self.path(relative_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(to_serializable(row), ensure_ascii=False))
                f.write("\n")
        return path

    def write_text(self, relative_name: str, content: str) -> Path:
        path = self.path(relative_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_latest_pointer(self) -> Path:
        return write_latest_pointer(self.base_dir, self.run_dir)
