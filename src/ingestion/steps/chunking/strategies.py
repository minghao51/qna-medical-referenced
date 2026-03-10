"""Chunk split strategies."""

from __future__ import annotations

import re


def find_legacy_split(text: str, start: int, end: int) -> int:
    for sep in ["\n\n", "\n", ". "]:
        last_sep = text.rfind(sep, start, end)
        if last_sep > start:
            return last_sep + len(sep)
    return end


def find_recursive_split(
    text: str,
    start: int,
    end: int,
    *,
    chunk_size: int,
    min_chunk_size: int,
) -> int:
    window = text[start:end]
    if not window:
        return end

    min_preferred = max(1, min(min_chunk_size, max(1, int(chunk_size * 0.6))))
    min_allowed_end = min(end, start + max(min_preferred, chunk_size // 4))
    candidate = None

    for sep in ["\n\n", "\n"]:
        pos = text.rfind(sep, min_allowed_end, end)
        if pos > start:
            candidate = pos + len(sep)
            break

    if candidate is None:
        sentence_matches = list(re.finditer(r"[.!?](?:\s|\n)", window))
        for match in reversed(sentence_matches):
            abs_end = start + match.end()
            if abs_end >= min_allowed_end:
                candidate = abs_end
                break

    if candidate is None:
        for sep in ["; ", ", ", " "]:
            pos = text.rfind(sep, min_allowed_end, end)
            if pos > start:
                candidate = pos + len(sep)
                break

    return candidate if candidate is not None else end
