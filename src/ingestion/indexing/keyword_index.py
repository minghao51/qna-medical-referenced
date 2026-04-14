"""Keyword index and BM25 scoring helpers."""

import math
from typing import Callable


def build_term_frequencies(
    contents: list[str], tokenize: Callable[[str], list[str]]
) -> dict[int, dict[str, int]]:
    term_freqs: dict[int, dict[str, int]] = {}
    for idx, content in enumerate(contents):
        tf: dict[str, int] = {}
        for token in tokenize(content):
            tf[token] = tf.get(token, 0) + 1
        term_freqs[idx] = tf
    return term_freqs


def build_keyword_index(
    contents: list[str], tokenize: Callable[[str], list[str]]
) -> dict[str, list[int]]:
    index: dict[str, list[int]] = {}
    for idx, content in enumerate(contents):
        for token in set(tokenize(content)):
            index.setdefault(token, []).append(idx)
    return index


def keyword_score(
    query: str,
    *,
    contents: list[str],
    keyword_index: dict[str, list[int]],
    doc_term_freqs: dict[int, dict[str, int]],
    tokenize: Callable[[str], list[str]],
) -> dict[int, float]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return {}

    total_docs = len(contents)
    if total_docs == 0:
        return {}

    doc_lengths = {idx: sum(freqs.values()) for idx, freqs in doc_term_freqs.items()}
    avg_doc_length = (sum(doc_lengths.values()) / total_docs) if total_docs else 0.0
    k1 = 1.5
    b = 0.75
    scores: dict[int, float] = {}
    for token in set(query_tokens):
        if token not in keyword_index:
            continue

        doc_ids = keyword_index[token]
        idf = math.log(1 + ((total_docs - len(doc_ids) + 0.5) / (len(doc_ids) + 0.5)))

        for doc_idx in doc_ids:
            tf = doc_term_freqs.get(doc_idx, {}).get(token, 0)
            if tf <= 0:
                continue
            doc_len = doc_lengths.get(doc_idx, 0)
            norm = 1 - b + b * (doc_len / avg_doc_length) if avg_doc_length else 1.0
            bm25 = idf * ((tf * (k1 + 1)) / (tf + (k1 * norm)))
            scores[doc_idx] = scores.get(doc_idx, 0.0) + bm25

    return scores


def keyword_score_with_extracted_keywords(
    query: str,
    *,
    contents: list[str],
    keyword_index: dict[str, list[int]],
    doc_term_freqs: dict[int, dict[str, int]],
    tokenize: Callable[[str], list[str]],
    extracted_keywords_list: list[list[str]] | None = None,
    keyword_boost_weight: float = 0.5,
) -> dict[int, float]:
    """BM25 keyword scoring with bonus for LLM-extracted keyword matches.

    Computes standard BM25 scores from chunk content, then adds a bonus
    score for chunks whose LLM-extracted keywords match query tokens.
    This bridges the gap between lay terms in queries and medical terminology
    that was extracted during ingestion.

    Args:
        query: The search query string
        contents: List of chunk content texts
        keyword_index: BM25 inverted index (token -> doc_indices)
        doc_term_freqs: Per-document term frequencies
        tokenize: Tokenization function
        extracted_keywords_list: List of extracted keyword lists per chunk index.
            extracted_keywords_list[i] = ["hypertension", "ldl", ...] for chunk i
        keyword_boost_weight: Multiplier for the base BM25 score added when
            extracted keywords match query tokens. 0.5 means a 50% bonus.

    Returns:
        Dict mapping doc_idx -> combined BM25 + extracted keyword bonus score
    """
    # Get base BM25 scores from content
    base_scores = keyword_score(
        query,
        contents=contents,
        keyword_index=keyword_index,
        doc_term_freqs=doc_term_freqs,
        tokenize=tokenize,
    )

    if not extracted_keywords_list:
        return base_scores

    query_tokens = set(tokenize(query))
    if not query_tokens:
        return base_scores

    # Build an index of extracted keywords: token -> set of doc indices
    extracted_keyword_index: dict[str, set[int]] = {}
    for doc_idx, keywords in enumerate(extracted_keywords_list):
        if not keywords:
            continue
        for kw in keywords:
            kw_lower = kw.lower().strip()
            if kw_lower:
                extracted_keyword_index.setdefault(kw_lower, set()).add(doc_idx)

    # Add bonus for chunks whose extracted keywords match query tokens
    bonus_scores: dict[int, float] = {}
    for token in query_tokens:
        if token not in extracted_keyword_index:
            continue
        for doc_idx in extracted_keyword_index[token]:
            base = base_scores.get(doc_idx, 0.0)
            bonus = base * keyword_boost_weight
            bonus_scores[doc_idx] = bonus_scores.get(doc_idx, 0.0) + bonus

    # Merge base and bonus scores
    combined = dict(base_scores)
    for doc_idx, bonus in bonus_scores.items():
        combined[doc_idx] = combined.get(doc_idx, 0.0) + bonus

    return combined
