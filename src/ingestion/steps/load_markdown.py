#!/usr/bin/env python3
"""
Load Markdown documents from data/raw for indexing.
"""

from pathlib import Path
from typing import List

from src.config import DATA_RAW_DIR


class MarkdownLoader:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else DATA_RAW_DIR

    def load_all_markdown(self) -> List[dict]:
        documents: List[dict] = []
        for md_file in sorted(self.data_dir.glob("*.md")):
            text = md_file.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                continue
            documents.append(
                {
                    "id": md_file.stem,
                    "source": md_file.name,
                    "content": text,
                }
            )
        return documents


def get_markdown_documents() -> List[dict]:
    loader = MarkdownLoader()
    return loader.load_all_markdown()

