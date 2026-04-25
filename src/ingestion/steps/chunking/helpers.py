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


def split_list_items(text: str) -> list[str]:
    """Split a list block into whole bullet items, preserving continuation lines."""
    items: list[str] = []
    current: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if current:
                current.append("")
            continue

        is_new_item = bool(re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", line))
        if is_new_item and current:
            items.append("\n".join(current).strip())
            current = [line]
            continue
        if is_new_item:
            current = [line]
            continue
        if current:
            current.append(line)
        else:
            current = [line]

    if current:
        items.append("\n".join(current).strip())

    return [item for item in items if item]


def group_list_items(items: list[str], max_chars: int) -> list[str]:
    """Group whole list items without splitting individual bullets."""
    if not items:
        return []

    groups: list[str] = []
    current: list[str] = []
    limit = max(1, max_chars)

    for item in items:
        candidate = "\n".join([*current, item]).strip()
        if current and len(candidate) > limit:
            groups.append("\n".join(current).strip())
            current = [item]
            continue
        current.append(item)

    if current:
        groups.append("\n".join(current).strip())
    return groups


def split_table_rows(
    text: str,
    *,
    max_chars: int,
    repeat_header: bool = True,
) -> list[dict[str, object]]:
    """Split a table block by rows, optionally repeating the header row."""
    rows = [row.strip() for row in text.splitlines() if row.strip()]
    if not rows:
        return []
    if len(rows) == 1 or len(text.strip()) <= max_chars:
        return [{"text": "\n".join(rows), "header_repeated": False}]

    header = rows[0]
    data_rows = rows[1:]
    groups: list[dict[str, object]] = []
    current_rows: list[str] = []

    def build_group(rows_for_group: list[str], header_repeated: bool) -> dict[str, object]:
        lines = [header, *rows_for_group] if header_repeated else rows_for_group
        return {"text": "\n".join(lines).strip(), "header_repeated": header_repeated}

    for row in data_rows:
        candidate_rows = [*current_rows, row]
        candidate_group = build_group(candidate_rows, repeat_header)
        if current_rows and len(str(candidate_group["text"])) > max_chars:
            groups.append(build_group(current_rows, repeat_header))
            current_rows = [row]
            continue
        current_rows = candidate_rows

    if current_rows:
        groups.append(build_group(current_rows, repeat_header))

    if not groups:
        return [{"text": "\n".join(rows), "header_repeated": False}]

    return groups


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
