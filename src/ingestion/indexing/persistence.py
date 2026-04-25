"""Persistence helpers for vector store JSON files."""

import json
from pathlib import Path
from typing import Any, cast

from src.config import VECTOR_DIR

__all__ = ["VECTOR_DIR", "empty_documents", "load_documents", "save_documents"]


def empty_documents() -> dict[str, Any]:
    return {
        "ids": [],
        "contents": [],
        "embeddings": [],
        "metadatas": [],
        "content_hashes": [],
        "index_metadata": {},
    }


def load_documents(path: Path) -> dict[str, Any]:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            loaded = cast(dict[str, Any], json.load(f))
            if "index_metadata" not in loaded:
                loaded["index_metadata"] = {}
            return loaded
    return empty_documents()


def save_documents(path: Path, documents: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(documents, f)
