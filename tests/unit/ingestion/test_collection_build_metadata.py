"""Offline guarantees for the Chroma collection build-metadata payload.

The payload must satisfy ``src.evals.index_snapshot``'s required-metadata
subset with validator-compatible types, must record live typed-configuration
values only, and its local corpus digest mirror must stay byte-compatible
with the D11 provenance source. Synthetic tmp-path fixtures only: no real
``data/`` reads and no network.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from src.config import settings
from src.evals.assessment.reporting import content_directory_provenance
from src.evals.index_snapshot import _REQUIRED_BUILD_METADATA, _reject_credentials
from src.ingestion.indexing.factory import get_vector_store_runtime_config
from src.ingestion.indexing.store import (
    _corpus_source_digest,
    build_collection_build_metadata,
)

_BOOL_KEYS = (
    "page_classification_enabled",
    "index_only_classified_pages",
    "structured_chunking_enabled",
    "enable_hype",
    "enable_keyword_extraction",
    "enable_chunk_summaries",
)
_NONEMPTY_STRING_KEYS = (
    "embedding_model",
    "html_extractor_mode",
    "html_extractor_strategy",
    "pdf_extractor_strategy",
    "pdf_table_extractor",
)
_WEIGHT_KEYS = ("semantic_weight", "keyword_weight", "boost_weight")


def _payload() -> dict[str, Any]:
    return build_collection_build_metadata(source_digest="b" * 64)


def test_payload_contains_every_required_key_with_valid_types():
    payload = _payload()
    assert _REQUIRED_BUILD_METADATA.issubset(payload)
    for key in _BOOL_KEYS:
        assert isinstance(payload[key], bool)
    for key in _NONEMPTY_STRING_KEYS:
        assert isinstance(payload[key], str)
        assert payload[key]
    for key in _WEIGHT_KEYS:
        value = payload[key]
        assert not isinstance(value, bool)
        assert isinstance(value, (int, float))
        assert math.isfinite(float(value))
    batch_size = payload["embedding_batch_size"]
    assert isinstance(batch_size, int)
    assert not isinstance(batch_size, bool)
    assert batch_size >= 1
    assert isinstance(payload["source_chunk_configs"], str)


def test_payload_values_come_from_live_typed_configuration():
    payload = _payload()
    runtime_config = get_vector_store_runtime_config()
    assert payload["embedding_model"] == settings.llm.embedding_model
    assert payload["embedding_batch_size"] == settings.llm.embedding_batch_size
    assert payload["semantic_weight"] == float(runtime_config["semantic_weight"])
    assert payload["keyword_weight"] == float(runtime_config["keyword_weight"])
    assert payload["boost_weight"] == float(runtime_config["boost_weight"])
    assert payload["page_classification_enabled"] == settings.ingestion.page_classification_enabled
    assert payload["index_only_classified_pages"] == settings.ingestion.index_only_classified_pages
    assert payload["structured_chunking_enabled"] == settings.ingestion.structured_chunking_enabled
    assert payload["html_extractor_mode"] == settings.ingestion.html_extractor_mode
    assert payload["html_extractor_strategy"] == settings.ingestion.html_extractor_strategy
    assert payload["pdf_extractor_strategy"] == settings.ingestion.pdf_extractor_strategy
    assert payload["pdf_table_extractor"] == settings.ingestion.pdf_table_extractor
    assert payload["enable_hype"] == settings.hype.enabled
    assert payload["hype_sample_rate"] == settings.hype.sample_rate
    assert payload["hype_max_chunks"] == settings.hype.max_chunks
    assert payload["hype_questions_per_chunk"] == settings.hype.questions_per_chunk
    assert payload["enable_keyword_extraction"] == settings.enrichment.enable_keyword_extraction
    assert payload["enable_chunk_summaries"] == settings.enrichment.enable_chunk_summaries
    assert (
        payload["keyword_extraction_sample_rate"]
        == settings.enrichment.keyword_extraction_sample_rate
    )
    assert (
        payload["keyword_extraction_max_chunks"]
        == settings.enrichment.keyword_extraction_max_chunks
    )


def test_source_chunk_configs_round_trips_and_passes_credential_guard():
    payload = _payload()
    chunk_configs = json.loads(payload["source_chunk_configs"])
    assert isinstance(chunk_configs, dict)
    assert chunk_configs
    for source_config in chunk_configs.values():
        assert isinstance(source_config, dict)
        assert {"chunk_size", "chunk_overlap", "strategy"}.issubset(source_config)
    # Passes the snapshot validator's own credential guard (must not raise),
    # and the encoding is exactly the deterministic canonical form.
    _reject_credentials(chunk_configs)
    _reject_credentials(payload)
    assert payload["source_chunk_configs"] == json.dumps(
        chunk_configs, ensure_ascii=False, sort_keys=True
    )


def test_payload_is_deterministic():
    assert build_collection_build_metadata("a" * 64) == build_collection_build_metadata("a" * 64)


@pytest.mark.parametrize("digest", ["a" * 64, "0" * 64, "f" * 64])
def test_explicit_source_digest_is_honored_verbatim(digest: str):
    assert build_collection_build_metadata(digest)["source_snapshot_sha256"] == digest


def test_default_source_digest_falls_back_to_corpus_digest(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "src.ingestion.indexing.store._corpus_source_digest", lambda directory: "d" * 64
    )
    assert build_collection_build_metadata()["source_snapshot_sha256"] == "d" * 64


def test_corpus_source_digest_matches_d11_provenance_byte_for_byte(tmp_path: Path):
    corpus = tmp_path / "raw"
    (corpus / "nested").mkdir(parents=True)
    (corpus / "guide.md").write_text("public fixture text", encoding="utf-8")
    (corpus / "nested" / "table.csv").write_bytes(b"a,b\n1,2\n")

    provenance = content_directory_provenance(corpus)
    assert provenance["status"] == "verified"
    assert _corpus_source_digest(corpus) == provenance["content_sha256"]


def test_corpus_source_digest_fails_closed_on_empty_or_unavailable_trees(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="source_tree_empty"):
        _corpus_source_digest(empty)

    with pytest.raises(ValueError, match="source_tree_unavailable"):
        _corpus_source_digest(tmp_path / "missing-corpus")

    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "link.md").symlink_to(empty)
    with pytest.raises(ValueError, match="source_tree_unavailable"):
        _corpus_source_digest(linked)
