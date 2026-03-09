"""Artifact writing helpers for evaluation runs."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _slugify(name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    return value or "run"


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
        pointer = self.base_dir / "latest_run.txt"
        pointer.write_text(str(self.run_dir), encoding="utf-8")
        return pointer
