#!/usr/bin/env python3
"""Offline D11 frozen embedding/index identity snapshot builder (slice task T5).

Implements the 2026-10-20 D11 decision (docs/plans/migration/decisions.md):
freeze the current embedding model, its 768-dimensional representation, the
corpus snapshot and the index as the comparison-time identity. Any reindex or
embedding-provider change is a separately named variant with its own identity;
cross-encoder/reranker assets remain unselected and not downloaded.

Offline only. The script reads existing local metadata exclusively:

- embedding identity comes from ``effective_roles`` (the same allowlisted,
  credential-free role source as the baseline configuration snapshot);
- corpus identity is ``content_directory_provenance`` verbatim (digests and
  counts only);
- index identity is captured by copying ``--chroma-dir`` to a fresh private
  temp directory (the source store's sqlite write lock is held across the
  copy and quiescence is re-verified with before/after recursive file
  signatures, as the L5 contract requires) and freezing the configured
  collection through the standard ``ConsistentIndexSnapshotSource`` seam. The
  shared runtime store is never certified, and no content (documents,
  metadata, embeddings) is ever written to the output - digests, counts and
  configuration values only.

Failures are recorded honestly: any freeze/validation failure yields
``status: unverified`` with the exact reason string and null identity fields.
A verified identity is never synthesized.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "docs/plans/migration/20261021-d11-frozen-embedding-index-identity.json"
)
DEFAULT_CHROMA_DIR = PROJECT_ROOT / "data/chroma"
OUTPUT_SCHEMA_VERSION = 1
# Fixed expectation from the D11 decision; the recorded dimension value itself
# always flows from the effective_roles source, never from this constant.
_D11_EXPECTED_DIMENSIONS = 768
# Digest shape contract shared with src.evals.index_snapshot._SOURCE_DIGEST.
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_EMBEDDER_ROLE_SOURCE = "src.evals.deepeval_models.effective_roles"

_UNVERIFIED_IDENTITY_FIELDS = (
    "snapshot_sha256",
    "fingerprint",
    "build_spec_sha256",
    "document_count",
    "embedding_dimensions",
    "embedding_model",
    "collection_name",
    "retrieval_weights",
    "source_snapshot_sha256",
)


def offline_refusal_reason(chroma_server_host: str) -> str | None:
    """Mirror the L5 capture contract: refuse any remote-server configuration.

    A remote Chroma server is the only configuration under which this builder
    would require network access; local persistent copies are read offline.
    """
    if str(chroma_server_host).strip():
        return "remote_snapshot_verification_unsupported"
    return None


def _is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_HEX.fullmatch(value))


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_finite_number(value: Any) -> bool:
    """Mirror upstream ``index_snapshot._finite_number`` (bool-excluding)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def unverified_embedding_identity(reason: str) -> dict[str, Any]:
    """Return the honest unverified embedding identity (null identity fields)."""
    return {
        "status": "unverified",
        "reason": str(reason),
        "role_source": _EMBEDDER_ROLE_SOURCE,
        "provider": None,
        "model": None,
        "dimensions": None,
        "dimensions_match_d11_decision": False,
        "batch_size": None,
        "endpoint": None,
    }


def build_embedding_identity(embedder_role: Mapping[str, Any]) -> dict[str, Any]:
    """Assemble the embedding identity block from an ``effective_roles`` embedder.

    The block is ``status: verified`` only when the role carries every
    required identity field (``provider``, ``model``, ``dimensions``); an
    absent or partial role fails closed as ``embedder_role_incomplete`` with
    null identity fields. The dimension value is recorded exactly as reported
    by the roles source; ``dimensions_match_d11_decision`` asserts it against
    the D11 expectation. No credential material is copied - only non-secret
    role fields.
    """
    if not (
        _is_nonempty_str(embedder_role.get("provider"))
        and _is_nonempty_str(embedder_role.get("model"))
        and _is_positive_int(embedder_role.get("dimensions"))
    ):
        return unverified_embedding_identity("embedder_role_incomplete")
    dimensions = embedder_role["dimensions"]
    return {
        "status": "verified",
        "role_source": _EMBEDDER_ROLE_SOURCE,
        "provider": embedder_role["provider"],
        "model": embedder_role["model"],
        "dimensions": dimensions,
        "dimensions_match_d11_decision": bool(dimensions == _D11_EXPECTED_DIMENSIONS),
        "batch_size": embedder_role.get("batch_size"),
        "endpoint": embedder_role.get("endpoint"),
    }


def build_spec_for_collection(
    collection_name: str,
    collection_metadata: Mapping[str, Any],
    embedder_role: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble the minimal build spec from configuration values, never content.

    ``collection_metadata`` is the frozen Chroma collection metadata (the
    record of how the index was actually built); the embedder block comes from
    the effective roles source. ``_validate_build_spec`` enforces their
    agreement, so drifted configurations fail honestly instead of being
    papered over.
    """
    return {
        "collection_name": str(collection_name),
        "collection_metadata": dict(collection_metadata),
        "embedder": {
            "model": embedder_role.get("model"),
            "batch_size": embedder_role.get("batch_size"),
            "dimensions": embedder_role.get("dimensions"),
        },
        "retrieval_weights": {
            "semantic": collection_metadata.get("semantic_weight"),
            "keyword": collection_metadata.get("keyword_weight"),
            "boost": collection_metadata.get("boost_weight"),
        },
    }


def unverified_index_identity(reason: str) -> dict[str, Any]:
    """Return the honest unverified identity record with null identity fields."""
    identity: dict[str, Any] = {
        "status": "unverified",
        "reason": str(reason),
        "freeze_guarantee": False,
    }
    identity.update(dict.fromkeys(_UNVERIFIED_IDENTITY_FIELDS, None))
    return identity


class _PayloadSnapshotSource:
    """Minimal ``ConsistentIndexSnapshotSource`` over an assembled payload."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = payload

    def read_consistent_index_snapshot(self) -> Mapping[str, Any]:
        return self._payload


def freeze_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Freeze a ``{snapshot, build_spec}`` payload without raising.

    Mirrors ``l5_index.capture_index_snapshot`` semantics: any validation
    failure is recorded as ``status: unverified`` with the exact reason string
    instead of an exception or a synthesized identity.
    """
    from src.evals.index_snapshot import SnapshotError, freeze_index_snapshot

    try:
        frozen = freeze_index_snapshot(_PayloadSnapshotSource(payload))
    except SnapshotError as error:
        return {"status": "unverified", "reason": str(error)}
    except (OSError, TypeError, ValueError):
        return {"status": "unverified", "reason": "index_snapshot_invalid_or_unavailable"}
    return frozen.capture_payload()


def build_index_identity_from_capture(capture: Mapping[str, Any]) -> dict[str, Any]:
    """Extract ONLY identity fields from a freeze capture payload.

    ``capture["snapshot"]`` and ``capture["build_spec"]`` (documents, metadata
    and embeddings) are never copied into the returned record. ``status:
    verified`` is emitted only after every identity field validates; a forged
    or incomplete success-shaped capture fails closed as
    ``index_capture_invalid`` with null identity fields instead. The field
    rules mirror the upstream ``_validate_build_spec`` contract: the source
    provenance digest must be a 64-char lowercase hex string (null is not
    accepted) and ``retrieval_weights`` must carry finite numeric
    ``semantic``, ``keyword`` and ``boost`` values.
    """
    if capture.get("status") != "verified":
        reason = str(capture.get("reason") or "index_snapshot_unavailable")
        return unverified_index_identity(reason)
    if capture.get("freeze_guarantee") is not True:
        return unverified_index_identity("backend_snapshot_freeze_unavailable")
    snapshot = capture.get("snapshot")
    build_spec = capture.get("build_spec")
    if not isinstance(snapshot, Mapping) or not isinstance(build_spec, Mapping):
        return unverified_index_identity("index_capture_invalid")
    metadata = build_spec.get("collection_metadata")
    embedder = build_spec.get("embedder")
    weights = build_spec.get("retrieval_weights")
    if not isinstance(metadata, Mapping) or not isinstance(embedder, Mapping):
        return unverified_index_identity("index_capture_invalid")
    ids = snapshot.get("ids")
    identity: dict[str, Any] = {
        "status": "verified",
        "reason": None,
        "freeze_guarantee": True,
        "snapshot_sha256": capture.get("snapshot_sha256"),
        "fingerprint": capture.get("fingerprint"),
        "build_spec_sha256": capture.get("build_spec_sha256"),
        "document_count": len(ids) if isinstance(ids, list) else None,
        "embedding_dimensions": embedder.get("dimensions"),
        "embedding_model": embedder.get("model"),
        "collection_name": build_spec.get("collection_name"),
        "retrieval_weights": dict(weights) if isinstance(weights, Mapping) else None,
        "source_snapshot_sha256": metadata.get("source_snapshot_sha256"),
    }
    if not (
        isinstance(weights, Mapping)
        and _is_sha256_hex(identity["snapshot_sha256"])
        and _is_sha256_hex(identity["fingerprint"])
        and _is_sha256_hex(identity["build_spec_sha256"])
        and _is_positive_int(identity["document_count"])
        and _is_positive_int(identity["embedding_dimensions"])
        and _is_nonempty_str(identity["embedding_model"])
        and _is_nonempty_str(identity["collection_name"])
        and _is_finite_number(weights.get("semantic"))
        and _is_finite_number(weights.get("keyword"))
        and _is_finite_number(weights.get("boost"))
    ):
        return unverified_index_identity("index_capture_invalid")
    # Upstream _validate_build_spec requires the source provenance digest;
    # unlike the earlier mirror of that contract there is no null escape
    # hatch: a verified record always carries a 64-char lowercase hex digest.
    if not _is_sha256_hex(identity["source_snapshot_sha256"]):
        return unverified_index_identity("index_capture_invalid")
    return identity


def _source_tree_signature(directory: Path) -> dict[str, tuple[int, int]]:
    """Map every regular file under ``directory`` to its (size, mtime_ns)."""
    signature: dict[str, tuple[int, int]] = {}
    for path in sorted(directory.rglob("*"), key=lambda item: os.fsencode(str(item))):
        info = path.lstat()
        if stat.S_ISREG(info.st_mode):
            signature[str(path.relative_to(directory))] = (info.st_size, info.st_mtime_ns)
    return signature


@contextmanager
def _source_sqlite_write_lock(sqlite_path: Path) -> Iterator[sqlite3.Connection]:
    """Hold the source store's sqlite write lock across the private copy.

    Chroma's local writers coordinate through sqlite (the ``acquire_write``
    table), so ``BEGIN EXCLUSIVE`` on the source's ``chroma.sqlite3`` is the
    store's own maintenance boundary: other writers cannot commit while it is
    held. Filesystem-level writers that bypass sqlite coordination are out of
    this model; they remain covered by the before/after signature check.

    The transaction is always rolled back and the connection closed, so the
    source store is never modified. Raises ``FileNotFoundError`` when the
    sqlite file is missing and ``sqlite3.Error`` when it is corrupt or
    already locked by another writer.
    """
    if not sqlite_path.is_file():
        raise FileNotFoundError(sqlite_path)
    # Short acquisition timeout: an offline identity build fails fast when the
    # store's maintenance boundary is already held by another writer.
    connection = sqlite3.connect(sqlite_path, timeout=1.0)
    try:
        connection.execute("BEGIN EXCLUSIVE")
        try:
            yield connection
        finally:
            connection.execute("ROLLBACK")
    finally:
        connection.close()


def capture_index_identity_from_chroma_dir(
    chroma_dir: Path,
    *,
    collection_name: str,
    embedder_role: Mapping[str, Any],
) -> dict[str, Any]:
    """Freeze the configured collection from a private copy of a local store.

    The copy honors the L5 "never certify the shared Chroma store" contract
    only while the shared source stays quiescent. Quiescence is enforced at
    the store's own maintenance boundary: the source ``chroma.sqlite3`` is
    opened and an exclusive transaction (``BEGIN EXCLUSIVE``) is held across
    the copy, so Chroma's local writers - which coordinate through sqlite -
    cannot commit until the copy completes. A missing, corrupt, or already
    locked source database fails closed with ``chroma_source_lock_unavailable``
    instead of a verified identity. Writers that bypass sqlite coordination
    entirely (raw filesystem writes) are out of the lock's model, so a
    recursive file signature (sizes + mtimes) is additionally captured before
    the copy and re-checked after the backend is closed; any difference fails
    closed with ``chroma_source_unstable``. The original directory stays
    untouched (the lock transaction is rolled back; nothing is written to
    the source). Only identity fields survive; contents are dropped with the
    temp copy.
    """
    source_dir = Path(chroma_dir)
    if not source_dir.is_dir():
        return unverified_index_identity("chroma_directory_missing")
    try:
        with tempfile.TemporaryDirectory(prefix="d11-identity-") as temp_root:
            signature_before_copy = _source_tree_signature(source_dir)
            private_copy = Path(temp_root) / "chroma"
            try:
                with _source_sqlite_write_lock(source_dir / "chroma.sqlite3"):
                    shutil.copytree(source_dir, private_copy, symlinks=False)
            except sqlite3.Error:
                # Corrupt or already-locked source database: the store's own
                # maintenance boundary is unavailable, so quiescence cannot
                # be established. Fixed reason only; never crash.
                return unverified_index_identity("chroma_source_lock_unavailable")
            except FileNotFoundError:
                # No chroma.sqlite3 anchoring the writer-coordination boundary.
                return unverified_index_identity("chroma_source_lock_unavailable")
            except OSError:
                return unverified_index_identity("chroma_directory_unreadable")
            import chromadb

            client = chromadb.PersistentClient(path=str(private_copy))
            try:
                collection = client.get_collection(name=collection_name, embedding_function=None)
            except Exception:
                # Fixed reason only; no exception bodies are recorded.
                return unverified_index_identity("chroma_collection_missing_or_unreadable")
            try:
                readback = collection.get(include=["documents", "metadatas", "embeddings"])
                metadata = dict(collection.metadata or {})
            except Exception:
                # Corrupt or unreadable copied store: record honestly, never crash.
                return unverified_index_identity("chroma_collection_unreadable")
            # Chroma returns numpy arrays for embeddings; an empty array's
            # truth value is ambiguous, so test for None explicitly.
            raw_embeddings = readback.get("embeddings")
            snapshot = {
                "ids": list(readback.get("ids") or []),
                "contents": list(readback.get("documents") or []),
                "metadatas": list(readback.get("metadatas") or []),
                "embeddings": list(raw_embeddings) if raw_embeddings is not None else [],
                "index_metadata": metadata,
            }
            build_spec = build_spec_for_collection(collection_name, metadata, embedder_role)
            capture = freeze_from_payload({"snapshot": snapshot, "build_spec": build_spec})
            del client, collection  # release backend handles before the temp copy is removed
        # Quiescence is a detected precondition, not an assumption: a writer
        # that touched the shared store while it was copied invalidates the
        # snapshot, so the identity fails closed.
        if _source_tree_signature(source_dir) != signature_before_copy:
            return unverified_index_identity("chroma_source_unstable")
    except OSError:
        return unverified_index_identity("chroma_directory_unreadable")
    except Exception:
        # Any other backend failure (unopenable copied store, unexpected read
        # error) is recorded honestly and fail-closed; never crash, never
        # synthesize a verified identity, never record exception bodies.
        return unverified_index_identity("chroma_collection_unreadable")
    return build_index_identity_from_capture(capture)


def build_output_document(
    *,
    embedding_identity: Mapping[str, Any],
    corpus_identity: Mapping[str, Any],
    index_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Frame the three identity blocks with the D11 decision record."""
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "d11_decision": {
            "decision": "freeze_current_embedding_model_representation_corpus_and_index",
            "freeze_semantics": (
                "comparison-time identity; any reindex or embedding-provider change "
                "is a separately named variant with its own identity"
            ),
            "frozen_representation_dimensions": _D11_EXPECTED_DIMENSIONS,
            "cross_encoder_reranker": "not_selected_not_downloaded",
            "live_claims": False,
            "clinical_quality_verified": False,
            "decision_reference": "docs/plans/migration/decisions.md (D11, 2026-10-20)",
        },
        "embedding_identity": dict(embedding_identity),
        "corpus_identity": dict(corpus_identity),
        "index_identity": dict(index_identity),
        "generation": {
            "script": "scripts/manual/build_d11_frozen_identity.py",
            "offline_only": True,
        },
    }


def serialize_output(payload: Mapping[str, Any]) -> str:
    """Serialize deterministically: sorted keys, ASCII-safe, indent 2, no timestamps."""
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    parser = argparse.ArgumentParser(
        description="Build the offline D11 frozen embedding/index identity snapshot."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output JSON path (default: docs/plans/migration/20261021-...-identity.json).",
    )
    parser.add_argument(
        "--chroma-dir",
        type=Path,
        default=DEFAULT_CHROMA_DIR,
        help="Local Chroma persistence directory to freeze a private copy of.",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=None,
        help="Corpus directory (default: the configured raw data directory).",
    )
    args = parser.parse_args(argv)

    from src.config import settings
    from src.config.paths import DATA_RAW_DIR
    from src.evals.assessment.reporting import content_directory_provenance
    from src.evals.deepeval_models import effective_roles

    refusal = offline_refusal_reason(settings.storage.chroma_server_host)
    if refusal is not None:
        print(
            "Refusing to run: a remote Chroma server is configured "
            f"(reason: {refusal}); the D11 identity builder is offline-only "
            "and freezes a local directory copy.",
            file=sys.stderr,
        )
        return 2

    try:
        roles = effective_roles(task="index_build")
    except ValueError as error:
        print(f"Refusing to run: effective embedder role unavailable: {error}", file=sys.stderr)
        return 3

    embedder_role = roles.get("embedder")
    if isinstance(embedder_role, Mapping):
        embedding_identity = build_embedding_identity(embedder_role)
    else:
        embedder_role = {}
        embedding_identity = unverified_embedding_identity("embedder_role_unavailable")
    corpus_dir = args.corpus_dir if args.corpus_dir is not None else DATA_RAW_DIR
    corpus_identity = content_directory_provenance(Path(corpus_dir))
    index_identity = capture_index_identity_from_chroma_dir(
        args.chroma_dir,
        collection_name=settings.storage.collection_name,
        embedder_role=embedder_role,
    )
    document = build_output_document(
        embedding_identity=embedding_identity,
        corpus_identity=corpus_identity,
        index_identity=index_identity,
    )
    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(serialize_output(document), encoding="utf-8")
    print(
        f"Wrote D11 identity snapshot to {output_path} "
        f"(index identity status: {index_identity.get('status')})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
