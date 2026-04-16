#!/usr/bin/env python3
"""Runtime RAG retrieval and index initialization."""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any

from src.config import settings
from src.config.context import get_runtime_state
from src.ingestion.indexing.text_utils import ACRONYM_EXPANSIONS, tokenize_text
from src.ingestion.indexing.vector_store import (
    get_vector_store,
    get_vector_store_runtime_config,
    set_vector_store_runtime_config,
)
from src.ingestion.steps.chunk_text import (
    chunk_documents,
    get_source_chunk_configs,
    set_auto_select_strategy,
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
from src.rag.medical_expansion import MedicalExpansion, get_medical_expansion_provider
from src.rag.trace_models import ChatSource, RetrievedDocument

logger = logging.getLogger(__name__)


_VALID_SEARCH_MODES = {"rrf_hybrid", "semantic_only", "bm25_only"}


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
        generation=GenerationStage(model=settings.model_name, timing_ms=0, tokens_estimate=0),
        total_time_ms=0,
    )


@dataclass
class RuntimeRetrievalConfig:
    """Runtime retrieval configuration with defaults from settings."""

    overfetch_multiplier: int = 4
    max_chunks_per_source_page: int = 2
    max_chunks_per_source: int = 3
    mmr_lambda: float = 0.75
    enable_diversification: bool = True
    search_mode: str = "rrf_hybrid"
    enable_hyde: bool = False
    hyde_max_length: int = 200
    enable_hype: bool = False

    @classmethod
    def from_settings(cls) -> "RuntimeRetrievalConfig":
        """Create configuration from settings."""
        return cls(
            overfetch_multiplier=settings.retrieval_overfetch_multiplier,
            max_chunks_per_source_page=settings.max_chunks_per_source_page,
            max_chunks_per_source=settings.max_chunks_per_source,
            mmr_lambda=settings.mmr_lambda,
            search_mode=settings.rrf_search_mode,
            enable_hype=settings.hype_enabled,
        )


@dataclass
class RetrievalDiversityConfig:
    overfetch_multiplier: int = 4
    max_chunks_per_source_page: int = 2
    max_chunks_per_source: int = 3
    mmr_lambda: float = 0.75
    enable_diversification: bool = True
    search_mode: str = "rrf_hybrid"
    enable_hyde: bool = False
    hyde_max_length: int = 200  # Maximum length for HyDE hypothetical answers
    enable_hype: bool = False  # Use pre-stored HyPE questions at retrieval time
    enable_medical_expansion: bool = False  # Enable provider-backed medical expansion
    medical_expansion_provider: str = "noop"  # Provider name for medical expansion
    enable_reranking: bool = False  # Enable cross-encoder reranking
    rerank_top_k: int | None = None  # Candidates to fetch before reranking (None = auto)
    rerank_score_threshold: float | None = None  # Drop candidates below this rerank score
    reranking_mode: str = "cross_encoder"  # cross_encoder, mmr, or both
    enable_keyword_extraction: bool = False  # Use LLM-extracted keywords for BM25 boosting
    enable_chunk_summaries: bool = False  # Chunks have summaries prepended to content


def get_runtime_retrieval_config() -> dict[str, Any]:
    return asdict(RetrievalDiversityConfig())


def _resolve_retrieval_config(overrides: dict[str, Any] | None = None) -> RetrievalDiversityConfig:
    cfg = RetrievalDiversityConfig(
        overfetch_multiplier=settings.retrieval_overfetch_multiplier,
        max_chunks_per_source_page=settings.max_chunks_per_source_page,
        max_chunks_per_source=settings.max_chunks_per_source,
        mmr_lambda=settings.mmr_lambda,
        search_mode=settings.rrf_search_mode,
    )
    if overrides:
        for key, value in overrides.items():
            if value is None or not hasattr(cfg, key):
                continue
            setattr(cfg, key, value)
    cfg.overfetch_multiplier = max(
        1, int(cfg.overfetch_multiplier or settings.retrieval_overfetch_multiplier)
    )
    cfg.max_chunks_per_source_page = max(
        1, int(cfg.max_chunks_per_source_page or settings.max_chunks_per_source_page)
    )
    cfg.max_chunks_per_source = max(
        1, int(cfg.max_chunks_per_source or settings.max_chunks_per_source)
    )
    cfg.mmr_lambda = max(0.0, min(1.0, float(cfg.mmr_lambda or settings.mmr_lambda)))
    cfg.search_mode = str(cfg.search_mode or settings.rrf_search_mode).lower()
    if cfg.search_mode not in _VALID_SEARCH_MODES:
        cfg.search_mode = settings.rrf_search_mode
    # Validate HyDE configuration
    cfg.enable_hyde = bool(cfg.enable_hyde)
    cfg.hyde_max_length = max(50, min(500, int(cfg.hyde_max_length)))
    cfg.enable_hype = bool(cfg.enable_hype) or bool(getattr(settings, "hype_enabled", False))
    cfg.enable_medical_expansion = bool(cfg.enable_medical_expansion) or bool(
        getattr(settings, "medical_expansion_enabled", False)
    )
    cfg.medical_expansion_provider = str(
        cfg.medical_expansion_provider or getattr(settings, "medical_expansion_provider", "noop")
    ).lower()
    cfg.enable_reranking = bool(cfg.enable_reranking) or bool(
        getattr(settings, "enable_reranking", False)
    )
    if cfg.rerank_top_k is None:
        cfg.rerank_top_k = getattr(settings, "rerank_top_k", None)
    elif cfg.rerank_top_k is not None:
        cfg.rerank_top_k = max(1, int(cfg.rerank_top_k))
    if cfg.rerank_score_threshold is None:
        cfg.rerank_score_threshold = getattr(settings, "rerank_score_threshold", None)
    elif cfg.rerank_score_threshold is not None:
        cfg.rerank_score_threshold = float(cfg.rerank_score_threshold)
    cfg.reranking_mode = str(
        cfg.reranking_mode or getattr(settings, "reranking_mode", "cross_encoder")
    ).lower()
    if cfg.reranking_mode not in {"cross_encoder", "mmr", "both"}:
        cfg.reranking_mode = "cross_encoder"
    cfg.enable_keyword_extraction = bool(cfg.enable_keyword_extraction) or bool(
        getattr(settings, "enable_keyword_extraction", False)
    )
    cfg.enable_chunk_summaries = bool(cfg.enable_chunk_summaries) or bool(
        getattr(settings, "enable_chunk_summaries", False)
    )
    return cfg


def _should_apply_diversification(cfg: RetrievalDiversityConfig) -> bool:
    """Apply MMR/diversity only when enabled and requested by the reranking mode."""
    return cfg.enable_diversification and cfg.reranking_mode in {"mmr", "both"}


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in queries:
        normalized = " ".join(item.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def _expand_lexical_queries(query: str) -> list[str]:
    """Expand query using lexical normalization and acronym expansion."""
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
    return _dedupe_queries(outputs)


def _expand_medical_terms(
    query: str,
    *,
    base_queries: list[str],
    enable_medical_expansion: bool = False,
    provider_name: str = "noop",
) -> list[MedicalExpansion]:
    """Expand query with provider-backed medical terms."""
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


def _prepare_expanded_queries(
    query: str,
    *,
    enable_medical_expansion: bool = False,
    medical_expansion_provider: str = "noop",
) -> tuple[list[str], list[dict[str, str | None]]]:
    """Return lexical plus provider-backed expansion queries and trace metadata."""
    base_queries = _expand_lexical_queries(query)
    medical_expansions = _expand_medical_terms(
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


def _expand_queries(query: str, hyde_client: Any = None, enable_hyde: bool = False) -> list[str]:
    """Backward-compatible sync expansion entrypoint.

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
    return _expand_lexical_queries(query)


async def _expand_queries_async(
    query: str,
    hyde_client: Any = None,
    enable_hyde: bool = False,
    hyde_max_length: int = 200,
    enable_medical_expansion: bool = False,
    medical_expansion_provider: str = "noop",
    pre_expanded_queries: list[str] | None = None,
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

    base_queries = (
        list(pre_expanded_queries)
        if pre_expanded_queries is not None
        else _prepare_expanded_queries(
            query,
            enable_medical_expansion=enable_medical_expansion,
            medical_expansion_provider=medical_expansion_provider,
        )[0]
    )

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
        all_queries = _dedupe_queries(base_queries + hyde_queries)

        logger.debug(f"HyDE expanded query '{query[:50]}...' to {len(all_queries)} variants")
        return all_queries

    except Exception as e:
        logger.error(
            f"HyDE expansion failed for query '{query}': {e}, falling back to base expansion"
        )
        return base_queries


def _build_index_from_sources(vector_store) -> dict[str, Any]:
    build_start = time.time()
    runtime_cfg = get_vector_store_runtime_config()
    indexing_features = dict(runtime_cfg.get("indexing_features", {}) or {})
    loader = ReferenceDataLoader()
    pdf_docs = get_documents()
    markdown_docs = get_markdown_documents()
    chunked_docs = chunk_documents(pdf_docs)
    chunked_docs.extend(chunk_documents(markdown_docs))

    hype_chunk_count = 0
    if indexing_features.get("enable_hype"):
        from src.infra.llm.qwen_client import get_client
        from src.ingestion.steps.hype import generate_hype_questions_for_chunks

        hype_questions = asyncio.run(
            generate_hype_questions_for_chunks(
                chunks=chunked_docs,
                client=get_client(),
                sample_rate=float(
                    indexing_features.get("hype_sample_rate", settings.hype_sample_rate)
                ),
                max_chunks=int(indexing_features.get("hype_max_chunks", settings.hype_max_chunks)),
                questions_per_chunk=int(
                    indexing_features.get(
                        "hype_questions_per_chunk", settings.hype_questions_per_chunk
                    )
                ),
            )
        )
        hype_chunk_count = len(hype_questions)
        for doc in chunked_docs:
            if doc["id"] in hype_questions:
                doc.setdefault("metadata", {})
                doc["metadata"]["hypothetical_questions"] = hype_questions[doc["id"]]

    enriched_chunk_count = 0
    if indexing_features.get("enable_keyword_extraction") or indexing_features.get(
        "enable_chunk_summaries"
    ):
        from src.infra.llm.qwen_client import get_client
        from src.ingestion.steps.enrich_chunks import (
            apply_enrichment_to_chunks,
            enrich_chunks,
        )

        enrichment_results = asyncio.run(
            enrich_chunks(
                chunks=chunked_docs,
                client=get_client(),
                enable_keywords=bool(indexing_features.get("enable_keyword_extraction")),
                enable_summaries=bool(indexing_features.get("enable_chunk_summaries")),
                sample_rate=float(
                    indexing_features.get(
                        "keyword_extraction_sample_rate",
                        settings.keyword_extraction_sample_rate,
                    )
                ),
                max_chunks=int(
                    indexing_features.get(
                        "keyword_extraction_max_chunks",
                        settings.keyword_extraction_max_chunks,
                    )
                ),
            )
        )
        enriched_chunk_count = apply_enrichment_to_chunks(
            chunked_docs,
            enrichment_results,
            enable_keywords=bool(indexing_features.get("enable_keyword_extraction")),
            enable_summaries=bool(indexing_features.get("enable_chunk_summaries")),
        )

    ref_docs = loader.load_reference_ranges_as_docs()
    chunked_docs.extend(ref_docs)
    stats = vector_store.add_documents(chunked_docs)
    stats["build_elapsed_ms"] = int((time.time() - build_start) * 1000)
    stats["pdf_document_count"] = len(pdf_docs)
    stats["markdown_document_count"] = len(markdown_docs)
    stats["reference_document_count"] = len(ref_docs)
    stats["chunk_count"] = len(chunked_docs)
    stats["hype_chunk_count"] = hype_chunk_count
    stats["enriched_chunk_count"] = enriched_chunk_count
    logger.info(
        "Indexed document chunks "
        "(attempted=%d, inserted=%d, "
        "duplicate_id=%d, duplicate_content=%d)",
        stats['attempted'], stats['inserted'],
        stats['skipped_duplicate_id'], stats['skipped_duplicate_content'],
    )
    return stats


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
    state = get_runtime_state()
    with state._lock:
        runtime_signature = _vector_store_runtime_signature()
        if state._vector_store_initialized_signature != runtime_signature:
            state._vector_store_initialized = False

    vector_store = get_vector_store()

    if rebuild:
        vector_store.clear()
        with state._lock:
            state._vector_store_initialized = False
            state._vector_store_initialized_signature = None

    if materialize_html:
        convert_html_main(force=force_html_reconvert)

    documents = vector_store.documents
    if documents.get("contents"):
        with state._lock:
            if not state._vector_store_initialized:
                state._vector_store_initialized = True
                state._vector_store_initialized_signature = runtime_signature
                logger.info(
                    "Loaded existing vector store with %d documents",
                    len(documents["contents"]),
                )
            else:
                state._vector_store_initialized_signature = runtime_signature
        return {
            "status": "ready",
            "reused_existing_index": True,
            "vector_store_config": get_vector_store_runtime_config(),
            "index_metadata": documents.get("index_metadata", {}),
            "vector_document_count": len(documents.get("contents", [])),
            "indexing_stats": vector_store.last_indexing_stats,
        }

    build_stats = _build_index_from_sources(vector_store)
    documents = vector_store.documents
    with state._lock:
        state._vector_store_initialized = True
        state._vector_store_initialized_signature = runtime_signature
    return {
        "status": "built",
        "reused_existing_index": False,
        "vector_store_config": get_vector_store_runtime_config(),
        "index_metadata": documents.get("index_metadata", {}),
        "vector_document_count": len(documents.get("contents", [])),
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


def reset_runtime_index_state() -> None:
    """Reset runtime-owned vector store initialization state."""
    get_runtime_state().reset_vector_store_state()


def get_runtime_status() -> dict[str, Any]:
    """Return lightweight runtime/index health metadata."""
    state = get_runtime_state()
    vector_store_config = get_vector_store_runtime_config()
    status = state.get_vector_store_status()
    return {
        "vector_store": {
            "initialized": status["initialized"],
            "signature": status["signature"],
            "config": vector_store_config,
        },
        "runtime": state.snapshot(),
    }


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
    set_auto_select_strategy(ingestion.get("auto_select_chunk_strategy", False))
    indexing_features = {
        "enable_hype": bool(ingestion.get("enable_hype", settings.hype_enabled)),
        "hype_sample_rate": float(ingestion.get("hype_sample_rate", settings.hype_sample_rate)),
        "hype_max_chunks": int(ingestion.get("hype_max_chunks", settings.hype_max_chunks)),
        "hype_questions_per_chunk": int(
            ingestion.get("hype_questions_per_chunk", settings.hype_questions_per_chunk)
        ),
        "enable_keyword_extraction": bool(
            ingestion.get("enable_keyword_extraction", settings.enable_keyword_extraction)
        ),
        "enable_chunk_summaries": bool(
            ingestion.get("enable_chunk_summaries", settings.enable_chunk_summaries)
        ),
        "keyword_extraction_sample_rate": float(
            ingestion.get(
                "keyword_extraction_sample_rate", settings.keyword_extraction_sample_rate
            )
        ),
        "keyword_extraction_max_chunks": int(
            ingestion.get("keyword_extraction_max_chunks", settings.keyword_extraction_max_chunks)
        ),
    }
    vector_config = {
        "collection_name": embedding_index.get("collection_name", settings.collection_name),
        "semantic_weight": embedding_index.get("semantic_weight", 0.6),
        "keyword_weight": embedding_index.get("keyword_weight", 0.2),
        "boost_weight": embedding_index.get("boost_weight", 0.2),
        "embedding_model": embedding_index.get("embedding_model", settings.embedding_model),
        "embedding_batch_size": embedding_index.get(
            "embedding_batch_size", settings.embedding_batch_size
        ),
        "indexing_features": indexing_features,
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
            "source_chunk_configs": json.dumps(get_source_chunk_configs()),
            **indexing_features,
        },
    }
    set_vector_store_runtime_config(vector_config)
    get_runtime_state().reset_vector_store_state()
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


def _mmr_rerank(results: list[dict], top_k: int, lambda_mult: float = 0.75) -> list[dict]:
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
    mmr_lambda: float = 0.75,
    overfetch_multiplier: int = 2,
    max_chunks_per_source_page: int = 2,
    max_chunks_per_source: int = 3,
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
    cfg: RetrievalDiversityConfig,
):
    """Apply cross-encoder reranking with candidate-window and score-threshold controls."""
    if not (cfg.enable_reranking and cfg.reranking_mode in {"cross_encoder", "both"}):
        return results, None, {}

    from src.rag.reranker import get_reranker

    reranker = get_reranker()
    rerank_candidates_count = cfg.rerank_top_k or fetch_k
    candidates = results[:rerank_candidates_count] if rerank_candidates_count < len(results) else results
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


def retrieve_context(
    query: str, top_k: int = 5, retrieval_options: dict[str, Any] | None = None
) -> tuple[str, list[ChatSource]]:
    if not query or not query.strip():
        return "", []
    if len(query) > 4000:
        logger.warning("Query truncated from %d to 4000 chars", len(query))
        query = query[:4000]
    initialize_runtime_index()
    cfg = _resolve_retrieval_config(retrieval_options)

    vector_store = get_vector_store()
    fetch_k = max(top_k, top_k * cfg.overfetch_multiplier)
    expanded_queries, _ = _prepare_expanded_queries(
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
    results = _retrieve_candidates(
        vector_store,
        query,
        fetch_k,
        cfg.search_mode,
        pre_expanded_queries=expanded_queries,
    )
    results, _, _ = _apply_reranking(query, results, fetch_k=fetch_k, cfg=cfg)

    apply_diversification = _should_apply_diversification(cfg)
    results = _diversify_results(
        results,
        top_k=top_k,
        mmr_lambda=cfg.mmr_lambda,
        overfetch_multiplier=cfg.overfetch_multiplier,
        max_chunks_per_source_page=cfg.max_chunks_per_source_page,
        max_chunks_per_source=cfg.max_chunks_per_source,
        enable_diversification=apply_diversification,
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
    if not query or not query.strip():
        return "", [], _empty_pipeline_trace("", top_k)
    original_query = query
    original_length = len(query)
    if len(query) > 4000:
        logger.warning("Query truncated from %d to 4000 chars", len(query))
        query = query[:4000]
    from src.rag.trace_models import (
        ContextStage,
        GenerationStage,
        PipelineTrace,
        RetrievalStage,
    )

    total_start = time.time()
    cfg = _resolve_retrieval_config(retrieval_options)

    initialize_runtime_index()
    vector_store = get_vector_store()

    fetch_k = max(top_k, top_k * cfg.overfetch_multiplier)
    expanded_queries, medical_expansion_trace = _prepare_expanded_queries(
        query,
        enable_medical_expansion=cfg.enable_medical_expansion,
        medical_expansion_provider=cfg.medical_expansion_provider,
    )
    expanded_queries, selected_hype_questions = _extend_with_hype_questions(
        vector_store,
        query,
        expanded_queries,
        enable_hype=cfg.enable_hype,
    )
    results, retrieval_trace = _retrieve_candidates_with_trace(
        vector_store,
        query,
        fetch_k,
        cfg.search_mode,
        pre_expanded_queries=expanded_queries,
    )

    results, rerank_result, rerank_info = _apply_reranking(query, results, fetch_k=fetch_k, cfg=cfg)

    apply_diversification = _should_apply_diversification(cfg)
    results = _diversify_results(
        results,
        top_k=top_k,
        mmr_lambda=cfg.mmr_lambda,
        overfetch_multiplier=cfg.overfetch_multiplier,
        max_chunks_per_source_page=cfg.max_chunks_per_source_page,
        max_chunks_per_source=cfg.max_chunks_per_source,
        enable_diversification=apply_diversification,
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
    if not query or not query.strip():
        from src.rag.trace_models import PipelineTrace as _PT
        return "", [], _PT()
    original_query = query
    original_length = len(query)
    if len(query) > 4000:
        logger.warning("Query truncated from %d to 4000 chars", len(query))
        query = query[:4000]
    from src.rag.trace_models import (
        ContextStage,
        GenerationStage,
        PipelineTrace,
        RetrievalStage,
        RetrievalStep,
    )

    total_start = time.time()
    cfg = _resolve_retrieval_config(retrieval_options)

    initialize_runtime_index()
    vector_store = get_vector_store()

    fetch_k = max(top_k, top_k * cfg.overfetch_multiplier)

    steps: list[RetrievalStep] = []

    # Step 1: Query Expansion
    query_expansion_start = time.time()
    expanded_queries, medical_expansion_trace = _prepare_expanded_queries(
        query,
        enable_medical_expansion=cfg.enable_medical_expansion,
        medical_expansion_provider=cfg.medical_expansion_provider,
    )
    expanded_queries = await _expand_queries_async(
        query,
        hyde_client=hyde_client,
        enable_hyde=cfg.enable_hyde,
        hyde_max_length=cfg.hyde_max_length,
        enable_medical_expansion=cfg.enable_medical_expansion,
        medical_expansion_provider=cfg.medical_expansion_provider,
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
                "medical_expansion_terms": medical_expansion_trace,
                "selected_hype_questions": selected_hype_questions,
                "hyde_enabled": cfg.enable_hyde,
                "hype_enabled": cfg.enable_hype,
                "medical_expansion_enabled": cfg.enable_medical_expansion,
                "medical_expansion_provider": cfg.medical_expansion_provider,
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
    results, rerank_result, rerank_info = _apply_reranking(query, results, fetch_k=fetch_k, cfg=cfg)

    apply_diversification = _should_apply_diversification(cfg)
    results = _diversify_results(
        results,
        top_k=top_k,
        mmr_lambda=cfg.mmr_lambda,
        overfetch_multiplier=cfg.overfetch_multiplier,
        max_chunks_per_source_page=cfg.max_chunks_per_source_page,
        max_chunks_per_source=cfg.max_chunks_per_source,
        enable_diversification=apply_diversification,
    )
    reranking_timing_ms = int((time.time() - reranking_start) * 1000)

    steps.append(
        RetrievalStep(
            name="reranking",
            timing_ms=reranking_timing_ms,
            skipped=not apply_diversification and not cfg.enable_reranking,
            details={
                "mmr_lambda": cfg.mmr_lambda,
                "overfetch_multiplier": cfg.overfetch_multiplier,
                "enable_diversification": apply_diversification,
                "enable_reranking": cfg.enable_reranking,
                "reranking_mode": cfg.reranking_mode,
                "reranker_model": rerank_result.model_name if rerank_result else None,
                "rerank_timing_ms": rerank_result.timing_ms if rerank_result else 0,
                "rerank_score_threshold": cfg.rerank_score_threshold,
                **rerank_info,
            },
        )
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


def _retrieve_candidates(
    vector_store,
    query: str,
    top_k: int,
    search_mode: str,
    *,
    pre_expanded_queries: list[str] | None = None,
) -> list[dict]:
    expanded_queries = (
        pre_expanded_queries if pre_expanded_queries is not None else _expand_queries(query)
    )
    result_sets = [
        vector_store.similarity_search(expanded_query, top_k=top_k, search_mode=search_mode)
        for expanded_query in expanded_queries
    ]
    return _merge_result_sets(result_sets, top_k=top_k)


def _retrieve_candidates_with_trace(
    vector_store,
    query: str,
    top_k: int,
    search_mode: str,
    *,
    pre_expanded_queries: list[str] | None = None,
) -> tuple[list[dict], dict]:
    expanded_queries = (
        pre_expanded_queries if pre_expanded_queries is not None else _expand_queries(query)
    )
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
    merged_trace["result_count"] = len(merged_results)
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
    merged_trace["result_count"] = len(merged_results)
    return merged_results, merged_trace
