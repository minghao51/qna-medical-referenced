#!/usr/bin/env python3
"""
Load Markdown documents from data/raw for indexing.
"""

from pathlib import Path
from typing import List

from src.config import DATA_RAW_DIR
from src.ingestion.artifacts import load_source_artifact

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
            if INDEX_ONLY_CLASSIFIED_PAGES and artifact and not artifact.get("metadata", {}).get("indexable", True):
                continue
            documents.append(
                {
                    "id": md_file.stem,
                    "source": md_file.name,
                    "content": text,
                    "source_type": "html",
                    "structured_blocks": (artifact or {}).get("structured_blocks", []),
                    "metadata": (artifact or {}).get("metadata", {}),
                }
            )
        return documents


def get_markdown_documents() -> List[dict]:
    loader = MarkdownLoader()
    return loader.load_all_markdown()


def set_index_only_classified_pages(enabled: bool) -> None:
    global INDEX_ONLY_CLASSIFIED_PAGES
    INDEX_ONLY_CLASSIFIED_PAGES = bool(enabled)
