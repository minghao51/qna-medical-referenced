#!/usr/bin/env python3
"""Runtime RAG retrieval and index initialization."""

from dataclasses import asdict, dataclass
import logging
import time
from typing import Any, List, Tuple

from src.ingestion.indexing.vector_store import get_vector_store
from src.ingestion.indexing.text_utils import tokenize_text
from src.ingestion.steps.chunk_text import chunk_documents
from src.ingestion.steps.load_markdown import get_markdown_documents
from src.ingestion.steps.load_pdfs import get_documents
from src.ingestion.steps.load_reference_data import ReferenceDataLoader
from src.rag.formatting import build_context_and_sources

logger = logging.getLogger(__name__)


_vector_store_initialized = False
_RETRIEVAL_OVERFETCH_MULTIPLIER = 4
_MAX_CHUNKS_PER_SOURCE_PAGE = 2
_MAX_CHUNKS_PER_SOURCE = 3
_MMR_LAMBDA = 0.75


@dataclass
class RetrievalDiversityConfig:
    overfetch_multiplier: int = _RETRIEVAL_OVERFETCH_MULTIPLIER
    max_chunks_per_source_page: int = _MAX_CHUNKS_PER_SOURCE_PAGE
    max_chunks_per_source: int = _MAX_CHUNKS_PER_SOURCE
    mmr_lambda: float = _MMR_LAMBDA
    enable_diversification: bool = True
    search_mode: str = "hybrid"  # hybrid | semantic_only | keyword_only


def get_runtime_retrieval_config() -> dict[str, Any]:
    return asdict(RetrievalDiversityConfig())


def _resolve_retrieval_config(overrides: dict[str, Any] | None = None) -> RetrievalDiversityConfig:
    cfg = RetrievalDiversityConfig()
    if not overrides:
        return cfg
    for key, value in overrides.items():
        if value is None or not hasattr(cfg, key):
            continue
        setattr(cfg, key, value)
    cfg.overfetch_multiplier = max(1, int(cfg.overfetch_multiplier))
    cfg.max_chunks_per_source_page = max(1, int(cfg.max_chunks_per_source_page))
    cfg.max_chunks_per_source = max(1, int(cfg.max_chunks_per_source))
    cfg.mmr_lambda = max(0.0, min(1.0, float(cfg.mmr_lambda)))
    cfg.search_mode = str(cfg.search_mode or "hybrid").lower()
    if cfg.search_mode not in {"hybrid", "semantic_only", "keyword_only"}:
        cfg.search_mode = "hybrid"
    return cfg


def _build_index_from_sources(vector_store) -> None:
    loader = ReferenceDataLoader()
    pdf_docs = get_documents()
    markdown_docs = get_markdown_documents()
    chunked_docs = chunk_documents(pdf_docs)
    chunked_docs.extend(chunk_documents(markdown_docs))
    ref_docs = loader.load_reference_ranges_as_docs()
    chunked_docs.extend(ref_docs)
    stats = vector_store.add_documents(chunked_docs)
    print(
        "Indexed document chunks "
        f"(attempted={stats['attempted']}, inserted={stats['inserted']}, "
        f"duplicate_id={stats['skipped_duplicate_id']}, duplicate_content={stats['skipped_duplicate_content']})"
    )


def initialize_vector_store(rebuild: bool = False):
    global _vector_store_initialized

    vector_store = get_vector_store()

    if rebuild:
        vector_store.clear()
        _vector_store_initialized = False

    if _vector_store_initialized:
        return

    if vector_store.documents.get("contents"):
        _vector_store_initialized = True
        logger.info("Loaded existing vector store with %d documents", len(vector_store.documents["contents"]))
        return

    _build_index_from_sources(vector_store)
    _vector_store_initialized = True


def initialize_runtime_index(rebuild: bool = False):
    initialize_vector_store(rebuild=rebuild)


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


def _mmr_rerank(results: list[dict], top_k: int, lambda_mult: float = _MMR_LAMBDA) -> list[dict]:
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


def _diversify_results(
    results: list[dict],
    top_k: int,
    *,
    mmr_lambda: float = _MMR_LAMBDA,
    overfetch_multiplier: int = 2,
    max_chunks_per_source_page: int = _MAX_CHUNKS_PER_SOURCE_PAGE,
    max_chunks_per_source: int = _MAX_CHUNKS_PER_SOURCE,
    enable_diversification: bool = True,
) -> list[dict]:
    """
    Reduce redundant results from the same source/page while preserving score order.
    """
    if not results:
        return []
    if not enable_diversification:
        return results[:top_k]
    mmr_candidates = _mmr_rerank(
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

    # Fill remaining slots if diversity constraints were too strict.
    if len(selected) < top_k:
        selected_ids = {str(item.get("id", "")) for item in selected}
        for item in mmr_candidates:
            item_id = str(item.get("id", ""))
            if item_id and item_id in selected_ids:
                continue
            selected.append(item)
            if item_id:
                selected_ids.add(item_id)
            if len(selected) >= top_k:
                break

    return selected


def retrieve_context(query: str, top_k: int = 5, retrieval_options: dict[str, Any] | None = None):
    initialize_runtime_index()
    cfg = _resolve_retrieval_config(retrieval_options)

    vector_store = get_vector_store()
    fetch_k = max(top_k, top_k * cfg.overfetch_multiplier)
    results = vector_store.similarity_search(query, top_k=fetch_k, search_mode=cfg.search_mode)
    results = _diversify_results(
        results,
        top_k=top_k,
        mmr_lambda=cfg.mmr_lambda,
        overfetch_multiplier=cfg.overfetch_multiplier,
        max_chunks_per_source_page=cfg.max_chunks_per_source_page,
        max_chunks_per_source=cfg.max_chunks_per_source,
        enable_diversification=cfg.enable_diversification,
    )

    return build_context_and_sources(results)


def retrieve_context_with_trace(query: str, top_k: int = 5, retrieval_options: dict[str, Any] | None = None):
    """
    Retrieve context with detailed pipeline trace information.

    Returns:
        tuple: (context, sources, pipeline_trace)
            - context: Formatted context string for LLM
            - sources: List of source names
            - pipeline_trace: Dictionary with detailed pipeline metadata
    """
    from src.rag.trace_models import (
        ContextStage,
        GenerationStage,
        PipelineTrace,
        RetrievalStage,
        RetrievedDocument,
    )

    total_start = time.time()
    cfg = _resolve_retrieval_config(retrieval_options)

    initialize_runtime_index()
    vector_store = get_vector_store()

    fetch_k = max(top_k, top_k * cfg.overfetch_multiplier)
    results, retrieval_trace = vector_store.similarity_search_with_trace(
        query,
        top_k=fetch_k,
        search_mode=cfg.search_mode,
    )
    results = _diversify_results(
        results,
        top_k=top_k,
        mmr_lambda=cfg.mmr_lambda,
        overfetch_multiplier=cfg.overfetch_multiplier,
        max_chunks_per_source_page=cfg.max_chunks_per_source_page,
        max_chunks_per_source=cfg.max_chunks_per_source,
        enable_diversification=cfg.enable_diversification,
    )

    retrieved_docs = []
    for r in results:
        retrieved_docs.append(RetrievedDocument(
            id=r["id"],
            content=r["content"],
            source=r["source"],
            page=r.get("page"),
            semantic_score=r["semantic_score"],
            keyword_score=r["keyword_score"],
            source_boost=r["source_boost"],
            combined_score=r["combined_score"],
            rank=r["rank"]
        ))

    retrieval_timing_ms = retrieval_trace.get("timing_ms", 0)
    retrieval_stage = RetrievalStage(
        query=query,
        top_k=top_k,
        documents=retrieved_docs,
        score_weights={
            **retrieval_trace.get("score_weights", {}),
            "search_mode": cfg.search_mode,
            "enable_diversification": cfg.enable_diversification,
            "mmr_lambda": cfg.mmr_lambda,
            "overfetch_multiplier": cfg.overfetch_multiplier,
            "max_chunks_per_source_page": cfg.max_chunks_per_source_page,
            "max_chunks_per_source": cfg.max_chunks_per_source,
        },
        timing_ms=retrieval_timing_ms
    )

    context, sources = build_context_and_sources(results)
    context_stage = ContextStage(
        total_chunks=len(results),
        total_chars=len(context),
        sources=sources,
        preview=context[:200] + "..." if len(context) > 200 else context
    )

    generation_stage = GenerationStage(
        model="models/gemini-2.5-flash",
        timing_ms=0,
        tokens_estimate=None
    )

    total_time_ms = int((time.time() - total_start) * 1000)
    pipeline_trace = PipelineTrace(
        retrieval=retrieval_stage,
        context=context_stage,
        generation=generation_stage,
        total_time_ms=total_time_ms
    )

    return context, sources, pipeline_trace


def get_full_context() -> str:
    loader = ReferenceDataLoader()
    ranges = loader.load_reference_ranges()
    pdf_texts = loader.load_pdfs_text()
    return f"{ranges}\n\n{pdf_texts}"


def get_context(query: str | None = None) -> Tuple[str, List[str]]:
    if query:
        return retrieve_context(query)
    return get_full_context(), []
