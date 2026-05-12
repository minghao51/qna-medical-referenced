"""Runtime RAG retrieval — thin facade delegating to focused modules.

Public API re-exports are in src/rag/__init__.py.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.config import settings
from src.ingestion.indexing.chroma_store import get_vector_store
from src.rag.config import (
    RetrievalDiversityConfig,
    resolve_retrieval_config,
)
from src.rag.diversification import diversify_results
from src.rag.index import initialize_runtime_index
from src.rag.query_expansion import prepare_expanded_queries
from src.rag.trace_models import ChatSource, RetrievedDocument

logger = logging.getLogger(__name__)


def _empty_pipeline_trace(query: str, top_k: int):
    from src.rag.trace_models import ContextStage, GenerationStage, PipelineTrace, RetrievalStage

    return PipelineTrace(
        retrieval=RetrievalStage(
            query=query,
            query_original_length=len(query),
            query_truncated=False,
            top_k=max(0, top_k),
            documents=[],
            score_weights={},
            timing_ms=0,
            steps=[],
        ),
        context=ContextStage(total_chunks=0, total_chars=0, sources=[], preview=""),
        generation=GenerationStage(model=settings.llm.model_name, timing_ms=0, tokens_estimate=0),
        total_time_ms=0,
    )


def _apply_query_understanding(
    query: str,
    retrieval_options: dict[str, Any] | None,
    cfg,
) -> dict[str, Any]:
    if not cfg.enable_query_understanding:
        return retrieval_options or {}

    try:
        from src.rag.query_understanding.classifier import classify_query
        from src.rag.query_understanding.router import get_retrieval_params_for_query

        classification = classify_query(query)
        query_params = get_retrieval_params_for_query(query, classification)
        merged = dict(retrieval_options or {})
        merged.update(query_params)
        logger.debug(
            f"Query understanding applied: type={classification.query_type.value}, "
            f"confidence={classification.confidence}"
        )
        return merged
    except Exception as e:
        logger.warning(f"Query understanding failed, using default options: {e}")
        return retrieval_options or {}


def _extend_with_hype_questions(
    vector_store,
    query: str,
    expanded_queries: list[str],
    *,
    enable_hype: bool,
    limit: int = 5,
) -> tuple[list[str], list[str]]:
    if not enable_hype:
        return expanded_queries, []
    selected_hype_questions = vector_store.search_hypothetical_questions(query, limit=limit)
    combined_queries = list(expanded_queries)
    for question in selected_hype_questions:
        if question not in combined_queries:
            combined_queries.append(question)
    return combined_queries, selected_hype_questions


def _build_retrieved_documents(results: list[dict]) -> list[RetrievedDocument]:
    retrieved_docs = []
    for r in results:
        metadata = r.get("metadata", {})
        retrieved_docs.append(
            RetrievedDocument(
                id=r["id"],
                content=r["content"],
                source=r["source"],
                page=r.get("page"),
                semantic_score=r["semantic_score"],
                keyword_score=r["keyword_score"],
                source_prior=r.get("source_prior", 0.0),
                source_boost=r.get("source_prior", 0.0),
                combined_score=r["combined_score"],
                rank=r["rank"],
                semantic_rank=r.get("semantic_rank"),
                bm25_rank=r.get("bm25_rank"),
                fused_rank=r.get("fused_rank"),
                fused_score=r.get("fused_score"),
                chunk_quality_score=r.get("quality_score"),
                content_type=r.get("content_type"),
                section_path=r.get("section_path", []),
                canonical_label=metadata.get("canonical_label"),
                display_label=metadata.get("display_label"),
                logical_name=metadata.get("logical_name"),
                source_url=metadata.get("source_url"),
                source_type=metadata.get("source_type"),
                source_class=metadata.get("source_class"),
                domain=metadata.get("domain"),
                domain_type=metadata.get("domain_type"),
            )
        )
    return retrieved_docs


def _apply_reranking(
    query: str,
    results: list[dict],
    *,
    fetch_k: int,
    cfg,
):
    if not (cfg.enable_reranking and cfg.reranking_mode in {"cross_encoder", "both"}):
        return results, None, {}

    from src.rag.reranker import get_reranker

    reranker = get_reranker()
    rerank_candidates_count = cfg.rerank_top_k or fetch_k
    candidates = (
        results[:rerank_candidates_count] if rerank_candidates_count < len(results) else results
    )
    rerank_result = reranker.rerank(
        query=query,
        results=candidates,
        top_k=fetch_k,
        min_score=cfg.rerank_score_threshold,
    )
    rerank_info = {
        "reranker_model": rerank_result.model_name,
        "rerank_timing_ms": rerank_result.timing_ms,
        "rerank_candidates_requested": rerank_candidates_count,
        "rerank_candidates_available": len(results),
        "rerank_candidates_reranked": rerank_result.candidates_count,
        "rerank_output": rerank_result.output_count,
        "rerank_score_threshold": cfg.rerank_score_threshold,
        "rerank_filtered_out": rerank_result.filtered_out_count,
    }
    return rerank_result.reranked_results, rerank_result, rerank_info


def _rerank_and_diversify(
    results: list[dict],
    query: str,
    top_k: int,
    fetch_k: int,
    cfg,
):
    results, rerank_result, rerank_info = _apply_reranking(query, results, fetch_k=fetch_k, cfg=cfg)
    from src.rag.config import should_apply_diversification

    apply_div = should_apply_diversification(cfg)
    results = diversify_results(
        results,
        top_k=top_k,
        mmr_lambda=cfg.mmr_lambda,
        overfetch_multiplier=cfg.overfetch_multiplier,
        max_chunks_per_source_page=cfg.max_chunks_per_source_page,
        max_chunks_per_source=cfg.max_chunks_per_source,
        enable_diversification=apply_div,
    )
    return results, rerank_result, rerank_info, apply_div


def _build_pipeline_trace(
    *,
    results: list[dict],
    retrieval_trace: dict,
    cfg,
    medical_expansion_trace: list,
    apply_diversification: bool,
    rerank_info: dict,
    original_length: int,
    query: str,
    top_k: int,
    total_start: float,
    steps: list | None = None,
):
    from src.rag.formatting import build_context_and_sources
    from src.rag.trace_models import (
        ContextStage,
        GenerationStage,
        PipelineTrace,
        RetrievalStage,
    )

    retrieved_docs = _build_retrieved_documents(results)
    retrieval_timing_ms = retrieval_trace.get("timing_ms", 0)
    retrieval_stage = RetrievalStage(
        query=query,
        query_original_length=original_length,
        query_truncated=(original_length > 4000),
        top_k=top_k,
        documents=retrieved_docs,
        score_weights={
            **retrieval_trace.get("score_weights", {}),
            "embedding_model": retrieval_trace.get("embedding_model"),
            "query_embedding_timing_ms": retrieval_trace.get("query_embedding_timing_ms", 0),
            "search_mode": cfg.search_mode,
            "expanded_queries": retrieval_trace.get("expanded_queries", []),
            "enable_medical_expansion": cfg.enable_medical_expansion,
            "medical_expansion_provider": cfg.medical_expansion_provider,
            "medical_expansion_terms": medical_expansion_trace,
            "medical_expansion_term_count": len(medical_expansion_trace),
            "enable_diversification": apply_diversification,
            "mmr_lambda": cfg.mmr_lambda,
            "overfetch_multiplier": cfg.overfetch_multiplier,
            "max_chunks_per_source_page": cfg.max_chunks_per_source_page,
            "max_chunks_per_source": cfg.max_chunks_per_source,
            "enable_reranking": cfg.enable_reranking,
            "reranking_mode": cfg.reranking_mode,
            "retrieval_candidate_count": retrieval_trace.get("result_count", len(results)),
            **rerank_info,
            "returned_documents": len(results),
        },
        timing_ms=retrieval_timing_ms,
        steps=steps or [],
    )

    context, source_labels, chat_sources = build_context_and_sources(results)
    context_stage = ContextStage(
        total_chunks=len(results),
        total_chars=len(context),
        sources=source_labels,
        preview=context[:200] + "..." if len(context) > 200 else context,
    )

    generation_stage = GenerationStage(
        model=settings.llm.model_name, timing_ms=0, tokens_estimate=None
    )
    total_time_ms = int((time.time() - total_start) * 1000)
    return (
        context,
        chat_sources,
        PipelineTrace(
            retrieval=retrieval_stage,
            context=context_stage,
            generation=generation_stage,
            total_time_ms=total_time_ms,
        ),
    )


def retrieve_context_with_trace(
    query: str, top_k: int = 5, retrieval_options: dict[str, Any] | None = None
):
    if not query or not query.strip():
        return "", [], _empty_pipeline_trace("", top_k)
    query, original_length, cfg, total_start, vector_store = _prepare_query(
        query, retrieval_options
    )

    fetch_k = max(top_k, top_k * cfg.overfetch_multiplier)
    expanded_queries, medical_expansion_trace = prepare_expanded_queries(
        query,
        enable_medical_expansion=cfg.enable_medical_expansion,
        medical_expansion_provider=cfg.medical_expansion_provider,
    )
    expanded_queries, _ = _extend_with_hype_questions(
        vector_store,
        query,
        expanded_queries,
        enable_hype=cfg.enable_hype,
    )

    from src.rag.retrieval import retrieve_candidates_with_trace as retrieve_fn

    results, retrieval_trace = retrieve_fn(
        vector_store,
        query,
        fetch_k,
        cfg.search_mode,
        pre_expanded_queries=expanded_queries,
    )

    results, _, rerank_info, apply_div = _rerank_and_diversify(results, query, top_k, fetch_k, cfg)

    return _build_pipeline_trace(
        results=results,
        retrieval_trace=retrieval_trace,
        cfg=cfg,
        medical_expansion_trace=medical_expansion_trace,
        apply_diversification=apply_div,
        rerank_info=rerank_info,
        original_length=original_length,
        query=query,
        top_k=top_k,
        total_start=total_start,
    )


async def retrieve_context_with_trace_async(
    query: str,
    top_k: int = 5,
    retrieval_options: dict[str, Any] | None = None,
    hyde_client: Any = None,
):
    if not query or not query.strip():
        return "", [], _empty_pipeline_trace("", top_k)
    query, original_length, cfg, total_start, vector_store = _prepare_query(
        query, retrieval_options
    )

    from src.rag.trace_models import RetrievalStep

    fetch_k = max(top_k, top_k * cfg.overfetch_multiplier)
    steps: list[RetrievalStep] = []

    query_expansion_start = time.time()
    expanded_queries, medical_expansion_trace = prepare_expanded_queries(
        query,
        enable_medical_expansion=cfg.enable_medical_expansion,
        medical_expansion_provider=cfg.medical_expansion_provider,
    )
    from src.rag.query_expansion import expand_queries_async

    expanded_queries = await expand_queries_async(
        query,
        hyde_client=hyde_client,
        enable_hyde=cfg.enable_hyde,
        hyde_max_length=cfg.hyde_max_length,
        pre_expanded_queries=expanded_queries,
    )
    query_expansion_timing_ms = int((time.time() - query_expansion_start) * 1000)

    expanded_queries, selected_hype_questions = _extend_with_hype_questions(
        vector_store,
        query,
        expanded_queries,
        enable_hype=cfg.enable_hype,
    )
    if selected_hype_questions:
        logger.debug(f"HyPE: expanded to {len(expanded_queries)} total queries")

    retrieval_start = time.time()
    from src.rag.retrieval import retrieve_candidates_with_trace_async as retrieve_fn

    results, retrieval_trace = await retrieve_fn(
        vector_store,
        query,
        fetch_k,
        cfg.search_mode,
        hyde_client=hyde_client,
        enable_hyde=cfg.enable_hyde,
        hyde_max_length=cfg.hyde_max_length,
        pre_expanded_queries=expanded_queries,
    )
    retrieval_search_timing_ms = int((time.time() - retrieval_start) * 1000)

    search_mode = cfg.search_mode
    is_hybrid = search_mode == "rrf_hybrid"

    steps.extend(
        [
            RetrievalStep(
                name="query_expansion",
                timing_ms=query_expansion_timing_ms,
                skipped=False,
                details={
                    "expanded_queries": expanded_queries,
                    "medical_expansion_terms": medical_expansion_trace,
                    "selected_hype_questions": selected_hype_questions,
                    "hyde_enabled": cfg.enable_hyde,
                    "hype_enabled": cfg.enable_hype,
                    "medical_expansion_enabled": cfg.enable_medical_expansion,
                    "medical_expansion_provider": cfg.medical_expansion_provider,
                },
            ),
            RetrievalStep(
                name="semantic_search",
                timing_ms=retrieval_search_timing_ms,
                skipped=False,
                details={"queries_count": len(expanded_queries)},
            ),
            RetrievalStep(
                name="keyword_search",
                timing_ms=0,
                skipped=search_mode == "semantic_only",
                details={"search_mode": search_mode},
            ),
            RetrievalStep(
                name="score_fusion",
                timing_ms=0,
                skipped=not is_hybrid,
                details={"search_mode": search_mode},
            ),
        ]
    )

    reranking_start = time.time()
    results, rerank_result, rerank_info, apply_div = _rerank_and_diversify(
        results,
        query,
        top_k,
        fetch_k,
        cfg,
    )
    reranking_timing_ms = int((time.time() - reranking_start) * 1000)

    steps.append(
        RetrievalStep(
            name="reranking",
            timing_ms=reranking_timing_ms,
            skipped=not apply_div and not cfg.enable_reranking,
            details={
                "mmr_lambda": cfg.mmr_lambda,
                "overfetch_multiplier": cfg.overfetch_multiplier,
                "enable_diversification": apply_div,
                "enable_reranking": cfg.enable_reranking,
                "reranking_mode": cfg.reranking_mode,
                "reranker_model": rerank_result.model_name if rerank_result else None,
                "rerank_timing_ms": rerank_result.timing_ms if rerank_result else 0,
                "rerank_score_threshold": cfg.rerank_score_threshold,
                **rerank_info,
            },
        )
    )

    return _build_pipeline_trace(
        results=results,
        retrieval_trace=retrieval_trace,
        cfg=cfg,
        medical_expansion_trace=medical_expansion_trace,
        apply_diversification=apply_div,
        rerank_info=rerank_info,
        original_length=original_length,
        query=query,
        top_k=top_k,
        total_start=total_start,
        steps=steps,
    )


def _prepare_query(
    query: str,
    retrieval_options: dict[str, Any] | None,
) -> tuple[str, int, RetrievalDiversityConfig, float, Any]:
    """Validate, truncate, config-resolve, and init shared by sync/async retrieval."""
    original_length = len(query)
    if len(query) > 4000:
        logger.warning("Query truncated from %d to 4000 chars", len(query))
        query = query[:4000]

    total_start = time.time()
    cfg = resolve_retrieval_config(retrieval_options)

    updated = _apply_query_understanding(query, retrieval_options, cfg)
    if updated:
        cfg = resolve_retrieval_config(updated)

    initialize_runtime_index()
    return query, original_length, cfg, total_start, get_vector_store()


def retrieve_context(
    query: str, top_k: int = 5, retrieval_options: dict[str, Any] | None = None
) -> tuple[str, list[ChatSource]]:
    context, sources, _ = retrieve_context_with_trace(
        query, top_k=top_k, retrieval_options=retrieval_options
    )
    return context, sources


def get_full_context() -> str:
    from src.ingestion.steps.load_reference_data import ReferenceDataLoader

    loader = ReferenceDataLoader()
    ranges = loader.load_reference_ranges()
    pdf_texts = loader.load_pdfs_text()
    return f"{ranges}\n\n{pdf_texts}"


def get_context(query: str | None = None) -> tuple[str, list[ChatSource]]:
    if query:
        return retrieve_context(query)
    return "", []
