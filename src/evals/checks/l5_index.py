"""L5 index quality checks."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.config import VECTOR_DIR, settings


def assess_l5_index_quality(
    vector_dir: Path | None = None,
    collection_name: str | None = None,
) -> dict[str, Any]:
    vdir = Path(vector_dir or VECTOR_DIR)
    coll = collection_name or settings.collection_name
    vector_path = vdir / f"{coll}.json"
    if not vector_path.exists():
        return {
            "aggregate": {"index_exists": False, "vector_path": str(vector_path)},
            "records": [],
            "findings": [
                {"severity": "warning", "message": "Vector index file missing", "stage": "L5"}
            ],
        }

    data = json.loads(vector_path.read_text(encoding="utf-8"))
    ids = data.get("ids", [])
    contents = data.get("contents", [])
    embeddings = data.get("embeddings", [])
    metadatas = data.get("metadatas", [])
    content_hashes = data.get("content_hashes", [])
    lengths = [len(e) for e in embeddings if isinstance(e, list)]
    source_counter = Counter((m or {}).get("source", "unknown") for m in metadatas)
    source_type_counter = Counter((m or {}).get("source_type", "unknown") for m in metadatas)
    source_class_counter = Counter((m or {}).get("source_class", "unknown") for m in metadatas)
    records = [
        {
            "id": ids[i] if i < len(ids) else None,
            "source": (metadatas[i] or {}).get("source", "unknown")
            if i < len(metadatas)
            else "unknown",
            "content_chars": len(contents[i])
            if i < len(contents) and isinstance(contents[i], str)
            else 0,
            "embedding_dim": len(embeddings[i])
            if i < len(embeddings) and isinstance(embeddings[i], list)
            else 0,
        }
        for i in range(min(len(ids), len(contents), len(embeddings), len(metadatas)))
    ]
    findings = []
    lengths_equal = len(ids) == len(contents) == len(embeddings) == len(metadatas)
    if not lengths_equal:
        findings.append(
            {"severity": "error", "message": "Vector arrays have mismatched lengths", "stage": "L5"}
        )
    unique_dims = sorted(set(lengths))
    index_metadata = data.get("index_metadata", {})
    if len(unique_dims) > 1:
        findings.append(
            {"severity": "error", "message": "Embedding dimensions are inconsistent", "stage": "L5"}
        )

    aggregate = {
        "index_exists": True,
        "vector_path": str(vector_path),
        "ids_count": len(ids),
        "contents_count": len(contents),
        "embeddings_count": len(embeddings),
        "metadatas_count": len(metadatas),
        "content_hashes_count": len(content_hashes),
        "lengths_consistent": lengths_equal,
        "embedding_dim_consistent": len(unique_dims) <= 1,
        "embedding_dim": unique_dims[0] if len(unique_dims) == 1 else None,
        "embedding_model": index_metadata.get("embedding_model"),
        "embedding_batch_size": index_metadata.get("embedding_batch_size"),
        "index_config_hash": index_metadata.get("index_config_hash"),
        "short_content_rate": (
            sum(1 for c in contents if isinstance(c, str) and len(c.strip()) < 20) / len(contents)
        )
        if contents
        else 0.0,
        "source_distribution": dict(source_counter),
        "source_type_distribution": dict(source_type_counter),
        "source_class_distribution": dict(source_class_counter),
        "dedupe_effect_estimate": max(0, len(content_hashes) - len(contents)),
        "index_file_size_bytes": vector_path.stat().st_size,
    }
    return {"aggregate": aggregate, "records": records, "findings": findings}
