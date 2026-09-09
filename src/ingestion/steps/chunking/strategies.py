"""Chunk split strategies and the strategy registry."""

from __future__ import annotations

import re

# Single source of truth for every chunking strategy selectable end-to-end
# (config validation, TextChunker, docs). Strategies:
# - recursive (default) / custom_recursive: in-house recursive chunker with
#   quality scoring
# - chonkie_recursive / chonkie_semantic / chonkie_late: chonkie-backed
# - medical_semantic: chonkie_semantic + medical structure rules (needs spacy)
CHUNKING_STRATEGIES: frozenset[str] = frozenset(
    {
        "recursive",
        "custom_recursive",
        "chonkie_recursive",
        "chonkie_semantic",
        "chonkie_late",
        "medical_semantic",
    }
)

# Strategies ChonkieChunkerAdapter handles directly. "medical_semantic" is
# deliberately absent: it goes through MedicalSemanticChunkerAdapter, which
# subclasses the adapter and forwards "chonkie_semantic" to it.
CHONKIE_ADAPTER_STRATEGIES: frozenset[str] = frozenset(
    {
        "chonkie_recursive",
        "chonkie_semantic",
        "chonkie_late",
    }
)


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
