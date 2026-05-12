"""Query expansion: lexical, medical, and HyDE."""

from __future__ import annotations

import logging
from typing import Any

from src.ingestion.indexing.text_utils import ACRONYM_EXPANSIONS, tokenize_text
from src.rag.hyde import expand_query_with_hyde_async
from src.rag.medical_expansion import MedicalExpansion, get_medical_expansion_provider

logger = logging.getLogger(__name__)


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in queries:
        normalized = " ".join(item.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def expand_lexical_queries(query: str) -> list[str]:
    query = str(query or "").strip()
    if not query:
        return []
    outputs = [query]
    outputs.append(" ".join(tokenize_text(query)))
    expansion_terms: list[str] = []
    for token in tokenize_text(query):
        expansion_terms.extend(ACRONYM_EXPANSIONS.get(token, []))
    if expansion_terms:
        outputs.append(f"{query} {' '.join(expansion_terms)}")
    keyword_focus = " ".join(dict.fromkeys(tokenize_text(query.lower())))
    if keyword_focus:
        outputs.append(keyword_focus)
    return _dedupe_queries(outputs)


def expand_medical_terms(
    query: str,
    *,
    base_queries: list[str],
    enable_medical_expansion: bool = False,
    provider_name: str = "noop",
) -> list[MedicalExpansion]:
    if not enable_medical_expansion:
        return []
    provider = get_medical_expansion_provider(provider_name)
    expansions = provider.expand(query, base_queries=base_queries)
    normalized: list[MedicalExpansion] = []
    seen: set[tuple[str, str, str | None]] = set()
    for expansion in expansions:
        term = expansion.normalized()
        if not term:
            continue
        key = (term, str(expansion.source), expansion.relation)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            MedicalExpansion(term=term, source=str(expansion.source), relation=expansion.relation)
        )
    return normalized


def prepare_expanded_queries(
    query: str,
    *,
    enable_medical_expansion: bool = False,
    medical_expansion_provider: str = "noop",
) -> tuple[list[str], list[dict[str, str | None]]]:
    base_queries = expand_lexical_queries(query)
    medical_expansions = expand_medical_terms(
        query,
        base_queries=base_queries,
        enable_medical_expansion=enable_medical_expansion,
        provider_name=medical_expansion_provider,
    )
    medical_terms = [expansion.term for expansion in medical_expansions]
    return (
        _dedupe_queries(base_queries + medical_terms),
        [expansion.as_trace_payload() for expansion in medical_expansions],
    )


async def expand_queries_async(
    query: str,
    hyde_client: Any = None,
    enable_hyde: bool = False,
    hyde_max_length: int = 200,
    enable_medical_expansion: bool = False,
    medical_expansion_provider: str = "noop",
    pre_expanded_queries: list[str] | None = None,
) -> list[str]:
    base_queries = (
        list(pre_expanded_queries)
        if pre_expanded_queries is not None
        else prepare_expanded_queries(
            query,
            enable_medical_expansion=enable_medical_expansion,
            medical_expansion_provider=medical_expansion_provider,
        )[0]
    )

    if not enable_hyde or not hyde_client:
        return base_queries

    try:
        hyde_queries = await expand_query_with_hyde_async(
            query=query,
            client=hyde_client,
            enable_hyde=True,
            max_length=hyde_max_length,
        )
        all_queries = _dedupe_queries(base_queries + hyde_queries)
        logger.debug(f"HyDE expanded query '{query[:50]}...' to {len(all_queries)} variants")
        return all_queries
    except Exception as e:
        logger.error(
            f"HyDE expansion failed for query '{query}': {e}, falling back to base expansion"
        )
        return base_queries
