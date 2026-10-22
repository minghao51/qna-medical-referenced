"""Offline authoring tool for schema-v1 review manifests with attestations.

Builds the exact artifact shape that ``retrieval_eval`` verification and the
orchestrator's ``_read_review_manifest``/``_validate_review_manifest_schema``
accept. Every hash and binding decision is delegated to the verification
helpers themselves; nothing here reimplements manifest semantics.

Authority and scope (D07-ext, docs/plans/migration/decisions.md):

- This tool makes no identity claims. Attestations authenticate
  supplied-content consistency only — never reviewer identity, medical
  qualification, or clinical endorsement.
- The review authority's name, scope, and date are recorded in
  ``docs/plans/migration/decisions.md`` by the owner when the tool is first
  exercised; authoring itself records no authority anywhere.
- No eligibility flag is flipped by authoring: the emitted manifest carries
  only the ``manifest_hash_verified_not_identity_authenticated`` authority
  status, and evaluation-side evidence eligibility stays False.

Offline only: local bounded file inputs, one local atomic output, no network,
no timestamps, no environment capture. Every refusal exits non-zero with one
fixed one-line reason and leaves no output artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .orchestrator import _read_review_manifest, _validate_review_manifest_schema
from .retrieval_eval import (
    _canonical_sha256,
    _is_sha256,
    _is_unanswerable,
    _review_context_parts,
    _review_manifest_authority_status_from_parts,
    _reviewed_evidence_qrels,
    _verify_review_attestations,
)

# Inputs are bounded like the orchestrator's review reads, at a tighter
# tool-specific limit (16 MiB) because review datasets and corpus exports are
# small by construction.
_MAX_INPUT_BYTES = 16 * 1024 * 1024

# The only authority status an authored manifest may carry: content hashes are
# verified, reviewer identity is not authenticated (D07-ext scope).
AUTHORITY_STATUS_HASH_VERIFIED = "manifest_hash_verified_not_identity_authenticated"

_SELF_CHECK_FAILURE_REASON = "review manifest tool self-check failed"
_POST_WRITE_FAILURE_REASON = "review manifest failed verification after write"
_OUTPUT_ALIAS_FAILURE_REASON = "manifest output must not overwrite a dataset or corpus input"


class ReviewManifestRefusalError(Exception):
    """Raised for every refusal; ``reason`` is a fixed one-line string."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _DuplicateKeyError(ValueError):
    """Marks duplicate JSON object keys distinctly from other decode errors."""


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError("JSON contains duplicate object keys")
        result[key] = value
    return result


def _path_has_symlink_component(path: Path) -> bool:
    """Mirror the orchestrator's per-component symlink discipline for inputs."""
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                return True
        except FileNotFoundError:
            return False
    return False


def _read_bounded_json(path: Path, label: str) -> Any:
    """Read one bounded JSON input with the orchestrator's read discipline."""
    target = path.absolute()
    if _path_has_symlink_component(target) or not target.is_file():
        raise ReviewManifestRefusalError(f"{label} input must be a regular non-symlink file")
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(target, flags)
        with os.fdopen(descriptor, "rb") as source:
            descriptor = None
            before = os.fstat(source.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_size <= 0
                or before.st_size > _MAX_INPUT_BYTES
            ):
                raise ReviewManifestRefusalError(f"{label} input has an unsupported size")
            raw = source.read(_MAX_INPUT_BYTES + 1)
            after = os.fstat(source.fileno())
    except OSError:
        raise ReviewManifestRefusalError(f"{label} input is unavailable") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or len(raw) != after.st_size:
        raise ReviewManifestRefusalError(f"{label} input changed while being read")
    try:
        return json.loads(raw, object_pairs_hook=_reject_duplicate_json_keys)
    except _DuplicateKeyError:
        raise ReviewManifestRefusalError(
            f"{label} input JSON contains duplicate object keys"
        ) from None
    except ValueError:
        raise ReviewManifestRefusalError(f"{label} input JSON is invalid") from None


def _read_dataset(path: Path) -> list[dict[str, Any]]:
    payload = _read_bounded_json(path, "dataset")
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ReviewManifestRefusalError("dataset input must be a JSON array of case objects")
    return payload


def _read_corpus(path: Path) -> dict[str, Any]:
    payload = _read_bounded_json(path, "corpus")
    if not isinstance(payload, dict):
        raise ReviewManifestRefusalError(
            "corpus input must be a JSON object with exactly sources and documents"
        )
    return payload


def _content_sha256(content: str) -> str:
    """Raw content digest exactly as ``_review_context_base_parts`` verifies it."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _freeze_corpus(corpus: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the corpus input and derive its frozen_sources/frozen_documents."""
    if not isinstance(corpus, dict) or set(corpus) != {"sources", "documents"}:
        raise ReviewManifestRefusalError(
            "corpus input must be a JSON object with exactly sources and documents"
        )
    sources_input = corpus["sources"]
    documents_input = corpus["documents"]
    if not isinstance(sources_input, dict) or not isinstance(documents_input, dict):
        raise ReviewManifestRefusalError(
            "corpus input must be a JSON object with exactly sources and documents"
        )

    frozen_sources: dict[str, Any] = {}
    for source_id, source in sources_input.items():
        if not isinstance(source_id, str) or not source_id.strip():
            raise ReviewManifestRefusalError("corpus input source ids must be non-empty strings")
        if (
            not isinstance(source, dict)
            or set(source) != {"content"}
            or not isinstance(source["content"], str)
        ):
            raise ReviewManifestRefusalError(
                "corpus input sources must map ids to objects with string content"
            )
        content = source["content"]
        frozen_sources[source_id] = {
            "content": content,
            "source_sha256": _content_sha256(content),
        }

    frozen_documents: dict[str, Any] = {}
    for document_id, document in documents_input.items():
        if not isinstance(document_id, str) or not document_id.strip():
            raise ReviewManifestRefusalError("corpus input document ids must be non-empty strings")
        if not isinstance(document, dict) or set(document) - {
            "source_id",
            "content",
            "source_sha256",
        }:
            raise ReviewManifestRefusalError(
                "corpus input documents must map ids to source_id/content objects"
            )
        document_source_id = document.get("source_id")
        document_content = document.get("content")
        if not isinstance(document_source_id, str) or not document_source_id.strip():
            raise ReviewManifestRefusalError(
                "corpus input documents require a non-empty string source_id"
            )
        if document_source_id not in frozen_sources:
            raise ReviewManifestRefusalError(
                "corpus input document source_id must reference a declared source"
            )
        if not isinstance(document_content, str):
            raise ReviewManifestRefusalError("corpus input document content must be a string")
        source_sha256 = frozen_sources[document_source_id]["source_sha256"]
        if "source_sha256" in document:
            # An explicit JSON null is a supplied claim, not an absent key: a
            # supplied claim must be valid 64-hex matching the computed hash.
            claimed_source_sha256 = document["source_sha256"]
            if not _is_sha256(claimed_source_sha256) or claimed_source_sha256 != source_sha256:
                raise ReviewManifestRefusalError(
                    "corpus input document source_sha256 does not match its source"
                )
        frozen_documents[document_id] = {
            "source_id": document_source_id,
            "source_sha256": source_sha256,
            "content_sha256": _content_sha256(document_content),
        }
    return frozen_sources, frozen_documents


def _case_qrels_sha256(
    item: dict[str, Any],
    case_id: str,
    reviewer_id: str,
    frozen_sources: dict[str, Any],
) -> str:
    """Bind one case's evidence passages through the real verification helper.

    The candidate ``qrels_sha256`` is the canonical hash of exactly the
    structure ``_reviewed_evidence_qrels`` builds; the helper re-derives that
    structure from the item plus the frozen sources and only returns qrels
    when the candidate matches and every passage binds to frozen source
    content. An empty helper result for an answerable case that declares
    passages therefore means a passage failed to bind, and the build refuses —
    empty qrels are never silently certified for such a case. A present but
    non-list ``evidence_passages`` value is a malformed declaration and refuses
    instead of taking the empty-qrels path.
    """
    passages = item.get("evidence_passages")
    if "evidence_passages" in item and not isinstance(passages, list):
        raise ReviewManifestRefusalError(
            f"evidence passage judgment is invalid for case {case_id!r}"
        )
    if _is_unanswerable(item) or not passages:
        empty = _canonical_sha256({"case_id": case_id.strip(), "passages": []})
        if empty is None:
            raise ReviewManifestRefusalError("canonical hashing failed")
        return empty

    # Input collection only: mirror the helper's extraction expressions so the
    # candidate equals the canonical structure it validates against.
    collected: dict[str, dict[str, Any]] = {}
    for passage in passages:
        if not isinstance(passage, dict):
            raise ReviewManifestRefusalError(
                f"evidence passage judgment is invalid for case {case_id!r}"
            )
        passage_id = str(passage.get("passage_id") or passage.get("evidence_id") or "").strip()
        grade = passage.get("relevance_grade", passage.get("grade", passage.get("relevance")))
        collected[passage_id] = {
            "grade": grade,
            "quote": passage.get("quote"),
            "source_id": passage.get("source_id"),
            "source_sha256": passage.get("source_sha256"),
        }
    candidate = _canonical_sha256(
        {
            "case_id": case_id.strip(),
            "passages": [
                {"passage_id": passage_id, **collected[passage_id]}
                for passage_id in sorted(collected)
            ],
        }
    )
    if candidate is None:
        raise ReviewManifestRefusalError("canonical hashing failed")
    review_case = {
        "review_status": "human_reviewed",
        "reviewer_id": reviewer_id,
        "qrels_sha256": candidate,
    }
    try:
        qrels = _reviewed_evidence_qrels(item, review_case, frozen_sources)
    except (TypeError, ValueError):
        raise ReviewManifestRefusalError(
            f"evidence passage judgment is invalid for case {case_id!r}"
        ) from None
    if not qrels:
        raise ReviewManifestRefusalError(f"evidence passage failed to bind for case {case_id!r}")
    return candidate


def build_review_manifest(
    dataset: list[dict[str, Any]],
    corpus: dict[str, Any],
    reviewer_id: str,
    manifest_id: str,
    index_snapshot_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Build the attested manifest; raises ``ReviewManifestRefusalError`` on refusal."""
    if not isinstance(dataset, list) or not all(isinstance(item, dict) for item in dataset):
        raise ReviewManifestRefusalError("dataset input must be a JSON array of case objects")
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise ReviewManifestRefusalError("reviewer_id must be a non-empty string")
    if not isinstance(manifest_id, str) or not manifest_id.strip():
        raise ReviewManifestRefusalError("manifest_id must be a non-empty string")
    if index_snapshot_fingerprint is not None and not _is_sha256(index_snapshot_fingerprint):
        raise ReviewManifestRefusalError(
            "index_snapshot_fingerprint must be a 64-character lowercase hex string"
        )

    frozen_sources, frozen_documents = _freeze_corpus(corpus)

    dataset_sha256 = _canonical_sha256(dataset)
    if dataset_sha256 is None:
        raise ReviewManifestRefusalError("canonical hashing failed")

    cases: dict[str, dict[str, Any]] = {}
    attested_cases: list[tuple[str, dict[str, Any]]] = []
    seen_case_ids: set[str] = set()
    for item in dataset:
        raw_case_id = item.get("query_id") or item.get("case_id")
        if not isinstance(raw_case_id, str) or not raw_case_id.strip():
            raise ReviewManifestRefusalError("dataset cases require a stable query_id or case_id")
        if raw_case_id in seen_case_ids:
            raise ReviewManifestRefusalError("dataset contains duplicate case ids")
        seen_case_ids.add(raw_case_id)
        cases[raw_case_id] = {
            "review_status": "human_reviewed",
            "reviewer_id": reviewer_id,
            "qrels_sha256": _case_qrels_sha256(item, raw_case_id, reviewer_id, frozen_sources),
        }
        attested_cases.append((raw_case_id, item))

    corpus_sha256 = _canonical_sha256(
        {"frozen_sources": frozen_sources, "frozen_documents": frozen_documents}
    )
    if corpus_sha256 is None:
        raise ReviewManifestRefusalError("canonical hashing failed")

    records: dict[str, Any] = {}
    for raw_case_id, item in attested_cases:
        record = _canonical_sha256({"dataset_case": item, "review_case": cases[raw_case_id]})
        if record is None:
            raise ReviewManifestRefusalError("canonical hashing failed")
        records[raw_case_id] = record
    content_sha256 = _canonical_sha256({"schema_version": 1, "records": records})
    if content_sha256 is None:
        raise ReviewManifestRefusalError("canonical hashing failed")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "manifest_id": manifest_id,
        "dataset_sha256": dataset_sha256,
        "corpus_sha256": corpus_sha256,
        "frozen_sources": frozen_sources,
        "frozen_documents": frozen_documents,
        "cases": cases,
        "attestations": {
            "schema_version": 1,
            "records": records,
            "content_sha256": content_sha256,
        },
    }
    if index_snapshot_fingerprint is not None:
        manifest["index_snapshot_fingerprint"] = index_snapshot_fingerprint
    return manifest


def verify_authored_manifest(manifest: dict[str, Any], dataset: list[dict[str, Any]]) -> str:
    """Run the full verification stack; return the authority status or refuse.

    Any failure here is a tool bug signal, so every failure carries one fixed
    reason regardless of which verification layer rejected the manifest.
    """
    try:
        _validate_review_manifest_schema(manifest)
        parts = _review_context_parts(manifest, dataset)
        attestations_verified = parts is not None and _verify_review_attestations(
            manifest, dataset, parts[0]
        )
        status = _review_manifest_authority_status_from_parts(manifest, parts)
    except (TypeError, ValueError):
        raise ReviewManifestRefusalError(_SELF_CHECK_FAILURE_REASON) from None
    if parts is None or not attestations_verified or status != AUTHORITY_STATUS_HASH_VERIFIED:
        raise ReviewManifestRefusalError(_SELF_CHECK_FAILURE_REASON)
    return status


def _delete_quietly(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        return


def _output_aliases_input(output: Path, inputs: Sequence[Path]) -> bool:
    """True when writing ``output`` would replace one of the input files."""
    for input_path in inputs:
        try:
            output_resolved = os.path.normcase(str(output.resolve()))
            input_resolved = os.path.normcase(str(input_path.resolve()))
            if output_resolved == input_resolved:
                return True
            output_stat = output.stat()
            input_stat = input_path.stat()
        except OSError:
            continue
        if (output_stat.st_dev, output_stat.st_ino) == (input_stat.st_dev, input_stat.st_ino):
            return True
    return False


def _write_manifest_atomic(output: Path, manifest: dict[str, Any]) -> bytes:
    payload = (
        json.dumps(manifest, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    ).encode("utf-8")
    try:
        descriptor, temp_name = tempfile.mkstemp(
            dir=output.parent, prefix=".review-manifest-", suffix=".tmp"
        )
    except OSError:
        raise ReviewManifestRefusalError("manifest output could not be written") from None
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, output)
    except OSError:
        Path(temp_name).unlink(missing_ok=True)
        raise ReviewManifestRefusalError("manifest output could not be written") from None
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Author an attested schema-v1 review manifest from a reviewed dataset and a "
            "frozen corpus (offline; content-consistency attestations only, no identity claims)."
        )
    )
    parser.add_argument(
        "--dataset", required=True, help="Reviewed dataset JSON (case object array)."
    )
    parser.add_argument(
        "--corpus",
        required=True,
        help="Corpus JSON object with exactly a sources and a documents object.",
    )
    parser.add_argument(
        "--reviewer-id", required=True, help="Reviewer identifier recorded per case."
    )
    parser.add_argument(
        "--manifest-id", required=True, help="Identifier for the authored manifest."
    )
    parser.add_argument(
        "--index-snapshot-fingerprint",
        default=None,
        help="Optional 64-hex index snapshot fingerprint embedded verbatim.",
    )
    parser.add_argument("--output", required=True, help="Manifest output path.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Author one manifest; return 0 on success or 1 with a fixed refusal line."""
    args = _build_parser().parse_args(argv)
    try:
        dataset = _read_dataset(Path(args.dataset))
        corpus = _read_corpus(Path(args.corpus))
        manifest = build_review_manifest(
            dataset,
            corpus,
            args.reviewer_id,
            args.manifest_id,
            args.index_snapshot_fingerprint,
        )
        status = verify_authored_manifest(manifest, dataset)
        output = Path(args.output).absolute()
        if _output_aliases_input(output, (Path(args.dataset), Path(args.corpus))):
            raise ReviewManifestRefusalError(_OUTPUT_ALIAS_FAILURE_REASON)
        payload = _write_manifest_atomic(output, manifest)
        try:
            written_manifest, written_sha256 = _read_review_manifest(output)
            verify_authored_manifest(written_manifest, dataset)
            if (
                written_manifest != manifest
                or written_sha256 != hashlib.sha256(payload).hexdigest()
            ):
                raise ValueError("review manifest read-back differs from the authored manifest")
        except (ValueError, ReviewManifestRefusalError):
            _delete_quietly(output)
            print(f"refusal: {_POST_WRITE_FAILURE_REASON}", file=sys.stderr)
            return 1
        print(f"{output} {status}")
        return 0
    except ReviewManifestRefusalError as refusal:
        print(f"refusal: {refusal.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
