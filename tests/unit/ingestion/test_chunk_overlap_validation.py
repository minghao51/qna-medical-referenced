"""Unit tests for chunk_overlap validation in resolve_source_chunk_configs."""

import pytest

from src.ingestion.steps.chunking.config import resolve_source_chunk_configs
from src.ingestion.steps.chunking.core import TextChunker


def test_default_configs_pass_overlap_validation():
    configs = resolve_source_chunk_configs(None, auto_select_strategy=False)
    assert configs["pdf"]["chunk_overlap"] == 64
    assert configs["default"]["chunk_overlap"] == 64


def test_valid_boundary_overlap_is_kept():
    # For chunk_size=512 the limit is 512 // 4 = 128, so 127 is the largest
    # legal overlap and must be preserved.
    configs = resolve_source_chunk_configs(
        {"pdf": {"chunk_size": 512, "chunk_overlap": 127}},
        auto_select_strategy=False,
    )
    assert configs["pdf"]["chunk_overlap"] == 127


@pytest.mark.parametrize(
    "chunk_overlap",
    [
        128,  # exactly at the limit (chunk_size // 4)
        200,
        64,  # == chunk_size, the stall-triggering config from the audit
        -1,
        "64",
        2.5,
    ],
)
def test_invalid_overlap_is_reset_by_default(chunk_overlap):
    configs = resolve_source_chunk_configs(
        {"pdf": {"chunk_size": 256, "chunk_overlap": chunk_overlap}},
        auto_select_strategy=False,
    )
    limit = max(1, 256 // 4)
    safe = min(32, 256 // 8)
    assert 0 <= configs["pdf"]["chunk_overlap"] < limit
    assert configs["pdf"]["chunk_overlap"] == safe


def test_invalid_overlap_raises_in_strict_mode():
    with pytest.raises(ValueError, match="Invalid chunk_overlap=64 for pdf"):
        resolve_source_chunk_configs(
            {"pdf": {"chunk_size": 64, "chunk_overlap": 64}},
            auto_select_strategy=False,
            strict_validation=True,
        )


def test_non_int_overlap_raises_in_strict_mode():
    with pytest.raises(ValueError, match=r"Invalid chunk_overlap=64\.5 for pdf"):
        resolve_source_chunk_configs(
            {"pdf": {"chunk_size": 512, "chunk_overlap": 64.5}},
            auto_select_strategy=False,
            strict_validation=True,
        )


def test_overlap_reset_respects_small_chunk_sizes():
    # With chunk_size=64 the safe default must shrink below the limit of 16.
    configs = resolve_source_chunk_configs(
        {"pdf": {"chunk_size": 64, "chunk_overlap": 64}},
        auto_select_strategy=False,
    )
    assert configs["pdf"]["chunk_overlap"] == min(32, 64 // 8)


def test_stalling_config_no_longer_hangs_chunker():
    # Regression for the audit finding: chunk_size=64 + chunk_overlap=64 used to
    # make _chunk_text_with_base_index loop forever. It must now terminate.
    chunker = TextChunker(chunk_size=64, chunk_overlap=64, min_chunk_size=10)
    chunks = chunker._chunk_text_with_base_index("word " * 200, "doc.pdf", "doc1")
    assert chunks
    assert all(c["content"] for c in chunks)


def test_valid_config_chunking_behavior_unchanged():
    chunker = TextChunker(chunk_size=100, chunk_overlap=20, min_chunk_size=10)
    chunks = chunker._chunk_text_with_base_index("word " * 100, "doc.pdf", "doc1")
    assert len(chunks) > 1
    # Overlap of 20 tokens between consecutive chunks is preserved.
    assert chunks[1]["start_char"] < chunks[0]["end_char"]
