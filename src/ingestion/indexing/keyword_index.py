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
