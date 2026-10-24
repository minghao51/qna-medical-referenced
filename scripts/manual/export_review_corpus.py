#!/usr/bin/env python3
"""Deterministic, offline export of a review-manifest corpus JSON.

The FrozenCorpus consumer in ``src/evals/assessment/review_manifest_tool.py``
(``_freeze_corpus``) requires a corpus payload of exactly:

    {
        "sources": {<source_id>: {"content": <str>}},
        "documents": {<doc_id>: {"source_id": <str>, "content": <str>}},
    }

with no extra keys anywhere. This script produces that payload from the frozen
D11 Chroma collection.

Read-only: a ``chromadb.PersistentClient`` opens the collection and calls
``col.get(include=["documents", "metadatas"])``; no writes, deletes, or metadata
mutation occur. Remote Chroma servers are never contacted.

Source derivation (stated honestly): ``sources[source_id]["content"]`` is the
ordered concatenation of the frozen chunk texts for that source, joined by
``"\\n\\n"`` and ordered by ``(page, chunk_index, doc_id)``. The review tool's
quote binding is against this derived content, not against the original
document files.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

DocumentId = str
SourceId = str


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse CLI args: required chroma-dir and output, default collection name."""
    parser = argparse.ArgumentParser(
        description=(
            "Export a review-manifest corpus JSON from a frozen Chroma "
            "collection (read-only, deterministic)."
        )
    )
    parser.add_argument(
        "--chroma-dir",
        required=True,
        type=Path,
        help="Path to the read-only Chroma PersistentClient directory.",
    )
    parser.add_argument(
        "--collection",
        default="medical_docs",
        help="Chroma collection name (default: medical_docs).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination path for the exported corpus JSON.",
    )
    return parser.parse_args(argv)


def _refuse(reason: str) -> None:
    """Print a single-line refusal reason to stderr and exit closed with code 1."""
    print(reason, file=sys.stderr)
    raise SystemExit(1)


def _read_records(
    chroma_dir: Path, collection: str
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Open the collection read-only and return parallel (ids, docs, metadatas)."""
    import chromadb

    client = chromadb.PersistentClient(path=str(chroma_dir))
    col = client.get_collection(collection)
    if col.count() == 0:
        _refuse(f"collection '{collection}' has 0 records")
    result = col.get(include=["documents", "metadatas"])
    ids = result.get("ids") or []
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    if not ids or not documents or not metadatas:
        _refuse("collection get() returned no records")
    return ids, documents, metadatas


def _safe_int(value: Any) -> int:
    """Return int(value) or 0 when value is missing or not numeric."""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _build_payload(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate records and assemble the review-manifest corpus payload."""
    documents_out: dict[DocumentId, dict[str, str]] = {}
    grouped: dict[SourceId, list[tuple[int, int, DocumentId, str]]] = defaultdict(list)

    for doc_id, document, metadata in zip(ids, documents, metadatas, strict=True):
        if not isinstance(doc_id, str) or not doc_id:
            _refuse("collection contains an empty or non-string id")
        if not isinstance(document, str):
            _refuse("collection contains a non-string document content")
        if not isinstance(metadata, dict):
            _refuse("collection contains a record with missing metadata")
        source = metadata.get("source")
        if not isinstance(source, str) or not source:
            _refuse("collection contains a record missing a non-empty string 'source'")

        documents_out[doc_id] = {"source_id": source, "content": document}
        page = _safe_int(metadata.get("page"))
        chunk_index = _safe_int(metadata.get("chunk_index"))
        grouped[source].append((page, chunk_index, doc_id, document))

    sources: dict[SourceId, dict[str, str]] = {}
    for source_id, chunks in grouped.items():
        chunks.sort(key=lambda item: (item[0], item[1], item[2]))
        sources[source_id] = {"content": "\n\n".join(chunk[3] for chunk in chunks)}

    return {"sources": sources, "documents": documents_out}


def _write_atomic(output: Path, payload: dict[str, Any]) -> None:
    """Serialize deterministically and write atomically via temp file + fsync + replace."""
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=1) + "\n"
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".corpus-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, output)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def main(argv: Sequence[str] | None = None) -> int:
    """Run the export: parse args, read records, build payload, write atomically."""
    args = _parse_args(argv)
    ids, documents, metadatas = _read_records(args.chroma_dir, args.collection)
    payload = _build_payload(ids, documents, metadatas)
    _write_atomic(args.output, payload)
    print(
        f"wrote {args.output}: "
        f"{len(payload['documents'])} documents, {len(payload['sources'])} sources"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
