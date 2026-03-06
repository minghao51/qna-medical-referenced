"""Structured ingestion artifacts persisted between pipeline stages."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.config import DATA_PROCESSED_DIR


@dataclass
class SourceArtifact:
    source_id: str
    source_path: str
    source_type: str
    raw_source: dict[str, Any] = field(default_factory=dict)
    extracted_text: str = ""
    structured_blocks: list[dict[str, Any]] = field(default_factory=list)
    markdown_text: str = ""
    chunks: list[dict[str, Any]] = field(default_factory=list)
    best_output: dict[str, Any] = field(default_factory=dict)
    fallback_output: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedDocument:
    id: str
    source: str
    source_type: str
    extracted_text: str
    structured_blocks: list[dict[str, Any]] = field(default_factory=list)
    markdown_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    pages: list[dict[str, Any]] | None = None


@dataclass
class StructuredBlock:
    id: str
    block_type: str
    text: str
    section_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkRecord:
    id: str
    source: str
    page: int | None
    content: str
    content_type: str
    section_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def artifact_dir_for(source_type: str, source_id: str) -> Path:
    path = DATA_PROCESSED_DIR / source_type / source_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def persist_source_artifact(artifact: SourceArtifact) -> Path:
    target = artifact_dir_for(artifact.source_type, artifact.source_id) / "artifact.json"
    target.write_text(json.dumps(asdict(artifact), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_source_artifact(source_type: str, source_id: str) -> dict[str, Any] | None:
    target = artifact_dir_for(source_type, source_id) / "artifact.json"
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))
