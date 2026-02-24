"""Keyword index and TF-IDF scoring helpers."""

import math
from typing import Callable


def build_term_frequencies(contents: list[str], tokenize: Callable[[str], list[str]]) -> dict[int, dict[str, int]]:
    term_freqs: dict[int, dict[str, int]] = {}
    for idx, content in enumerate(contents):
        tf: dict[str, int] = {}
        for token in tokenize(content):
            tf[token] = tf.get(token, 0) + 1
        term_freqs[idx] = tf
    return term_freqs


def build_keyword_index(contents: list[str], tokenize: Callable[[str], list[str]]) -> dict[str, list[int]]:
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

    scores: dict[int, float] = {}
    for token in set(query_tokens):
        if token not in keyword_index:
            continue

        doc_ids = keyword_index[token]
        idf = math.log((total_docs + 1) / (len(doc_ids) + 1)) + 1

        for doc_idx in doc_ids:
            tf = doc_term_freqs.get(doc_idx, {}).get(token, 0)
            tf_idf = (1 + math.log(tf)) * idf if tf > 0 else 0
            scores[doc_idx] = scores.get(doc_idx, 0) + tf_idf

    return scores

