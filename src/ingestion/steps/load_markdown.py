#!/usr/bin/env python3
"""
Load Markdown documents from data/raw for indexing.
"""

from pathlib import Path
from typing import List

from src.config import DATA_RAW_DIR
from src.ingestion.artifacts import load_source_artifact
from src.ingestion.steps.download_web import (
    get_manifest_record_by_filename,
    get_manifest_record_by_logical_name,
)

INDEX_ONLY_CLASSIFIED_PAGES = True


class MarkdownLoader:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else DATA_RAW_DIR

    def load_all_markdown(self) -> List[dict]:
        documents: List[dict] = []
        for md_file in sorted(self.data_dir.glob("*.md")):
            text = md_file.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                continue
            artifact = load_source_artifact("html", md_file.stem)
            if (
                INDEX_ONLY_CLASSIFIED_PAGES
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

            metadata = (artifact or {}).get("metadata", {}).copy()
            if manifest_record:
                metadata["logical_name"] = manifest_record.get("logical_name")
                metadata["source_url"] = manifest_record.get("url")

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


def get_markdown_documents() -> List[dict]:
    loader = MarkdownLoader()
    return loader.load_all_markdown()


def set_index_only_classified_pages(enabled: bool) -> None:
    global INDEX_ONLY_CLASSIFIED_PAGES
    INDEX_ONLY_CLASSIFIED_PAGES = bool(enabled)
