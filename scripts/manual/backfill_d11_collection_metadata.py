#!/usr/bin/env python3
"""Backfill D11 build metadata onto an existing local Chroma collection.

The materialized D11 collection (``data/chroma-d11``) was created before
``ChromaVectorStore`` attached build metadata at collection creation, so the
D11 snapshot builder rejects it with "Index build metadata is missing". This
script computes the same payload as
``src.ingestion.indexing.store.build_collection_build_metadata`` - with the
corpus digest always computed from the configured raw data directory, never
overridden - and writes it onto the existing collection via
``collection.modify(metadata=...)``, merged over the existing metadata so
unrelated existing keys survive (payload values win conflicts).

Offline and local-only: a ``chromadb.PersistentClient`` over ``--chroma-dir``;
remote Chroma servers are never contacted. Idempotent: when the collection
already carries every required metadata value (``source_chunk_configs``
compared as parsed JSON), it reports "already up to date" without writing.
Fail closed: a missing collection, an unavailable corpus digest, or a failed
write/verification exits nonzero and never claims success. Only metadata key
names are printed - never values, contents, or exception internals.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHROMA_DIR = PROJECT_ROOT / "data/chroma-d11"
DEFAULT_COLLECTION_NAME = "medical_docs"


def _json_normalized(metadata: dict[str, Any]) -> dict[str, Any]:
    """Copy metadata with ``source_chunk_configs`` parsed so JSON strings compare equal."""
    normalized = dict(metadata)
    raw = normalized.get("source_chunk_configs")
    if isinstance(raw, str):
        try:
            normalized["source_chunk_configs"] = json.loads(raw)
        except json.JSONDecodeError:
            normalized["source_chunk_configs"] = None
    return normalized


def main(argv: Sequence[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    parser = argparse.ArgumentParser(
        description=(
            "Backfill collection build metadata onto an existing local Chroma "
            "collection (offline, idempotent, fail-closed)."
        )
    )
    parser.add_argument(
        "--chroma-dir",
        type=Path,
        default=DEFAULT_CHROMA_DIR,
        help="Local Chroma persistence directory (default: data/chroma-d11).",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION_NAME,
        help="Collection name to backfill (default: medical_docs).",
    )
    args = parser.parse_args(argv)

    from src.evals.index_snapshot import _REQUIRED_BUILD_METADATA
    from src.ingestion.indexing.store import build_collection_build_metadata

    try:
        payload = build_collection_build_metadata()
    except ValueError:
        payload = None
    if payload is None:
        # Fail closed: the corpus digest is always computed from the
        # configured raw data directory and never overridden or invented.
        print("error: backfill failed: corpus digest unavailable", file=sys.stderr)
        return 1

    if not args.chroma_dir.is_dir():
        print(f"error: chroma directory not found: {args.chroma_dir}", file=sys.stderr)
        return 1
    import chromadb

    try:
        client = chromadb.PersistentClient(path=str(args.chroma_dir))
        collection = client.get_collection(name=args.collection, embedding_function=None)
    except Exception:
        # Fixed label only; exception internals are never printed.
        print("error: backfill failed: collection unavailable", file=sys.stderr)
        return 1

    raw_existing = dict(collection.metadata or {})
    existing = _json_normalized(raw_existing)
    normalized_payload = _json_normalized(payload)
    if all(existing.get(key) == normalized_payload.get(key) for key in _REQUIRED_BUILD_METADATA):
        print("already up to date")
        return 0

    try:
        # Merge the payload over the existing metadata: keys unrelated to
        # the build payload survive, payload values win conflicts. Chroma's
        # modify() replaces the whole mapping, so the merge must be explicit.
        collection.modify(metadata={**raw_existing, **payload})
        verified = client.get_collection(name=args.collection, embedding_function=None)
    except Exception:
        # Fixed label only; exception internals are never printed.
        print("error: backfill failed: metadata write failed", file=sys.stderr)
        return 1
    missing = sorted(_REQUIRED_BUILD_METADATA - set(dict(verified.metadata or {})))
    if missing:
        print(f"error: metadata verification failed; missing keys: {missing}", file=sys.stderr)
        return 1
    added = sorted(set(payload) - set(raw_existing))
    print(f"backfilled build metadata onto '{args.collection}'; keys added: {added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
