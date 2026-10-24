"""URL-guard scoping in snapshot credential rejection (prose false-positive fix)."""

from __future__ import annotations

from typing import Any

import pytest

from src.evals.index_snapshot import (
    SnapshotError,
    _reject_credentials,
    freeze_index_snapshot,
)


@pytest.mark.parametrize(
    "value",
    [
        "See https://example.com/x and is it useful? Yes #indeed",
        "plain text",
        "https-only-ish text without scheme start: foo://bar",
        "",
        "17α-Hydroxyprogesterone 0.4-2.1 nmol/L",  # noqa: RUF001 - mandated medical prose
    ],
)
def test_accepts_prose_and_non_url_strings(value: str):
    _reject_credentials(value)


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://user:pass@host/db",
        "https://host/path?token=abc",
        "https://host/page#frag",
        "https://user@host",
        "HTTPS://HOST/PATH?Q=1",
        "weird+scheme.1://host?p=1",
    ],
)
def test_rejects_scheme_prefixed_strings_with_userinfo_query_or_fragment(value: str):
    with pytest.raises(SnapshotError):
        _reject_credentials(value)


@pytest.mark.parametrize(
    "value",
    [
        " https://user:pass@host/path?token=x",  # leading whitespace before the scheme
        "See https://user:pass@host/path for details",  # prose-embedded userinfo
        "x https://host/p?q=1",  # prose-embedded query
    ],
)
def test_rejects_padded_or_embedded_url_spans(value: str):
    with pytest.raises(SnapshotError):
        _reject_credentials(value)


@pytest.mark.parametrize(
    "payload",
    [
        {"api_key": "x"},
        {"request_headers": {}},
        {"auth": "1"},
        {"my_token": "1"},
        {"a": [{"api_key": "1"}]},
    ],
)
def test_key_name_rules_remain_enforced(payload: dict[str, Any]):
    with pytest.raises(SnapshotError):
        _reject_credentials(payload)


def test_freeze_accepts_prose_document_with_embedded_url():
    metadata = {
        "source_snapshot_sha256": "a" * 64,
        "embedding_model": "test-embedder",
        "embedding_batch_size": 8,
        "semantic_weight": 0.6,
        "keyword_weight": 0.2,
        "boost_weight": 0.2,
        "page_classification_enabled": True,
        "index_only_classified_pages": False,
        "html_extractor_mode": "auto",
        "html_extractor_strategy": "primary",
        "pdf_extractor_strategy": "pymupdf",
        "pdf_table_extractor": "none",
        "structured_chunking_enabled": True,
        "source_chunk_configs": "{}",
        "enable_hype": False,
        "hype_sample_rate": 0.0,
        "hype_max_chunks": 0,
        "hype_questions_per_chunk": 0,
        "enable_keyword_extraction": False,
        "enable_chunk_summaries": False,
        "keyword_extraction_sample_rate": 0.0,
        "keyword_extraction_max_chunks": 0,
    }
    prose = "See https://example.com/x and is it useful? Yes #indeed"
    payload: dict[str, Any] = {
        "snapshot": {
            "ids": ["doc-prose"],
            "contents": [prose],
            "metadatas": [{"source": "prose.txt"}],
            "embeddings": [[0.0, 1.0]],
            "index_metadata": metadata,
        },
        "build_spec": {
            "collection_name": "prose-test",
            "collection_metadata": metadata,
            "embedder": {"model": "test-embedder", "batch_size": 8, "dimensions": 2},
            "retrieval_weights": {"semantic": 0.6, "keyword": 0.2, "boost": 0.2},
        },
    }

    class _Source:
        def read_consistent_index_snapshot(self) -> dict[str, Any]:
            return payload

    frozen = freeze_index_snapshot(_Source())
    assert frozen.capture_payload()["snapshot"]["contents"] == [prose]
