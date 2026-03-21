#!/usr/bin/env python3
"""Runtime RAG retrieval and index initialization."""

import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any

from src.config import settings
from src.ingestion.indexing.text_utils import ACRONYM_EXPANSIONS, tokenize_text
from src.ingestion.indexing.vector_store import (
    get_vector_store,
    get_vector_store_runtime_config,
    set_vector_store_runtime_config,
)
from src.ingestion.steps.chunk_text import (
    chunk_documents,
    get_source_chunk_configs,
    set_source_chunk_configs,
    set_structured_chunking_enabled,
)
from src.ingestion.steps.convert_html import main as convert_html_main
from src.ingestion.steps.convert_html import (
    set_html_extractor_mode,
    set_html_extractor_strategy,
    set_page_classification_enabled,
)
from src.ingestion.steps.load_markdown import (
    get_markdown_documents,
    set_index_only_classified_pages,
)
from src.ingestion.steps.load_pdfs import (
    get_documents,
    set_pdf_extractor_strategy,
    set_pdf_table_extractor,
)
from src.ingestion.steps.load_reference_data import ReferenceDataLoader
from src.rag.formatting import build_context_and_sources
from src.rag.trace_models import ChatSource

logger = logging.getLogger(__name__)


_vector_store_initialized = False
_vector_store_initialized_signature: str | None = None
_RETRIEVAL_OVERFETCH_MULTIPLIER = 4
_MAX_CHUNKS_PER_SOURCE_PAGE = 2
_MAX_CHUNKS_PER_SOURCE = 3
_MMR_LAMBDA = 0.75
_RRF_SEARCH_MODE = "rrf_hybrid"
_VALID_SEARCH_MODES = {"rrf_hybrid", "semantic_only", "bm25_only"}


@dataclass
class RetrievalDiversityConfig:
    overfetch_multiplier: int = _RETRIEVAL_OVERFETCH_MULTIPLIER
    max_chunks_per_source_page: int = _MAX_CHUNKS_PER_SOURCE_PAGE
    max_chunks_per_source: int = _MAX_CHUNKS_PER_SOURCE
    mmr_lambda: float = _MMR_LAMBDA
    enable_diversification: bool = True
    search_mode: str = _RRF_SEARCH_MODE
    enable_hyde: bool = False
    hyde_max_length: int = 200  # Maximum length for HyDE hypothetical answers


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
    cfg.search_mode = str(cfg.search_mode or _RRF_SEARCH_MODE).lower()
    if cfg.search_mode not in _VALID_SEARCH_MODES:
        cfg.search_mode = _RRF_SEARCH_MODE
    # Validate HyDE configuration
    cfg.enable_hyde = bool(cfg.enable_hyde)
    cfg.hyde_max_length = max(50, min(500, int(cfg.hyde_max_length)))
    return cfg


def _expand_queries(query: str, hyde_client: Any = None, enable_hyde: bool = False) -> list[str]:
    """Expand query using multiple techniques: tokenization, acronym expansion, and optionally HyDE.

    Args:
        query: The user's original query
        hyde_client: Optional LLM client for HyDE expansion (not used in sync version)
        enable_hyde: Whether to enable HyDE expansion (not effective in sync version)

    Returns:
        List of expanded query variants

    Note:
        For full HyDE functionality, use _expand_queries_async instead.
        This synchronous version does not perform LLM-based HyDE expansion.
    """
    query = str(query or "").strip()
    if not query:
        return []
    outputs = [query]
    lowered = query.lower()
    outputs.append(" ".join(tokenize_text(query)))
    expansion_terms: list[str] = []
    for token in tokenize_text(query):
        expansion_terms.extend(ACRONYM_EXPANSIONS.get(token, []))
    if expansion_terms:
        outputs.append(f"{query} {' '.join(expansion_terms)}")
    keyword_focus = " ".join(dict.fromkeys(tokenize_text(lowered)))
    if keyword_focus:
        outputs.append(keyword_focus)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in outputs:
        normalized = " ".join(item.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


async def _expand_queries_async(
    query: str,
    hyde_client: Any = None,
    enable_hyde: bool = False,
    hyde_max_length: int = 200,
) -> list[str]:
    """Async version of query expansion with HyDE support.

    Args:
        query: The user's original query
        hyde_client: Optional LLM client for HyDE expansion
        enable_hyde: Whether to enable HyDE expansion
        hyde_max_length: Maximum length for HyDE hypothetical answers

    Returns:
        List of expanded query variants (original + HyDE if enabled)
    """
    from src.rag.hyde import expand_query_with_hyde_async

    # Get base query expansions (tokenization, acronyms)
    base_queries = _expand_queries(query)

    # If HyDE is disabled, return base expansions only
    if not enable_hyde or not hyde_client:
        return base_queries

    # Generate HyDE expansion
    try:
        hyde_queries = await expand_query_with_hyde_async(
            query=query,
            client=hyde_client,
            enable_hyde=True,
            max_length=hyde_max_length,
        )

        # Combine base queries with HyDE queries, removing duplicates
        all_queries = base_queries + hyde_queries
        seen: set[str] = set()
        deduped: list[str] = []
        for q in all_queries:
            normalized = " ".join(q.split())
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)

        logger.debug(f"HyDE expanded query '{query[:50]}...' to {len(deduped)} variants")
        return deduped

    except Exception as e:
        logger.error(
            f"HyDE expansion failed for query '{query}': {e}, falling back to base expansion"
        )
        return base_queries


def _build_index_from_sources(vector_store) -> dict[str, Any]:
    build_start = time.time()
    loader = ReferenceDataLoader()
    pdf_docs = get_documents()
    markdown_docs = get_markdown_documents()
    chunked_docs = chunk_documents(pdf_docs)
    chunked_docs.extend(chunk_documents(markdown_docs))
    ref_docs = loader.load_reference_ranges_as_docs()
    chunked_docs.extend(ref_docs)
    stats = vector_store.add_documents(chunked_docs)
    stats["build_elapsed_ms"] = int((time.time() - build_start) * 1000)
    stats["pdf_document_count"] = len(pdf_docs)
    stats["markdown_document_count"] = len(markdown_docs)
    stats["reference_document_count"] = len(ref_docs)
    stats["chunk_count"] = len(chunked_docs)
    print(
        "Indexed document chunks "
        f"(attempted={stats['attempted']}, inserted={stats['inserted']}, "
        f"duplicate_id={stats['skipped_duplicate_id']}, duplicate_content={stats['skipped_duplicate_content']})"
    )
    return stats  # type: ignore[no-any-return]


def _vector_store_runtime_signature() -> str:
    return json.dumps(
        get_vector_store_runtime_config(),
        sort_keys=True,
        separators=(",", ":"),
    )


def initialize_vector_store(
    rebuild: bool = False,
    *,
    materialize_html: bool = False,
    force_html_reconvert: bool = False,
):
    global _vector_store_initialized, _vector_store_initialized_signature

    runtime_signature = _vector_store_runtime_signature()
    if _vector_store_initialized_signature != runtime_signature:
        _vector_store_initialized = False

    vector_store = get_vector_store()

    if rebuild:
        vector_store.clear()
        _vector_store_initialized = False
        _vector_store_initialized_signature = None

    if materialize_html:
        convert_html_main(force=force_html_reconvert)

    if _vector_store_initialized and vector_store.documents.get("contents"):
        _vector_store_initialized_signature = runtime_signature
        return {
            "status": "ready",
            "reused_existing_index": True,
            "vector_store_config": get_vector_store_runtime_config(),
            "index_metadata": vector_store.documents.get("index_metadata", {}),
            "vector_document_count": len(vector_store.documents.get("contents", [])),
            "indexing_stats": vector_store.last_indexing_stats,
        }

    if vector_store.documents.get("contents"):
        _vector_store_initialized = True
        _vector_store_initialized_signature = runtime_signature
        logger.info(
            "Loaded existing vector store with %d documents",
            len(vector_store.documents["contents"]),
        )
        return {
            "status": "ready",
            "reused_existing_index": True,
            "vector_store_config": get_vector_store_runtime_config(),
            "index_metadata": vector_store.documents.get("index_metadata", {}),
            "vector_document_count": len(vector_store.documents.get("contents", [])),
            "indexing_stats": vector_store.last_indexing_stats,
        }

    build_stats = _build_index_from_sources(vector_store)
    _vector_store_initialized = True
    _vector_store_initialized_signature = runtime_signature
    return {
        "status": "built",
        "reused_existing_index": False,
        "vector_store_config": get_vector_store_runtime_config(),
        "index_metadata": vector_store.documents.get("index_metadata", {}),
        "vector_document_count": len(vector_store.documents.get("contents", [])),
        "indexing_stats": build_stats,
    }


def initialize_runtime_index(
    rebuild: bool = False,
    *,
    materialize_html: bool = False,
    force_html_reconvert: bool = False,
):
    return initialize_vector_store(
        rebuild=rebuild,
        materialize_html=materialize_html,
        force_html_reconvert=force_html_reconvert,
    )


def configure_runtime_for_experiment(experiment: dict[str, Any] | None = None) -> dict[str, Any]:
    if not experiment:
        return {}

    ingestion = dict(experiment.get("ingestion", {}))
    embedding_index = dict(experiment.get("embedding_index", {}))
    set_page_classification_enabled(ingestion.get("page_classification_enabled", True))
    set_index_only_classified_pages(ingestion.get("index_only_classified_pages", True))
    set_html_extractor_mode(ingestion.get("html_extractor_mode", "auto"))
    set_html_extractor_strategy(ingestion.get("html_extractor_strategy", "trafilatura_bs"))
    set_pdf_extractor_strategy(ingestion.get("pdf_extractor_strategy", "pypdf_pdfplumber"))
    set_pdf_table_extractor(ingestion.get("pdf_table_extractor", "heuristic"))
    set_structured_chunking_enabled(ingestion.get("structured_chunking_enabled", True))
    set_source_chunk_configs(ingestion.get("source_chunk_configs"))
    vector_config = {
        "collection_name": embedding_index.get("collection_name", settings.collection_name),
        "semantic_weight": embedding_index.get("semantic_weight", 0.6),
        "keyword_weight": embedding_index.get("keyword_weight", 0.2),
        "boost_weight": embedding_index.get("boost_weight", 0.2),
        "embedding_model": embedding_index.get("embedding_model", settings.embedding_model),
        "embedding_batch_size": embedding_index.get(
            "embedding_batch_size", settings.embedding_batch_size
        ),
        "index_metadata": {
            "experiment_name": experiment.get("metadata", {}).get("name"),
            "experiment_file": experiment.get("experiment_file"),
            "experiment_config_hash": experiment.get("experiment_config_hash"),
            "index_config_hash": experiment.get("index_config_hash"),
            "collection_name": embedding_index.get("collection_name", settings.collection_name),
            "embedding_model": embedding_index.get("embedding_model", settings.embedding_model),
            "embedding_batch_size": embedding_index.get(
                "embedding_batch_size", settings.embedding_batch_size
            ),
            "semantic_weight": embedding_index.get("semantic_weight", 0.6),
            "keyword_weight": embedding_index.get("keyword_weight", 0.2),
            "boost_weight": embedding_index.get("boost_weight", 0.2),
            "page_classification_enabled": ingestion.get("page_classification_enabled", True),
            "index_only_classified_pages": ingestion.get("index_only_classified_pages", True),
            "html_extractor_mode": ingestion.get("html_extractor_mode", "auto"),
            "html_extractor_strategy": ingestion.get("html_extractor_strategy", "trafilatura_bs"),
            "pdf_extractor_strategy": ingestion.get("pdf_extractor_strategy", "pypdf_pdfplumber"),
            "pdf_table_extractor": ingestion.get("pdf_table_extractor", "heuristic"),
            "structured_chunking_enabled": ingestion.get("structured_chunking_enabled", True),
            "source_chunk_configs": get_source_chunk_configs(),
        },
    }
    set_vector_store_runtime_config(vector_config)
    return {
        "ingestion": ingestion,
        "embedding_index": embedding_index,
        "vector_store": vector_config,
    }


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


def retrieve_context(
    query: str, top_k: int = 5, retrieval_options: dict[str, Any] | None = None
) -> tuple[str, list[ChatSource]]:
    initialize_runtime_index()
    cfg = _resolve_retrieval_config(retrieval_options)

    vector_store = get_vector_store()
    fetch_k = max(top_k, top_k * cfg.overfetch_multiplier)
    results = _retrieve_candidates(vector_store, query, fetch_k, cfg.search_mode)
    results = _diversify_results(
        results,
        top_k=top_k,
        mmr_lambda=cfg.mmr_lambda,
        overfetch_multiplier=cfg.overfetch_multiplier,
        max_chunks_per_source_page=cfg.max_chunks_per_source_page,
        max_chunks_per_source=cfg.max_chunks_per_source,
        enable_diversification=cfg.enable_diversification,
    )

    context, _, chat_sources = build_context_and_sources(results)
    return context, chat_sources


def retrieve_context_with_trace(
    query: str, top_k: int = 5, retrieval_options: dict[str, Any] | None = None
):
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
    results, retrieval_trace = _retrieve_candidates_with_trace(
        vector_store, query, fetch_k, cfg.search_mode
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

    retrieval_timing_ms = retrieval_trace.get("timing_ms", 0)
    retrieval_stage = RetrievalStage(
        query=query,
        top_k=top_k,
        documents=retrieved_docs,
        score_weights={
            **retrieval_trace.get("score_weights", {}),
            "embedding_model": retrieval_trace.get("embedding_model"),
            "query_embedding_timing_ms": retrieval_trace.get("query_embedding_timing_ms", 0),
            "search_mode": cfg.search_mode,
            "expanded_queries": retrieval_trace.get("expanded_queries", []),
            "enable_diversification": cfg.enable_diversification,
            "mmr_lambda": cfg.mmr_lambda,
            "overfetch_multiplier": cfg.overfetch_multiplier,
            "max_chunks_per_source_page": cfg.max_chunks_per_source_page,
            "max_chunks_per_source": cfg.max_chunks_per_source,
        },
        timing_ms=retrieval_timing_ms,
    )

    context, source_labels, chat_sources = build_context_and_sources(results)
    context_stage = ContextStage(
        total_chunks=len(results),
        total_chars=len(context),
        sources=source_labels,
        preview=context[:200] + "..." if len(context) > 200 else context,
    )

    generation_stage = GenerationStage(model=settings.model_name, timing_ms=0, tokens_estimate=None)

    total_time_ms = int((time.time() - total_start) * 1000)
    pipeline_trace = PipelineTrace(
        retrieval=retrieval_stage,
        context=context_stage,
        generation=generation_stage,
        total_time_ms=total_time_ms,
    )

    return context, chat_sources, pipeline_trace


async def retrieve_context_with_trace_async(
    query: str,
    top_k: int = 5,
    retrieval_options: dict[str, Any] | None = None,
    hyde_client: Any = None,
):
    """
    Async version of retrieve_context_with_trace with HyDE support.

    Retrieve context with detailed pipeline trace information, optionally
    using HyDE query expansion for improved retrieval quality.

    Args:
        query: The user's query
        top_k: Number of documents to retrieve
        retrieval_options: Optional retrieval configuration overrides
        hyde_client: Optional LLM client for HyDE expansion

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
        RetrievalStep,
        RetrievedDocument,
    )

    total_start = time.time()
    cfg = _resolve_retrieval_config(retrieval_options)

    initialize_runtime_index()
    vector_store = get_vector_store()

    fetch_k = max(top_k, top_k * cfg.overfetch_multiplier)

    steps: list[RetrievalStep] = []

    # Step 1: Query Expansion
    query_expansion_start = time.time()
    expanded_queries = await _expand_queries_async(
        query,
        hyde_client=hyde_client,
        enable_hyde=cfg.enable_hyde,
        hyde_max_length=cfg.hyde_max_length,
    )
    query_expansion_timing_ms = int((time.time() - query_expansion_start) * 1000)

    # Use async retrieval with HyDE support (pass pre-expanded queries to avoid double expansion)
    retrieval_start = time.time()
    results, retrieval_trace = await _retrieve_candidates_with_trace_async(
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

    # Build steps based on config
    search_mode = cfg.search_mode
    is_hybrid = search_mode == "rrf_hybrid"

    steps.append(
        RetrievalStep(
            name="query_expansion",
            timing_ms=query_expansion_timing_ms,
            skipped=False,
            details={
                "expanded_queries": expanded_queries,
                "hyde_enabled": cfg.enable_hyde,
            },
        )
    )

    steps.append(
        RetrievalStep(
            name="semantic_search",
            timing_ms=retrieval_search_timing_ms,
            skipped=False,
            details={"queries_count": len(expanded_queries)},
        )
    )

    steps.append(
        RetrievalStep(
            name="keyword_search",
            timing_ms=0,
            skipped=search_mode == "semantic_only",
            details={"search_mode": search_mode},
        )
    )

    steps.append(
        RetrievalStep(
            name="score_fusion",
            timing_ms=0,
            skipped=not is_hybrid,
            details={"search_mode": search_mode},
        )
    )

    # Step 3: Reranking/Diversification
    reranking_start = time.time()
    results = _diversify_results(
        results,
        top_k=top_k,
        mmr_lambda=cfg.mmr_lambda,
        overfetch_multiplier=cfg.overfetch_multiplier,
        max_chunks_per_source_page=cfg.max_chunks_per_source_page,
        max_chunks_per_source=cfg.max_chunks_per_source,
        enable_diversification=cfg.enable_diversification,
    )
    reranking_timing_ms = int((time.time() - reranking_start) * 1000)

    steps.append(
        RetrievalStep(
            name="reranking",
            timing_ms=reranking_timing_ms,
            skipped=not cfg.enable_diversification,
            details={
                "mmr_lambda": cfg.mmr_lambda,
                "overfetch_multiplier": cfg.overfetch_multiplier,
            },
        )
    )

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

    retrieval_timing_ms = retrieval_trace.get("timing_ms", 0)
    retrieval_stage = RetrievalStage(
        query=query,
        top_k=top_k,
        documents=retrieved_docs,
        score_weights={
            **retrieval_trace.get("score_weights", {}),
            "embedding_model": retrieval_trace.get("embedding_model"),
            "query_embedding_timing_ms": retrieval_trace.get("query_embedding_timing_ms", 0),
            "search_mode": cfg.search_mode,
            "expanded_queries": retrieval_trace.get("expanded_queries", []),
            "hyde_enabled": retrieval_trace.get("hyde_enabled", False),
            "enable_diversification": cfg.enable_diversification,
            "mmr_lambda": cfg.mmr_lambda,
            "overfetch_multiplier": cfg.overfetch_multiplier,
            "max_chunks_per_source_page": cfg.max_chunks_per_source_page,
            "max_chunks_per_source": cfg.max_chunks_per_source,
        },
        timing_ms=retrieval_timing_ms,
        steps=steps,
    )

    context, source_labels, chat_sources = build_context_and_sources(results)
    context_stage = ContextStage(
        total_chunks=len(results),
        total_chars=len(context),
        sources=source_labels,
        preview=context[:200] + "..." if len(context) > 200 else context,
    )

    generation_stage = GenerationStage(model=settings.model_name, timing_ms=0, tokens_estimate=None)

    total_time_ms = int((time.time() - total_start) * 1000)
    pipeline_trace = PipelineTrace(
        retrieval=retrieval_stage,
        context=context_stage,
        generation=generation_stage,
        total_time_ms=total_time_ms,
    )

    return context, chat_sources, pipeline_trace


def get_full_context() -> str:
    loader = ReferenceDataLoader()
    ranges = loader.load_reference_ranges()
    pdf_texts = loader.load_pdfs_text()
    return f"{ranges}\n\n{pdf_texts}"


def get_context(query: str | None = None) -> tuple[str, list[ChatSource]]:
    if query:
        return retrieve_context(query)
    return "", []


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
        row.setdefault("rank", rank)
    return ranked[:top_k]


def _merge_traced_result_sets(result_sets: list[list[dict]], top_k: int) -> list[dict]:
    merged = _merge_result_sets(result_sets, top_k=top_k)
    for rank, row in enumerate(merged, start=1):
        row["rank"] = rank
    return merged


def _retrieve_candidates(vector_store, query: str, top_k: int, search_mode: str) -> list[dict]:
    expanded_queries = _expand_queries(query)
    result_sets = [
        vector_store.similarity_search(expanded_query, top_k=top_k, search_mode=search_mode)
        for expanded_query in expanded_queries
    ]
    return _merge_result_sets(result_sets, top_k=top_k)


def _retrieve_candidates_with_trace(
    vector_store, query: str, top_k: int, search_mode: str
) -> tuple[list[dict], dict]:
    expanded_queries = _expand_queries(query)
    result_sets: list[list[dict]] = []
    traces: list[dict] = []
    for expanded_query in expanded_queries:
        results, trace = vector_store.similarity_search_with_trace(
            expanded_query, top_k=top_k, search_mode=search_mode
        )
        result_sets.append(results)
        traces.append(trace)
    merged_results = _merge_traced_result_sets(result_sets, top_k=top_k)
    merged_trace = traces[0] if traces else {}
    merged_trace["expanded_queries"] = expanded_queries
    merged_trace["candidate_traces"] = traces
    return merged_results, merged_trace


async def _retrieve_candidates_with_trace_async(
    vector_store,
    query: str,
    top_k: int,
    search_mode: str,
    hyde_client: Any = None,
    enable_hyde: bool = False,
    hyde_max_length: int = 200,
    pre_expanded_queries: list[str] | None = None,
) -> tuple[list[dict], dict]:
    """Async version of _retrieve_candidates_with_trace with HyDE support.

    Args:
        pre_expanded_queries: If provided, skip query expansion and use these queries directly.
    """
    if pre_expanded_queries is None:
        expanded_queries = await _expand_queries_async(
            query,
            hyde_client=hyde_client,
            enable_hyde=enable_hyde,
            hyde_max_length=hyde_max_length,
        )
    else:
        expanded_queries = pre_expanded_queries
    result_sets: list[list[dict]] = []
    traces: list[dict] = []
    for expanded_query in expanded_queries:
        results, trace = vector_store.similarity_search_with_trace(
            expanded_query, top_k=top_k, search_mode=search_mode
        )
        result_sets.append(results)
        traces.append(trace)
    merged_results = _merge_traced_result_sets(result_sets, top_k=top_k)
    merged_trace = traces[0] if traces else {}
    merged_trace["expanded_queries"] = expanded_queries
    merged_trace["candidate_traces"] = traces
    merged_trace["hyde_enabled"] = enable_hyde
    return merged_results, merged_trace
