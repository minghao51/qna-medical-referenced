"""Read-only research catalog projections: allowlist, bounds and revisions."""

import json
from pathlib import Path

import pytest

from src.evals import research_catalog
from src.evals.research_catalog import (
    CatalogCasesUnavailableError,
    CatalogNotFoundError,
    CatalogRevisionChangedError,
    get_catalog_cases,
    get_catalog_entry,
    list_catalog,
)


def _write_json(root: Path, name: str, payload) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def catalog_roots(tmp_path, monkeypatch):
    fixtures = tmp_path / "fixtures"
    review = tmp_path / "review"
    reference = tmp_path / "reference"
    _write_json(
        fixtures,
        "golden_queries_all.json",
        {
            "golden_queries": [
                {"query": "alpha", "dataset_split": "test", "label_confidence": "high"},
                {"query": "beta", "dataset_split": "dev", "label_confidence": "medium"},
                {"query": "gamma", "dataset_split": "test", "label_confidence": "high"},
            ]
        },
    )
    _write_json(
        fixtures,
        "golden_queries_expanded.json",
        {
            "golden_queries": [
                {"query": "beta", "dataset_split": "dev", "label_confidence": "medium"},
                {"query": "gamma", "dataset_split": "test", "label_confidence": "high"},
                {"query": "delta", "dataset_split": "test", "label_confidence": "high"},
            ]
        },
    )
    _write_json(
        fixtures,
        "golden_queries.json",
        {"golden_queries": [{"query": "alpha", "dataset_split": "test"}]},
    )
    _write_json(
        fixtures,
        "golden_conversations.json",
        {
            "golden_conversations": [
                {
                    "conversation_id": "conv-1",
                    "conversation_category": "topic_shift",
                    "turns": [
                        {"role": "user", "content": "first"},
                        {"role": "assistant", "content": "second"},
                    ],
                }
            ],
            "stop_words": [f"stop-{index}" for index in range(100)],
        },
    )
    _write_json(
        review,
        "dataset.json",
        [
            {"query_id": "case-1", "question": "q1", "answerability": "answerable"},
            {"query_id": "case-2", "question": "q2", "answerability": "unanswerable"},
        ],
    )
    _write_json(
        review,
        "manifest.json",
        {
            "manifest_id": "test",
            "cases": {
                "case-1": {"review_status": "human_reviewed", "reviewer_id": "secret-reviewer"},
                "case-2": {"review_status": "human_reviewed", "reviewer_id": "secret-reviewer"},
            },
            "frozen_documents": {"chunk": "private corpus body"},
        },
    )
    reference.mkdir()
    (reference / "reference_ranges.csv").write_text("test,unit\nLDL-C,mmol/L\n", encoding="utf-8")

    monkeypatch.setattr(research_catalog, "FIXTURE_ROOT", fixtures)
    monkeypatch.setattr(research_catalog, "REVIEW_ROOT", review)
    monkeypatch.setattr(research_catalog, "REFERENCE_ROOT", reference)
    return {"fixtures": fixtures, "review": review, "reference": reference}


def _entry(catalog: dict, catalog_id: str) -> dict:
    return next(item for item in catalog["datasets"] if item["catalog_id"] == catalog_id)


def test_missing_roots_stay_missing_and_are_not_created(tmp_path, monkeypatch):
    fixtures = tmp_path / "missing-fixtures"
    review = tmp_path / "missing-review"
    reference = tmp_path / "missing-reference"
    monkeypatch.setattr(research_catalog, "FIXTURE_ROOT", fixtures)
    monkeypatch.setattr(research_catalog, "REVIEW_ROOT", review)
    monkeypatch.setattr(research_catalog, "REFERENCE_ROOT", reference)

    catalog = list_catalog()
    assert len(catalog["datasets"]) == 9
    assert catalog["overlap"] == []
    for entry in catalog["datasets"]:
        if entry["catalog_id"] == "d11-index":
            assert entry["availability"] == "inventory_reference"
            assert entry["inventory_ref"] == "/documents"
        else:
            assert entry["availability"] == "missing"
            assert entry["availability_reason"] == "file_missing"
            assert entry["revision_sha256"] is None
            assert entry["record_count"] is None
    assert not fixtures.exists()
    assert not review.exists()
    assert not reference.exists()


def test_entries_have_independent_availability(catalog_roots):
    (catalog_roots["fixtures"] / "golden_queries_diverse.json").write_text(
        "{not-json", encoding="utf-8"
    )
    catalog = list_catalog()

    assert _entry(catalog, "golden-diverse")["availability"] == "malformed"
    assert _entry(catalog, "golden-diverse")["availability_reason"] == "invalid_json"
    assert _entry(catalog, "golden-all")["availability"] == "available"
    assert _entry(catalog, "d11-review")["availability"] == "available"


def test_query_entry_counts_revision_and_overlap(catalog_roots):
    catalog = list_catalog()
    all_entry = _entry(catalog, "golden-all")
    assert all_entry["record_count"] == 3
    assert all_entry["record_unit"] == "question"
    assert all_entry["split_counts"] == {"dev": 1, "test": 2}
    assert all_entry["label_confidence_counts"] == {"high": 2, "medium": 1}
    assert all_entry["raw_review_status_counts"] is None
    assert all_entry["review_status_missing_count"] == 3
    assert all_entry["case_projection"] == "available"
    assert len(all_entry["revision_sha256"]) == 64

    overlap = catalog["overlap"][0]
    assert overlap["left_catalog_id"] == "golden-all"
    assert overlap["right_catalog_id"] == "golden-expanded"
    assert overlap["left_unique_query_count"] == 3
    assert overlap["right_unique_query_count"] == 3
    assert overlap["intersection_unique_query_count"] == 2
    assert overlap["method"] == "exact_stored_query_text"
    assert overlap["normalization"] == "none"
    assert overlap["near_duplicate_status"] == "not_assessed"
    assert overlap["left_revision"] == all_entry["revision_sha256"]


def test_conversation_units_ignore_support_arrays(catalog_roots):
    entry = _entry(list_catalog(), "golden-conversations")
    assert entry["record_count"] == 1
    assert entry["turn_count"] == 2
    assert entry["case_projection"] == "available"


def test_review_summary_excludes_reviewer_ids_and_bodies(catalog_roots):
    entry = get_catalog_entry("d11-review")
    assert entry["record_count"] == 2
    assert entry["split_counts"] == {"answerable": 1, "unanswerable": 1}
    assert entry["raw_review_status_counts"] == {"human_reviewed": 2}
    assert entry["review_status_missing_count"] == 0
    assert entry["review_authority"] == "manifest_declared_not_authenticated"
    assert entry["case_projection"] == "summary_only"
    serialized = json.dumps(entry)
    assert "reviewer_id" not in serialized
    assert "secret-reviewer" not in serialized
    assert "private corpus body" not in serialized

    with pytest.raises(CatalogCasesUnavailableError):
        get_catalog_cases("d11-review", revision=entry["revision_sha256"], limit=20, offset=0)


def test_reference_csv_counts_rows_separately(catalog_roots):
    entry = _entry(list_catalog(), "lab-reference")
    assert entry["kind"] == "reference_csv"
    assert entry["record_unit"] == "row"
    assert entry["record_count"] == 1
    assert entry["revision_sha256"] is not None


def test_case_projection_is_revision_bound_and_paged(catalog_roots):
    entry = get_catalog_entry("golden-all")
    revision = entry["revision_sha256"]

    page = get_catalog_cases("golden-all", revision=revision, limit=1, offset=1)
    assert page["total"] == 3
    assert page["offset"] == 1
    assert page["limit"] == 1
    assert page["revision_sha256"] == revision
    assert len(page["items"]) == 1
    case = page["items"][0]
    assert case["question"] == "beta"
    assert case["locator"] == {"revision_sha256": revision, "source_ordinal": 1}
    assert case["normalized_review_status"] is None
    assert case["stored_turns"] is None

    with pytest.raises(CatalogRevisionChangedError) as exc_info:
        get_catalog_cases("golden-all", revision="0" * 64, limit=20, offset=0)
    assert exc_info.value.current_revision_sha256 == revision


def test_conversation_cases_expose_minimal_stored_turns(catalog_roots):
    entry = get_catalog_entry("golden-conversations")
    page = get_catalog_cases(
        "golden-conversations", revision=entry["revision_sha256"], limit=20, offset=0
    )
    case = page["items"][0]
    assert case["source_case_id"] == "conv-1"
    assert case["question"] is None
    assert case["stored_turns"] == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
    ]


def test_unknown_ids_are_not_paths(catalog_roots):
    for candidate in ("../../etc/passwd", "..", "unknown", "golden-all.json"):
        with pytest.raises(CatalogNotFoundError):
            get_catalog_entry(candidate)
        with pytest.raises(CatalogNotFoundError):
            get_catalog_cases(candidate, revision="abc", limit=20, offset=0)


def test_symlink_escape_is_reported_missing(catalog_roots, tmp_path):
    fixture = catalog_roots["fixtures"] / "golden_queries.json"
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"golden_queries": [{"query": "outside"}]}), encoding="utf-8")
    fixture.unlink()
    fixture.symlink_to(outside)

    entry = _entry(list_catalog(), "golden-original")
    assert entry["availability"] == "missing"
    assert entry["availability_reason"] == "file_missing"


def test_size_and_record_caps_mark_entry_unavailable(catalog_roots, monkeypatch):
    monkeypatch.setattr(research_catalog, "MAX_SOURCE_BYTES", 5)
    catalog = list_catalog()
    assert _entry(catalog, "golden-all")["availability"] == "unsupported"
    assert _entry(catalog, "golden-all")["availability_reason"] == "size_cap_exceeded"

    monkeypatch.setattr(research_catalog, "MAX_SOURCE_BYTES", 5 * 1024 * 1024)
    monkeypatch.setattr(research_catalog, "MAX_RECORDS", 1)
    entry = _entry(list_catalog(), "golden-all")
    assert entry["availability"] == "unsupported"
    assert entry["availability_reason"] == "record_cap_exceeded"


def test_repository_fixtures_report_expected_counts_and_overlap():
    """Read-only acceptance check against the tracked current fixtures."""
    repository = Path(__file__).resolve().parents[3]
    if not (repository / "tests" / "fixtures" / "golden_queries_all.json").exists():
        pytest.skip("tracked fixture files are not present")

    catalog = list_catalog()
    all_entry = next(item for item in catalog["datasets"] if item["catalog_id"] == "golden-all")
    if all_entry["availability"] != "available":
        pytest.skip("fixtures are not available in this checkout")

    assert all_entry["record_count"] == 57
    assert all_entry["split_counts"] == {"dev": 17, "regression": 17, "test": 23}
    assert all_entry["label_confidence_counts"] == {"high": 43, "medium": 14}
    expanded = next(item for item in catalog["datasets"] if item["catalog_id"] == "golden-expanded")
    assert expanded["record_count"] == 54
    assert catalog["overlap"][0]["intersection_unique_query_count"] == 54

    conversations = next(
        item for item in catalog["datasets"] if item["catalog_id"] == "golden-conversations"
    )
    assert conversations["record_count"] == 15
    assert conversations["turn_count"] == 30

    review = next(item for item in catalog["datasets"] if item["catalog_id"] == "d11-review")
    if review["availability"] == "available":
        assert review["record_count"] == 8
        assert review["raw_review_status_counts"] == {"human_reviewed": 8}


def test_dockerfile_packages_only_the_six_approved_fixture_files():
    repository = Path(__file__).resolve().parents[3]
    dockerfile = (repository / "Dockerfile").read_text(encoding="utf-8")
    fixture_copies = [
        line for line in dockerfile.splitlines() if line.startswith("COPY tests/fixtures/")
    ]
    assert len(fixture_copies) == 6
    assert "COPY tests/ ./tests/" not in dockerfile
    assert "COPY . ." not in dockerfile
    for name in (
        "golden_queries.json",
        "golden_queries_comprehensive.json",
        "golden_queries_diverse.json",
        "golden_queries_expanded.json",
        "golden_queries_all.json",
        "golden_conversations.json",
    ):
        assert any(line.endswith(f"tests/fixtures/{name}") for line in fixture_copies)


def test_dockerignore_allows_the_six_fixture_files():
    repository = Path(__file__).resolve().parents[3]
    ignore_lines = (repository / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "tests/" not in ignore_lines
    assert "!tests/fixtures/" in ignore_lines
    for name in (
        "golden_queries.json",
        "golden_queries_comprehensive.json",
        "golden_queries_diverse.json",
        "golden_queries_expanded.json",
        "golden_queries_all.json",
        "golden_conversations.json",
    ):
        assert f"!tests/fixtures/{name}" in ignore_lines
