"""Chunking helper utilities."""

from __future__ import annotations

import hashlib
import re

_DOC_METADATA_KEYS = (
    "logical_name",
    "source_url",
    "source_type",
    "source_class",
    "page_type",
    "canonical_label",
    "domain",
    "domain_type",
)


def build_chunk_metadata(doc_metadata: dict | None = None) -> dict:
    """Keep ingestion metadata attached to every chunk."""
    metadata = dict(doc_metadata or {})
    return {key: metadata.get(key) for key in _DOC_METADATA_KEYS if metadata.get(key) is not None}


def split_markdown_sections(text: str) -> list[tuple[int, str]]:
    heading_matches = list(re.finditer(r"(?m)^#{1,6}\s+.+$", text))
    if not heading_matches:
        return [(0, text)]

    sections: list[tuple[int, str]] = []
    first_heading_start = heading_matches[0].start()
    if first_heading_start > 0:
        preamble = text[:first_heading_start]
        if preamble.strip():
            sections.append((0, preamble))

    for idx, match in enumerate(heading_matches):
        start = match.start()
        end = heading_matches[idx + 1].start() if idx + 1 < len(heading_matches) else len(text)
        section = text[start:end]
        if section.strip():
            sections.append((start, section))
    return sections


def quality_score_for_block(block: dict, min_chunk_size: int) -> float:
    text = str(block.get("text", ""))
    lowered = text.lower()
    score = 1.0
    if len(text.strip()) < min_chunk_size:
        score -= 0.35
    boilerplate_hits = sum(
        lowered.count(term) for term in ("cookie", "privacy", "navigation", "subscribe")
    )
    if boilerplate_hits:
        score -= min(0.4, 0.08 * boilerplate_hits)
    confidence = str(block.get("metadata", {}).get("confidence", "high"))
    if confidence == "medium":
        score -= 0.15
    elif confidence == "low":
        score -= 0.35
    return max(0.0, min(1.0, score))


def build_block_chunk(
    *,
    text: str,
    source: str,
    doc_id: str,
    page: int,
    chunk_index: int,
    content_type: str,
    section_path: list[str],
    quality_score: float,
    parent_block_ids: list[str],
    source_type: str,
    doc_metadata: dict | None = None,
) -> dict:
    text = text.strip()
    chunk_metadata = build_chunk_metadata(doc_metadata)
    return {
        "id": f"{doc_id}_p{page}_chunk_{chunk_index}",
        "source": source,
        "page": page,
        "content": text,
        "content_type": content_type,
        "section_path": list(section_path),
        "chunk_index": chunk_index,
        "start_char": 0,
        "end_char": len(text),
        "char_count": len(text),
        "token_count_estimate": len(text.split()),
        "quality_score": quality_score,
        "parent_block_ids": list(parent_block_ids),
        "previous_chunk_id": None,
        "next_chunk_id": None,
        "section_sibling_rank": 0,
        "source_type": source_type,
        "metadata": chunk_metadata,
    }


def source_kind(source: str) -> str:
    lowered = str(source).lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if lowered.endswith(".md"):
        return "markdown"
    return "default"


def hash_content(content: str) -> str:
    return hashlib.sha256(content.lower().encode("utf-8")).hexdigest()[:16] if content else ""
