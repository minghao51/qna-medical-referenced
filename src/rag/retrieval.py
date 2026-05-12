"""Candidate retrieval and result merging."""

from __future__ import annotations

import logging
from typing import Any

from src.rag.query_expansion import expand_lexical_queries

logger = logging.getLogger(__name__)


def _merge_result_sets(result_sets: list[list[dict]], top_k: int) -> list[dict]:
    merged: dict[str, dict] = {}
    for results in result_sets:
        for item in results:
            key = str(item.get("id"))
            existing = merged.get(key)
            if existing is None or float(
                item.get("score", item.get("combined_score", 0.0))
            ) > float(existing.get("score", existing.get("combined_score", 0.0))):
                merged[key] = dict(item)
    ranked = list(merged.values())
    ranked.sort(
        key=lambda row: float(row.get("score", row.get("combined_score", 0.0))), reverse=True
    )
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank
    return ranked[:top_k]


def _resolve_expanded_queries(
    query: str, pre_expanded_queries: list[str] | None
) -> list[str]:
    return list(pre_expanded_queries) if pre_expanded_queries is not None else expand_lexical_queries(query)


def retrieve_candidates(
    vector_store,
    query: str,
    top_k: int,
    search_mode: str,
    *,
    pre_expanded_queries: list[str] | None = None,
) -> list[dict]:
    expanded_queries = _resolve_expanded_queries(query, pre_expanded_queries)
    result_sets = [
        vector_store.similarity_search(expanded_query, top_k=top_k, search_mode=search_mode)
        for expanded_query in expanded_queries
    ]
    return _merge_result_sets(result_sets, top_k=top_k)


def retrieve_candidates_with_trace(
    vector_store,
    query: str,
    top_k: int,
    search_mode: str,
    *,
    pre_expanded_queries: list[str] | None = None,
) -> tuple[list[dict], dict]:
    expanded_queries = _resolve_expanded_queries(query, pre_expanded_queries)
    return _search_and_merge_traced(vector_store, expanded_queries, top_k, search_mode)


async def retrieve_candidates_with_trace_async(
    vector_store,
    query: str,
    top_k: int,
    search_mode: str,
    *,
    pre_expanded_queries: list[str] | None = None,
    hyde_client: Any = None,
    enable_hyde: bool = False,
    hyde_max_length: int = 200,
) -> tuple[list[dict], dict]:
    if pre_expanded_queries is None:
        from src.rag.query_expansion import expand_queries_async

        expanded_queries = await expand_queries_async(
            query,
            hyde_client=hyde_client,
            enable_hyde=enable_hyde,
            hyde_max_length=hyde_max_length,
        )
    else:
        expanded_queries = pre_expanded_queries
    results, merged_trace = _search_and_merge_traced(
        vector_store, expanded_queries, top_k, search_mode
    )
    merged_trace["hyde_enabled"] = enable_hyde
    return results, merged_trace


def _search_and_merge_traced(
    vector_store,
    expanded_queries: list[str],
    top_k: int,
    search_mode: str,
) -> tuple[list[dict], dict]:
    result_sets: list[list[dict]] = []
    traces: list[dict] = []
    for expanded_query in expanded_queries:
        results, trace = vector_store.similarity_search_with_trace(
            expanded_query, top_k=top_k, search_mode=search_mode
        )
        result_sets.append(results)
        traces.append(trace)
    merged_results = _merge_result_sets(result_sets, top_k=top_k)
    merged_trace = traces[0] if traces else {}
    merged_trace["expanded_queries"] = expanded_queries
    merged_trace["candidate_traces"] = traces
    merged_trace["result_count"] = len(merged_results)
    return merged_results, merged_trace
