"""Regression tests locking chunk outputs and schema for the chunking subsystem.

The golden fixture (tests/fixtures/chunking_regression_golden.json) is generated
by tests/fixtures/gen_chunking_golden.py. Custom/recursive cases lock the FULL
chunk dicts (ids, boundaries, metadata) and must stay byte-identical across
refactors. Chonkie cases lock the content-level projection (ids, content,
indices, counts); their dict schema is normalized to match the custom chunker's
schema (see test_chonkie_chunks_have_normalized_schema).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ingestion.steps.chunking.core import TextChunker
from tests.fixtures.gen_chunking_golden import (
    MARKDOWN_DOC,
    MULTI_SOURCE_DOCS,
    PER_SOURCE_CONFIGS,
    PLAIN_DOC,
    PLAIN_TEXT,
    STRUCTURED_DOC,
    _content_projection,
    _deterministic_embed,
)

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "chunking_regression_golden.json"

# Keys emitted by the custom chunker's base path (_chunk_text_with_base_index).
_BASE_CHUNK_KEYS = frozenset(
    {
        "id",
        "source",
        "page",
        "content",
        "content_type",
        "section_path",
        "chunk_index",
        "start_char",
        "end_char",
        "char_count",
        "token_count_estimate",
        "quality_score",
        "parent_block_ids",
        "extractor",
        "metadata",
    }
)
# Full normalized schema: base keys plus the linking/source keys that
# build_block_chunk emits (plus extractor). Chonkie chunks are normalized to
# this exact shape.
_FULL_CHUNK_KEYS = _BASE_CHUNK_KEYS | frozenset(
    {"previous_chunk_id", "next_chunk_id", "section_sibling_rank", "source_type"}
)


def _load_golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text())


def _custom_cases() -> dict:
    chunker = TextChunker(chunk_size=120, chunk_overlap=24, min_chunk_size=30)
    return {
        "plain_text_recursive": chunker.chunk_text(PLAIN_TEXT, "guide.pdf", "doc1", 2),
        "structured_blocks": TextChunker(chunk_size=512, chunk_overlap=64).chunk_documents(
            [STRUCTURED_DOC]
        ),
        "markdown_document": TextChunker(chunk_size=160, chunk_overlap=20).chunk_documents(
            [{"id": "md1", "source": "doc.md", "content": MARKDOWN_DOC}]
        ),
        "plain_doc_default_configs": TextChunker(chunk_size=512, chunk_overlap=64).chunk_documents(
            [PLAIN_DOC]
        ),
        "multi_source_per_doc_configs": TextChunker(
            chunk_size=512, chunk_overlap=64, min_chunk_size=100
        ).chunk_documents_with_configs(MULTI_SOURCE_DOCS, source_chunk_configs=PER_SOURCE_CONFIGS),
    }


@pytest.mark.parametrize(
    "case_name",
    [
        "plain_text_recursive",
        "structured_blocks",
        "markdown_document",
        "plain_doc_default_configs",
        "multi_source_per_doc_configs",
    ],
)
def test_custom_chunk_outputs_match_golden(case_name):
    golden = _load_golden()[case_name]
    actual = _custom_cases()[case_name]
    assert actual == golden


def test_custom_chunk_schema_is_stable():
    chunks = _custom_cases()["plain_text_recursive"]
    assert all(frozenset(chunk) == _BASE_CHUNK_KEYS for chunk in chunks)
    # build_block_chunk (list/table path) omits "extractor" but adds linking keys.
    structured = _custom_cases()["structured_blocks"]
    assert all(frozenset(chunk) >= _BASE_CHUNK_KEYS - {"extractor"} for chunk in structured)
    assert all(
        {"previous_chunk_id", "next_chunk_id", "source_type"} <= frozenset(chunk)
        for chunk in structured
    )


def _chonkie_cases() -> dict:
    pytest.importorskip("chonkie")
    import src.ingestion.steps.chunking.qwen_embedding_wrapper as qw

    original = qw.embed_texts
    qw.embed_texts = _deterministic_embed
    try:
        from src.ingestion.steps.chunking.chonkie_adapter import ChonkieChunkerAdapter

        recursive = ChonkieChunkerAdapter(
            strategy="chonkie_recursive", chunk_size=150, chunk_overlap=10
        ).chunk_text(PLAIN_TEXT, "guide.pdf", "doc1", 1)
        semantic = ChonkieChunkerAdapter(
            strategy="chonkie_semantic", chunk_size=150, chunk_overlap=10
        ).chunk_text(PLAIN_TEXT, "guide.pdf", "doc1", 1)
    finally:
        qw.embed_texts = original
    return {"chonkie_recursive": recursive, "chonkie_semantic": semantic}


@pytest.mark.parametrize(
    "case_name",
    ["chonkie_recursive", "chonkie_semantic"],
)
def test_chonkie_chunk_content_matches_golden(case_name):
    pytest.importorskip("chonkie")
    golden = _load_golden()[case_name]
    chunks = _chonkie_cases()[case_name]
    lock_token_count = case_name == "chonkie_recursive"
    assert _content_projection(chunks, lock_token_count=lock_token_count) == golden


def test_chonkie_chunks_have_normalized_schema():
    pytest.importorskip("chonkie")
    for chunks in _chonkie_cases().values():
        assert chunks
        for chunk in chunks:
            assert frozenset(chunk) == _FULL_CHUNK_KEYS


def test_chonkie_overlap_updates_token_count_estimate():
    pytest.importorskip("chonkie")
    import src.ingestion.steps.chunking.qwen_embedding_wrapper as qw

    original = qw.embed_texts
    qw.embed_texts = _deterministic_embed
    try:
        from src.ingestion.steps.chunking.chonkie_adapter import ChonkieChunkerAdapter

        chunks = ChonkieChunkerAdapter(
            strategy="chonkie_semantic", chunk_size=150, chunk_overlap=10
        ).chunk_text(PLAIN_TEXT, "guide.pdf", "doc1", 1)
    finally:
        qw.embed_texts = original
    assert len(chunks) > 1
    # The first chunk keeps chonkie's own token estimate; every chunk whose
    # content was rewritten by the overlap enrichment must have its estimate
    # recomputed to match the new content.
    assert chunks[0]["content"] == _load_golden()["chonkie_semantic"][0]["content"]
    for chunk in chunks[1:]:
        assert chunk["token_count_estimate"] == len(chunk["content"].split())
    for chunk in chunks:
        assert chunk["char_count"] == len(chunk["content"])


def test_medical_semantic_adapter_end_to_end(monkeypatch):
    """Lock the refactored medical_semantic flow (no dead NER preprocessing)."""
    pytest.importorskip("chonkie")
    import sys
    import types

    import src.ingestion.steps.chunking.qwen_embedding_wrapper as qw

    monkeypatch.setattr(qw, "embed_texts", _deterministic_embed)

    # Force the detector's regex fallback so the test needs no spaCy model.
    fake_spacy = types.ModuleType("spacy")

    def _load(*args, **kwargs):
        raise OSError("model not installed")

    fake_spacy.load = _load
    monkeypatch.setitem(sys.modules, "spacy", fake_spacy)

    from src.ingestion.steps.chunking.medical_semantic import MedicalSemanticChunkerAdapter

    adapter = MedicalSemanticChunkerAdapter(
        strategy="medical_semantic", chunk_size=150, chunk_overlap=10
    )
    text = (
        "CHIEF COMPLAINT: Chest pain.\n"
        "HISTORY OF PRESENT ILLNESS: Patient with hypertension. Aspirin 81 mg daily. "
        "Continue monitoring blood pressure closely. "
        * 6
        + "\nMEDICATIONS: Metformin 500 mg\nTest | Result | Range\nHemoglobin | 13.1 | 12-16\n"
    )
    chunks = adapter.chunk_text(text, "note.pdf", "doc9", 1)
    assert len(chunks) >= 2
    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    assert [chunk["id"] for chunk in chunks] == [
        f"doc9_p1_chunk_{idx}" for idx in range(len(chunks))
    ]
    for chunk in chunks:
        # Chonkie-normalized schema plus the medical metadata.
        assert frozenset(chunk) >= _FULL_CHUNK_KEYS
        assert "medical_preservation_score" in chunk["metadata"]
    # No dead preprocessing metadata is attached anywhere.
    for chunk in chunks:
        for key in ("clinical_sections", "lab_tables", "dosing_sections", "entity_boundaries"):
            assert key not in chunk
            assert key not in chunk["metadata"]
