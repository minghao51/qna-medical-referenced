"""Pydantic models for the read-only research catalog HTTP boundary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

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


class CatalogEntry(BaseModel):
    catalog_id: str
    label: str
    kind: CatalogKind
    availability: Availability
    availability_reason: AvailabilityReason | None = None
    origin_ref: str
    revision_sha256: str | None = None
    record_unit: RecordUnit
    record_count: int | None = None
    turn_count: int | None = None
    split_counts: dict[str, int] | None = None
    label_confidence_counts: dict[str, int] | None = None
    raw_review_status_counts: dict[str, int] | None = None
    review_status_missing_count: int | None = None
    review_authority: ReviewAuthority
    case_projection: CaseProjection
    inventory_ref: str | None = None


class CatalogOverlap(BaseModel):
    left_catalog_id: str
    left_revision: str
    right_catalog_id: str
    right_revision: str
    method: Literal["exact_stored_query_text"]
    left_unique_query_count: int
    right_unique_query_count: int
    intersection_unique_query_count: int
    normalization: Literal["none"]
    near_duplicate_status: Literal["not_assessed"]


class CatalogListResponse(BaseModel):
    datasets: list[CatalogEntry]
    overlap: list[CatalogOverlap]


class CaseLocator(BaseModel):
    revision_sha256: str
    source_ordinal: int


class StoredTurn(BaseModel):
    role: str | None = None
    content: str | None = None


class CatalogCase(BaseModel):
    locator: CaseLocator
    source_case_id: str | None = None
    question: str | None = None
    expected_keywords: list[str] | None = None
    expected_source_labels: list[str] | None = None
    split: str | None = None
    difficulty: str | None = None
    query_category: str | None = None
    source_family: str | None = None
    topic: str | None = None
    label_confidence: str | None = None
    raw_review_status: str | None = None
    normalized_review_status: str | None = None
    stored_turns: list[StoredTurn] | None = None


class CatalogCasesResponse(BaseModel):
    catalog_id: str
    revision_sha256: str
    total: int
    offset: int
    limit: int
    items: list[CatalogCase]
