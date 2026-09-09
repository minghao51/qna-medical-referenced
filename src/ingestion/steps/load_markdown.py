#!/usr/bin/env python3
"""
Load Markdown documents from data/raw for indexing.
"""

from pathlib import Path

from src.config import DATA_RAW_DIR
from src.config.context import get_runtime_state
from src.core.source_metadata import build_document_source_metadata
from src.ingestion.artifacts import load_source_artifact
from src.ingestion.steps.download_web import (
    get_manifest_record_by_filename,
    get_manifest_record_by_logical_name,
)


def _is_index_only_classified_pages() -> bool:
    return bool(get_runtime_state().index_only_classified_pages)


def get_index_only_classified_pages() -> bool:
    return _is_index_only_classified_pages()


class MarkdownLoader:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else DATA_RAW_DIR

    def load_all_markdown(self) -> list[dict]:
        documents: list[dict] = []
        for md_file in sorted(self.data_dir.glob("*.md")):
            text = md_file.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                continue
            artifact = load_source_artifact("html", md_file.stem)
            if (
                _is_index_only_classified_pages()
                and artifact
                and not artifact.get("metadata", {}).get("indexable", True)
            ):
                continue

            # Lookup manifest record for additional metadata
            # Try .md filename first, then .html (original source), then by logical_name
            manifest_record = get_manifest_record_by_filename(md_file.name)
            if not manifest_record:
                # Try with .html extension (md file stem + .html)
                html_filename = md_file.stem + ".html"
                manifest_record = get_manifest_record_by_filename(html_filename)
            if not manifest_record:
                # Try by logical_name (md file stem)
                manifest_record = get_manifest_record_by_logical_name(md_file.stem)

            metadata = build_document_source_metadata(
                (artifact or {}).get("metadata"),
                source=md_file.name,
                source_type="html",
                manifest_record=manifest_record,
            )

            documents.append(
                {
                    "id": md_file.stem,
                    "source": md_file.name,
                    "content": text,
                    "source_type": "html",
                    "structured_blocks": (artifact or {}).get("structured_blocks", []),
                    "metadata": metadata,
                }
            )
        return documents


def get_markdown_documents() -> list[dict]:
    loader = MarkdownLoader()
    return loader.load_all_markdown()


def set_index_only_classified_pages(enabled: bool) -> None:
    get_runtime_state().index_only_classified_pages = bool(enabled)
