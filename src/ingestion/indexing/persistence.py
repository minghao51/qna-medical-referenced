"""Persistence helpers for vector store JSON files."""

import json
from pathlib import Path

from src.config import VECTOR_DIR

__all__ = ["VECTOR_DIR", "empty_documents", "load_documents", "save_documents"]


def empty_documents() -> dict:
    return {
        "ids": [],
        "contents": [],
        "embeddings": [],
        "metadatas": [],
        "content_hashes": [],
    }


def load_documents(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return empty_documents()


def save_documents(path: Path, documents: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(documents, f)
