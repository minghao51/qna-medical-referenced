"""HTTP boundary for the read-only research catalog."""

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.app.routes import research
from src.evals import research_catalog


def _auth_request():
    return SimpleNamespace(state=SimpleNamespace(auth=object()))


@pytest.fixture
def fixed_catalog(tmp_path, monkeypatch):
    fixtures = tmp_path / "fixtures"
    review = tmp_path / "review"
    reference = tmp_path / "reference"
    fixtures.mkdir()
    (fixtures / "golden_queries_all.json").write_text(
        json.dumps({"golden_queries": [{"query": "alpha"}, {"query": "beta"}]}),
        encoding="utf-8",
    )
    (fixtures / "golden_queries_expanded.json").write_text(
        json.dumps({"golden_queries": [{"query": "beta"}]}), encoding="utf-8"
    )
    (fixtures / "golden_conversations.json").write_text(
        json.dumps(
            {
                "golden_conversations": [
                    {"conversation_id": "c1", "turns": [{"role": "user", "content": "hi"}]}
                ]
            }
        ),
        encoding="utf-8",
    )
    review.mkdir()
    (review / "dataset.json").write_text("[]", encoding="utf-8")
    (review / "manifest.json").write_text("{}", encoding="utf-8")
    reference.mkdir()
    (reference / "reference_ranges.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    monkeypatch.setattr(research_catalog, "FIXTURE_ROOT", fixtures)
    monkeypatch.setattr(research_catalog, "REVIEW_ROOT", review)
    monkeypatch.setattr(research_catalog, "REFERENCE_ROOT", reference)
    return fixtures


def test_catalog_routes_require_authentication():
    unauthenticated = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(HTTPException) as exc_info:
        research.list_research_datasets(unauthenticated)
    assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info:
        research.get_research_dataset("golden-all", unauthenticated)
    assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info:
        research.get_research_dataset_cases(
            "golden-all", unauthenticated, revision="abc", limit=20, offset=0
        )
    assert exc_info.value.status_code == 401


def test_list_returns_all_entries_and_overlap(fixed_catalog):
    response = research.list_research_datasets(_auth_request())
    payload = response.model_dump()
    assert len(payload["datasets"]) == 9
    assert {entry["catalog_id"] for entry in payload["datasets"]} >= {
        "golden-original",
        "golden-all",
        "golden-conversations",
        "d11-review",
        "lab-reference",
        "d11-index",
    }
    assert payload["overlap"][0]["intersection_unique_query_count"] == 1


def test_detail_rejects_unknown_id(fixed_catalog):
    with pytest.raises(HTTPException) as exc_info:
        research.get_research_dataset("not-a-dataset", _auth_request())
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "catalog_not_found"

    with pytest.raises(HTTPException) as exc_info:
        research.get_research_dataset("../fixtures/golden_queries.json", _auth_request())
    assert exc_info.value.status_code == 404


def test_detail_returns_entry(fixed_catalog):
    entry = research.get_research_dataset("golden-all", _auth_request())
    assert entry.catalog_id == "golden-all"
    assert entry.record_count == 2
    assert entry.revision_sha256 is not None
    assert entry.origin_ref == "golden_queries_all.json"


def test_cases_require_current_revision_and_bounds(fixed_catalog):
    entry = research.get_research_dataset("golden-all", _auth_request())
    page = research.get_research_dataset_cases(
        "golden-all",
        _auth_request(),
        revision=entry.revision_sha256 or "",
        limit=1,
        offset=1,
    )
    assert page.total == 2
    assert page.limit == 1
    assert page.offset == 1
    assert len(page.items) == 1
    assert page.items[0].question == "beta"

    with pytest.raises(HTTPException) as exc_info:
        research.get_research_dataset_cases(
            "golden-all", _auth_request(), revision="0" * 64, limit=20, offset=0
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "catalog_revision_changed"


def test_summary_only_entries_do_not_fake_cases(fixed_catalog):
    with pytest.raises(HTTPException) as exc_info:
        research.get_research_dataset_cases(
            "d11-index", _auth_request(), revision="abc", limit=20, offset=0
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "catalog_cases_unavailable"


def test_missing_entry_cases_return_unavailable(fixed_catalog):
    fixtures = fixed_catalog
    (fixtures / "golden_queries_diverse.json").unlink(missing_ok=True)
    with pytest.raises(HTTPException) as exc_info:
        research.get_research_dataset_cases(
            "golden-diverse", _auth_request(), revision="abc", limit=20, offset=0
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "catalog_unavailable"
