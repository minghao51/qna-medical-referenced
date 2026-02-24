"""Persistence helpers for vector store JSON files."""

import json
from pathlib import Path

DATA_DIR = Path("data")
VECTOR_DIR = DATA_DIR / "vectors"
VECTOR_DIR.mkdir(exist_ok=True)


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
        with open(path, "r") as f:
            return json.load(f)
    return empty_documents()


def save_documents(path: Path, documents: dict) -> None:
    with open(path, "w") as f:
        json.dump(documents, f)

