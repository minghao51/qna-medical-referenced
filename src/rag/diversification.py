"""MMR diversification and result deduplication."""

from __future__ import annotations

import logging

from src.ingestion.indexing.text_utils import tokenize_text

logger = logging.getLogger(__name__)


def _source_page_key(item: dict) -> tuple[str, int | None]:
    return (str(item.get("source", "")), item.get("page"))


def _content_similarity(a: str, b: str) -> float:
    a_tokens = set(tokenize_text(a))
    b_tokens = set(tokenize_text(b))
    if not a_tokens or not b_tokens:
        return 0.0
    union = a_tokens | b_tokens
    if not union:
        return 0.0
    return len(a_tokens & b_tokens) / len(union)


def _score_field(item: dict) -> float:
    if "combined_score" in item:
        return float(item["combined_score"])
    if "score" in item:
        return float(item["score"])
    return 0.0


def mmr_rerank(results: list[dict], top_k: int, lambda_mult: float = 0.75) -> list[dict]:
    if len(results) <= 1:
        return results[:top_k]

    remaining = list(results)
    selected: list[dict] = []
    max_base = max((_score_field(r) for r in remaining), default=1.0) or 1.0

    while remaining and len(selected) < top_k:
        best_idx = 0
        best_mmr = None
        for idx, item in enumerate(remaining):
            base_score = _score_field(item) / max_base
            redundancy = 0.0
            if selected:
                redundancy = max(
                    _content_similarity(str(item.get("content", "")), str(s.get("content", "")))
                    for s in selected
                )
            mmr_score = lambda_mult * base_score - (1 - lambda_mult) * redundancy
            if best_mmr is None or mmr_score > best_mmr:
                best_mmr = mmr_score
                best_idx = idx
        selected.append(remaining.pop(best_idx))
    return selected


def diversify_results(
    results: list[dict],
    top_k: int,
    *,
    mmr_lambda: float = 0.75,
    overfetch_multiplier: int = 2,
    max_chunks_per_source_page: int = 2,
    max_chunks_per_source: int = 3,
    enable_diversification: bool = True,
) -> list[dict]:
    if not results:
        return []
    if not enable_diversification:
        return results[:top_k]
    mmr_candidates = mmr_rerank(
        results,
        top_k=max(top_k * max(1, int(overfetch_multiplier)), top_k),
        lambda_mult=mmr_lambda,
    )
    selected: list[dict] = []
    seen_ids: set[str] = set()
    seen_content_keys: set[str] = set()
    source_page_counts: dict[tuple[str, int | None], int] = {}
    source_counts: dict[str, int] = {}

    for item in mmr_candidates:
        item_id = str(item.get("id", ""))
        content_key = str(item.get("content", "")).strip()
        source = str(item.get("source", ""))
        sp_key = _source_page_key(item)

        if item_id and item_id in seen_ids:
            continue
        if content_key and content_key in seen_content_keys:
            continue
        if source_page_counts.get(sp_key, 0) >= max_chunks_per_source_page:
            continue
        if source_counts.get(source, 0) >= max_chunks_per_source:
            continue

        selected.append(item)
        if item_id:
            seen_ids.add(item_id)
        if content_key:
            seen_content_keys.add(content_key)
        source_page_counts[sp_key] = source_page_counts.get(sp_key, 0) + 1
        source_counts[source] = source_counts.get(source, 0) + 1
        if len(selected) >= top_k:
            break

    if len(selected) < top_k:
        selected_ids = {str(item.get("id", "")) for item in selected}
        for item in mmr_candidates:
            item_id = str(item.get("id", ""))
            if item_id and item_id in selected_ids:
                continue
            sp_key = _source_page_key(item)
            if source_page_counts.get(sp_key, 0) >= max_chunks_per_source_page + 1:
                continue
            selected.append(item)
            if item_id:
                selected_ids.add(item_id)
            source_page_counts[sp_key] = source_page_counts.get(sp_key, 0) + 1
            if len(selected) >= top_k:
                break
        if len(selected) < top_k:
            logger.warning(
                "Only %d/%d results after diversity constraints", len(selected), top_k
            )

    return selected
