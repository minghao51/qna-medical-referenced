"""Document listing projections: global facets and optional source labels."""

from __future__ import annotations

from typing import Any

from src.ingestion.indexing.listing import DocumentListingMixin


class _FakeCollection:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records

    def get(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int,
        offset: int,
        include: list[str],
    ) -> dict[str, Any]:
        del include
        records = self.records
        if where is not None:
            records = [
                record
                for record in records
                if record["metadata"].get("source_type") == where["source_type"]
            ]
        page = records[offset : offset + limit]
        return {
            "ids": [record["id"] for record in page],
            "documents": [record["content"] for record in page],
            "metadatas": [record["metadata"] for record in page],
        }


class _Listing(DocumentListingMixin):
    def __init__(self, records: list[dict[str, Any]], index_metadata: dict[str, Any]) -> None:
        self._collection = _FakeCollection(records)
        self._doc_metadatas = [record["metadata"] for record in records]
        self._index_metadata = index_metadata

    def _rebuild_index_if_needed(self) -> None:
        return None


def _records() -> list[dict[str, Any]]:
    return [
        {
            "id": "pdf-1",
            "content": "x" * 300,
            "metadata": {
                "source": "a.pdf",
                "page": 4,
                "source_type": "pdf",
                "source_class": "guideline_pdf",
                "content_type": "paragraph",
                "canonical_label": "Lipid guideline",
                "logical_name": "lipid_guideline",
                "source_url": "https://example.org/guideline",
                "domain": "example.org",
            },
        },
        {
            "id": "pdf-2",
            "content": "second",
            "metadata": {
                "source": "b.pdf",
                "page": 1,
                "source_type": "pdf",
                "source_class": "guideline_pdf",
                "source_url": "javascript:alert(1)",
            },
        },
        {
            "id": "pdf-3",
            "content": "third",
            "metadata": {"source": "c.pdf", "source_type": "pdf", "source_class": "guideline_pdf"},
        },
        {
            "id": "html-1",
            "content": "html",
            "metadata": {
                "source": "page.html",
                "page": 1,
                "source_type": "html",
                "source_class": "guideline_html",
            },
        },
        {
            "id": "html-2",
            "content": "html two",
            "metadata": {"source": "page2.html", "source_type": "html"},
        },
    ]


def test_filtered_counts_keep_semantics_and_global_counts_stay_full() -> None:
    listing = _Listing(_records(), {"source_snapshot_sha256": "a" * 64})

    page = listing.list_documents_paginated(limit=2, offset=0, source_type="pdf")

    assert page["total"] == 3
    assert [item["id"] for item in page["items"]] == ["pdf-1", "pdf-2"]
    assert page["source_type_counts"] == {"pdf": 3}
    assert page["global_source_type_counts"] == {"pdf": 3, "html": 2}
    assert page["index_identity"] == "a" * 64


def test_unfiltered_page_keeps_filtered_counts_equal_to_global() -> None:
    listing = _Listing(_records(), {})

    page = listing.list_documents_paginated(limit=50, offset=0)

    assert page["total"] == 5
    assert page["source_type_counts"] == {"pdf": 3, "html": 2}
    assert page["global_source_type_counts"] == {"pdf": 3, "html": 2}
    assert page["index_identity"] is None


def test_unknown_filter_returns_zero_rows_but_global_facets_survive() -> None:
    listing = _Listing(_records(), {"source_snapshot_sha256": "f" * 64})

    page = listing.list_documents_paginated(limit=50, offset=0, source_type="unknown")

    assert page["total"] == 0
    assert page["source_type_counts"] == {}
    assert page["global_source_type_counts"] == {"pdf": 3, "html": 2}


def test_items_expose_only_present_labels_and_safe_urls() -> None:
    listing = _Listing(_records(), {"source_snapshot_sha256": "not-a-digest"})

    page = listing.list_documents_paginated(limit=3, offset=0, source_type="pdf")
    first, second, third = page["items"]

    assert first["canonical_label"] == "Lipid guideline"
    assert first["logical_name"] == "lipid_guideline"
    assert first["source_url"] == "https://example.org/guideline"
    assert first["domain"] == "example.org"
    assert first["content_preview"] == "x" * 200

    assert second["canonical_label"] is None
    assert second["source_url"] is None
    assert third["source_url"] is None
    assert page["index_identity"] is None
