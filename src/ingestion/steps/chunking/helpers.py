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
        if is_new_item:
            if current:
                items.append("\n".join(current).strip())
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
    # Running length of "\n".join(current) plus its leading/trailing whitespace
    # counts, so the stripped candidate length is derived without re-joining.
    current_len = 0
    head_ws = 0
    tail_ws = 0
    limit = max(1, max_chars)

    for item in items:
        item_len = len(item)
        item_head_ws = item_len - len(item.lstrip())
        item_tail_ws = item_len - len(item.rstrip())
        item_is_whitespace = item_head_ws == item_len

        if current:
            candidate_len = current_len + 1 + item_len
            # Joining with "\n" only extends the leading whitespace run when the
            # accumulated text is whitespace-only, and the trailing run when the
            # new item is whitespace-only.
            candidate_head_ws = (
                current_len + 1 + item_head_ws if current_len == head_ws else head_ws
            )
            candidate_tail_ws = tail_ws + 1 + item_len if item_is_whitespace else item_tail_ws
            if candidate_len - candidate_head_ws - candidate_tail_ws > limit:
                groups.append("\n".join(current).strip())
                current = [item]
                current_len = item_len
                head_ws = item_head_ws
                tail_ws = item_tail_ws
                continue
            current.append(item)
            current_len = candidate_len
            head_ws = candidate_head_ws
            tail_ws = candidate_tail_ws
        else:
            current = [item]
            current_len = item_len
            head_ws = item_head_ws
            tail_ws = item_tail_ws

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
    # Running sum of row lengths, so the joined candidate length is derived
    # without re-joining rows on every append. All rows are stripped and
    # non-empty, so "\n".join(...) needs no further stripping.
    current_rows_len = 0
    header_extra = len(header) + 1 if repeat_header else 0

    def build_group(rows_for_group: list[str], header_repeated: bool) -> dict[str, object]:
        lines = [header, *rows_for_group] if header_repeated else rows_for_group
        return {"text": "\n".join(lines).strip(), "header_repeated": header_repeated}

    for row in data_rows:
        if current_rows:
            # len("\n".join([header?, *current_rows, row])) without building it:
            # one separator per accumulated row plus one for the new row (and
            # one more for the repeated header).
            candidate_len = current_rows_len + len(row) + len(current_rows) + header_extra
            if candidate_len > max_chars:
                groups.append(build_group(current_rows, repeat_header))
                current_rows = [row]
                current_rows_len = len(row)
                continue
        current_rows.append(row)
        current_rows_len += len(row)

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
    if lowered.endswith(".html"):
        return "html"
    if lowered.endswith(".md"):
        return "markdown"
    return "default"


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16] if content else ""
