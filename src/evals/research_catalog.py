"""Bounded, read-only projections for the private research catalog.

The catalog exposes a fixed set of known files. Nothing here accepts a path from
a request, discovers files dynamically, opens the vector store or creates the
data directories: missing roots/files stay missing and are reported honestly.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from src.config.paths import (
    CHROMA_PERSIST_DIRECTORY,
    DATA_DIR,
    DATA_RAW_DIR,
    PROJECT_ROOT,
)

logger = logging.getLogger(__name__)

FIXTURE_ROOT: Path = PROJECT_ROOT / "tests" / "fixtures"
REVIEW_ROOT: Path = DATA_DIR / "evals" / "review"
REFERENCE_ROOT: Path = Path(DATA_RAW_DIR) / "LabQAR"

MAX_SOURCE_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 10_000
MAX_FIELD_CHARS = 16_000

CatalogKind = Literal[
    "query_fixture",
    "conversation_fixture",
    "review_dataset",
    "reference_csv",
    "retrieval_index",
]
RecordUnit = Literal["question", "conversation", "case", "row", "chunk"]
Availability = Literal["available", "missing", "malformed", "unsupported", "inventory_reference"]
AvailabilityReason = Literal[
    "file_missing",
    "root_missing",
    "invalid_json",
    "schema_mismatch",
    "size_cap_exceeded",
    "record_cap_exceeded",
]
CaseProjection = Literal["available", "summary_only", "unavailable"]
ReviewAuthority = Literal["not_assessed", "manifest_declared_not_authenticated"]


class CatalogError(Exception):
    """Base error for safe catalog projections."""


class CatalogNotFoundError(CatalogError):
    """The logical catalog ID is not in the fixed allowlist."""


class CatalogUnavailableError(CatalogError):
    """The requested entry exists in the allowlist but its source is unavailable."""

    def __init__(self, reason: str, availability: str = "missing") -> None:
        super().__init__(reason)
        self.reason = reason
        self.availability = availability


class CatalogCasesUnavailableError(CatalogError):
    """The entry cannot expose case rows (summary-only or unavailable)."""


class CatalogRevisionChangedError(CatalogError):
    """Requested revision does not match the current source bytes."""

    def __init__(self, current_revision_sha256: str) -> None:
        super().__init__("catalog_revision_changed")
        self.current_revision_sha256 = current_revision_sha256


class CatalogSourceError(Exception):
    """Internal availability failure while reading one fixed source."""

    def __init__(self, reason: AvailabilityReason, availability: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.availability = availability


@dataclass(frozen=True)
class _Source:
    catalog_id: str
    label: str
    kind: CatalogKind
    record_unit: RecordUnit
    filename: str | None
    root: Literal["fixtures", "review", "reference"]

    @property
    def path(self) -> Path:
        if self.filename is None:
            raise CatalogSourceError("file_missing", "missing")
        return _root_for(self.root) / self.filename


_SOURCES: tuple[_Source, ...] = (
    _Source(
        "golden-original",
        "Golden queries — original",
        "query_fixture",
        "question",
        "golden_queries.json",
        "fixtures",
    ),
    _Source(
        "golden-comprehensive",
        "Golden queries — comprehensive",
        "query_fixture",
        "question",
        "golden_queries_comprehensive.json",
        "fixtures",
    ),
    _Source(
        "golden-diverse",
        "Golden queries — diverse",
        "query_fixture",
        "question",
        "golden_queries_diverse.json",
        "fixtures",
    ),
    _Source(
        "golden-expanded",
        "Golden queries — expanded",
        "query_fixture",
        "question",
        "golden_queries_expanded.json",
        "fixtures",
    ),
    _Source(
        "golden-all",
        "Golden queries — all",
        "query_fixture",
        "question",
        "golden_queries_all.json",
        "fixtures",
    ),
    _Source(
        "golden-conversations",
        "Golden conversations",
        "conversation_fixture",
        "conversation",
        "golden_conversations.json",
        "fixtures",
    ),
    _Source(
        "d11-review",
        "D11 frozen review set",
        "review_dataset",
        "case",
        "dataset.json",
        "review",
    ),
    _Source(
        "lab-reference",
        "LabQAR reference ranges",
        "reference_csv",
        "row",
        "reference_ranges.csv",
        "reference",
    ),
    _Source(
        "d11-index",
        "D11 retrieval index",
        "retrieval_index",
        "chunk",
        None,
        "fixtures",
    ),
)

_SOURCE_BY_ID = {source.catalog_id: source for source in _SOURCES}
_CASE_KINDS = {"query_fixture", "conversation_fixture"}


def _root_for(name: str) -> Path:
    if name == "fixtures":
        return FIXTURE_ROOT
    if name == "review":
        return REVIEW_ROOT
    return REFERENCE_ROOT


def _origin_ref(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except (OSError, RuntimeError, ValueError):
        return path.name


def _bounded_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if len(value) > MAX_FIELD_CHARS:
        return None
    return value


def _bounded_str_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = [_bounded_str(item) for item in value]
    bounded = [item for item in items if item is not None]
    return bounded if bounded or not value else []


def _count_field(records: list[dict[str, Any]], field: str) -> dict[str, int] | None:
    counts: dict[str, int] = {}
    for record in records:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            key = value.strip()
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items())) or None


def _read_snapshot(path: Path, root: Path) -> bytes:
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
    except (OSError, RuntimeError) as exc:
        raise CatalogSourceError("file_missing", "missing") from exc
    if not resolved.is_relative_to(root_resolved) or not resolved.is_file():
        raise CatalogSourceError("file_missing", "missing")
    try:
        with resolved.open("rb") as handle:
            data = handle.read(MAX_SOURCE_BYTES + 1)
    except OSError as exc:
        raise CatalogSourceError("file_missing", "missing") from exc
    if len(data) > MAX_SOURCE_BYTES:
        raise CatalogSourceError("size_cap_exceeded", "unsupported")
    return data


def _parse_json(data: bytes) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogSourceError("invalid_json", "malformed") from exc


def _json_snapshot(source: _Source) -> tuple[bytes, str, Any]:
    data = _read_snapshot(source.path, _root_for(source.root))
    return data, hashlib.sha256(data).hexdigest(), _parse_json(data)


def _query_records(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        raise CatalogSourceError("schema_mismatch", "malformed")
    records = data.get("golden_queries")
    if not isinstance(records, list) or not records:
        raise CatalogSourceError("schema_mismatch", "malformed")
    if len(records) > MAX_RECORDS:
        raise CatalogSourceError("record_cap_exceeded", "unsupported")
    if not all(
        isinstance(record, dict) and isinstance(record.get("query"), str) for record in records
    ):
        raise CatalogSourceError("schema_mismatch", "malformed")
    return records


def _conversation_records(data: Any) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(data, dict):
        raise CatalogSourceError("schema_mismatch", "malformed")
    records = data.get("golden_conversations")
    if not isinstance(records, list) or not records:
        raise CatalogSourceError("schema_mismatch", "malformed")
    if len(records) > MAX_RECORDS:
        raise CatalogSourceError("record_cap_exceeded", "unsupported")
    if not all(isinstance(record, dict) for record in records):
        raise CatalogSourceError("schema_mismatch", "malformed")
    turn_count = 0
    for record in records:
        turns = record.get("turns")
        if not isinstance(turns, list):
            raise CatalogSourceError("schema_mismatch", "malformed")
        turn_count += len(turns)
    return records, turn_count


def _review_manifest_counts(review_root: Path) -> tuple[dict[str, int] | None, int | None]:
    """Return declared review status counts only; never reviewer IDs or bodies."""
    manifest_path = review_root / "manifest.json"
    try:
        data = _read_snapshot(manifest_path, review_root)
    except CatalogSourceError:
        return None, None
    try:
        manifest = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    if not isinstance(manifest, dict):
        return None, None
    cases = manifest.get("cases")
    if not isinstance(cases, dict):
        return None, None
    counts: dict[str, int] = {}
    missing = 0
    for case in cases.values():
        status = case.get("review_status") if isinstance(case, dict) else None
        if isinstance(status, str) and status.strip():
            key = status.strip()
            counts[key] = counts.get(key, 0) + 1
        else:
            missing += 1
    return dict(sorted(counts.items())) or None, missing


def _empty_entry(
    source: _Source, reason: AvailabilityReason | None, availability: str
) -> dict[str, Any]:
    return {
        "catalog_id": source.catalog_id,
        "label": source.label,
        "kind": source.kind,
        "availability": availability,
        "availability_reason": reason,
        "origin_ref": _origin_ref(source.path)
        if source.filename
        else _origin_ref(CHROMA_PERSIST_DIRECTORY),
        "revision_sha256": None,
        "record_unit": source.record_unit,
        "record_count": None,
        "turn_count": None,
        "split_counts": None,
        "label_confidence_counts": None,
        "raw_review_status_counts": None,
        "review_status_missing_count": None,
        "review_authority": "not_assessed",
        "case_projection": "unavailable",
        "inventory_ref": None,
    }


def _build_entry(source: _Source) -> dict[str, Any]:
    if source.kind == "retrieval_index":
        entry = _empty_entry(source, None, "inventory_reference")
        entry["inventory_ref"] = "/documents"
        return entry

    if source.kind == "reference_csv":
        # Row count only; this is not the served reference-chunk total.
        try:
            data = _read_snapshot(source.path, _root_for(source.root))
            text = data.decode("utf-8-sig")
            rows = list(csv.reader(io.StringIO(text)))
        except CatalogSourceError as exc:
            return _empty_entry(source, exc.reason, exc.availability)
        except (UnicodeDecodeError, csv.Error):
            return _empty_entry(source, "schema_mismatch", "malformed")
        data_rows = sum(1 for row in rows[1:] if any(cell.strip() for cell in row))
        if data_rows > MAX_RECORDS:
            return _empty_entry(source, "record_cap_exceeded", "unsupported")
        entry = _empty_entry(source, None, "available")
        entry["revision_sha256"] = hashlib.sha256(data).hexdigest()
        entry["origin_ref"] = _origin_ref(source.path)
        entry["record_count"] = data_rows
        return entry

    try:
        _, revision, parsed = _json_snapshot(source)
    except CatalogSourceError as exc:
        return _empty_entry(source, exc.reason, exc.availability)

    entry = _empty_entry(source, None, "available")
    entry["revision_sha256"] = revision
    entry["origin_ref"] = _origin_ref(source.path)

    if source.kind == "query_fixture":
        try:
            records = _query_records(parsed)
        except CatalogSourceError as exc:
            return _empty_entry(source, exc.reason, exc.availability)
        entry["record_count"] = len(records)
        entry["split_counts"] = _count_field(records, "dataset_split")
        entry["label_confidence_counts"] = _count_field(records, "label_confidence")
        entry["raw_review_status_counts"] = _count_field(records, "review_status")
        entry["review_status_missing_count"] = sum(
            1
            for record in records
            if not isinstance(record.get("review_status"), str)
            or not record["review_status"].strip()
        )
        entry["case_projection"] = "available"
        return entry

    if source.kind == "conversation_fixture":
        try:
            records, turn_count = _conversation_records(parsed)
        except CatalogSourceError as exc:
            return _empty_entry(source, exc.reason, exc.availability)
        entry["record_count"] = len(records)
        entry["turn_count"] = turn_count
        entry["case_projection"] = "available"
        return entry

    if source.kind == "review_dataset":
        if (
            not isinstance(parsed, list)
            or not parsed
            or not all(isinstance(item, dict) for item in parsed)
        ):
            return _empty_entry(source, "schema_mismatch", "malformed")
        if len(parsed) > MAX_RECORDS:
            return _empty_entry(source, "record_cap_exceeded", "unsupported")
        entry["record_count"] = len(parsed)
        entry["split_counts"] = _count_field(parsed, "answerability")
        declared, missing = _review_manifest_counts(_root_for("review"))
        entry["raw_review_status_counts"] = declared
        entry["review_status_missing_count"] = missing
        entry["review_authority"] = (
            "manifest_declared_not_authenticated" if declared is not None else "not_assessed"
        )
        entry["case_projection"] = "summary_only"
        return entry

    return _empty_entry(source, "schema_mismatch", "unsupported")


def list_catalog() -> dict[str, Any]:
    """Summaries of every fixed catalog entry plus exact current-file overlap."""
    return {
        "datasets": [_build_entry(source) for source in _SOURCES],
        "overlap": _overlap_observations(),
    }


def _query_texts(catalog_id: str) -> tuple[str, set[str]] | None:
    source = _SOURCE_BY_ID[catalog_id]
    try:
        _, revision, parsed = _json_snapshot(source)
        records = _query_records(parsed)
    except CatalogSourceError:
        return None
    return revision, {str(record["query"]) for record in records}


def _overlap_observations() -> list[dict[str, Any]]:
    left = _query_texts("golden-all")
    right = _query_texts("golden-expanded")
    if left is None or right is None:
        return []
    left_revision, left_queries = left
    right_revision, right_queries = right
    return [
        {
            "left_catalog_id": "golden-all",
            "left_revision": left_revision,
            "right_catalog_id": "golden-expanded",
            "right_revision": right_revision,
            "method": "exact_stored_query_text",
            "left_unique_query_count": len(left_queries),
            "right_unique_query_count": len(right_queries),
            "intersection_unique_query_count": len(left_queries & right_queries),
            "normalization": "none",
            "near_duplicate_status": "not_assessed",
        }
    ]


def get_catalog_entry(catalog_id: str) -> dict[str, Any]:
    source = _SOURCE_BY_ID.get(catalog_id)
    if source is None:
        raise CatalogNotFoundError(catalog_id)
    return _build_entry(source)


def _case_item(
    record: dict[str, Any], *, revision: str, ordinal: int, kind: CatalogKind
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "locator": {"revision_sha256": revision, "source_ordinal": ordinal},
        "source_case_id": None,
        "question": None,
        "expected_keywords": None,
        "expected_source_labels": None,
        "split": None,
        "difficulty": None,
        "query_category": None,
        "source_family": None,
        "topic": None,
        "label_confidence": None,
        "raw_review_status": None,
        "normalized_review_status": None,
        "stored_turns": None,
    }
    if kind == "conversation_fixture":
        item["source_case_id"] = _bounded_str(record.get("conversation_id"))
        item["query_category"] = _bounded_str(record.get("conversation_category"))
        turns = record.get("turns")
        stored_turns = []
        if isinstance(turns, list):
            for turn in turns:
                if not isinstance(turn, dict):
                    continue
                stored_turns.append(
                    {
                        "role": _bounded_str(turn.get("role")),
                        "content": _bounded_str(turn.get("content")),
                    }
                )
        item["stored_turns"] = stored_turns
        return item

    item["source_case_id"] = _bounded_str(record.get("query_id") or record.get("id"))
    item["question"] = _bounded_str(record.get("query"))
    item["expected_keywords"] = _bounded_str_list(record.get("expected_keywords"))
    item["expected_source_labels"] = _bounded_str_list(record.get("expected_sources"))
    item["split"] = _bounded_str(record.get("dataset_split"))
    item["difficulty"] = _bounded_str(record.get("difficulty"))
    item["query_category"] = _bounded_str(record.get("query_category"))
    item["source_family"] = _bounded_str(record.get("source_family"))
    item["topic"] = _bounded_str(record.get("topic"))
    item["label_confidence"] = _bounded_str(record.get("label_confidence"))
    item["raw_review_status"] = _bounded_str(record.get("review_status"))
    return item


def get_catalog_cases(
    catalog_id: str,
    *,
    revision: str,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    source = _SOURCE_BY_ID.get(catalog_id)
    if source is None:
        raise CatalogNotFoundError(catalog_id)
    if source.kind not in _CASE_KINDS:
        raise CatalogCasesUnavailableError(catalog_id)

    try:
        _, current_revision, parsed = _json_snapshot(source)
    except CatalogSourceError as exc:
        raise CatalogUnavailableError(exc.reason, exc.availability) from exc
    if revision != current_revision:
        raise CatalogRevisionChangedError(current_revision)

    if source.kind == "query_fixture":
        try:
            records = _query_records(parsed)
        except CatalogSourceError as exc:
            raise CatalogUnavailableError(exc.reason, exc.availability) from exc
    else:
        try:
            records, _ = _conversation_records(parsed)
        except CatalogSourceError as exc:
            raise CatalogUnavailableError(exc.reason, exc.availability) from exc

    page = records[offset : offset + limit]
    return {
        "catalog_id": source.catalog_id,
        "revision_sha256": current_revision,
        "total": len(records),
        "offset": offset,
        "limit": limit,
        "items": [
            _case_item(record, revision=current_revision, ordinal=offset + index, kind=source.kind)
            for index, record in enumerate(page)
        ],
    }
