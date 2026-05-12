"""RAG retrieval configuration and resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.config import settings

_VALID_SEARCH_MODES = {"rrf_hybrid", "semantic_only", "bm25_only"}


@dataclass
class RetrievalDiversityConfig:
    overfetch_multiplier: int = 4
    max_chunks_per_source_page: int = 2
    max_chunks_per_source: int = 3
    mmr_lambda: float = 0.75
    enable_diversification: bool = True
    search_mode: str = "rrf_hybrid"
    top_k: int = 5
    enable_hyde: bool = False
    hyde_max_length: int = 200
    enable_hype: bool = False
    enable_medical_expansion: bool = False
    medical_expansion_provider: str = "noop"
    enable_reranking: bool = False
    rerank_top_k: int | None = None
    rerank_score_threshold: float | None = None
    reranking_mode: str = "cross_encoder"
    enable_keyword_extraction: bool = False
    enable_chunk_summaries: bool = False
    enable_query_understanding: bool = False


def resolve_retrieval_config(
    overrides: dict[str, Any] | None = None,
) -> RetrievalDiversityConfig:
    cfg = RetrievalDiversityConfig(
        overfetch_multiplier=settings.retrieval.retrieval_overfetch_multiplier,
        max_chunks_per_source_page=settings.retrieval.max_chunks_per_source_page,
        max_chunks_per_source=settings.retrieval.max_chunks_per_source,
        mmr_lambda=settings.retrieval.mmr_lambda,
        search_mode=settings.retrieval.rrf_search_mode,
    )
    if overrides:
        for key, value in overrides.items():
            if value is None or not hasattr(cfg, key):
                continue
            setattr(cfg, key, value)
    cfg.overfetch_multiplier = max(
        1, int(cfg.overfetch_multiplier or settings.retrieval.retrieval_overfetch_multiplier)
    )
    cfg.max_chunks_per_source_page = max(
        1, int(cfg.max_chunks_per_source_page or settings.retrieval.max_chunks_per_source_page)
    )
    cfg.max_chunks_per_source = max(
        1, int(cfg.max_chunks_per_source or settings.retrieval.max_chunks_per_source)
    )
    cfg.mmr_lambda = max(0.0, min(1.0, float(cfg.mmr_lambda or settings.retrieval.mmr_lambda)))
    cfg.search_mode = str(cfg.search_mode or settings.retrieval.rrf_search_mode).lower()
    if cfg.search_mode not in _VALID_SEARCH_MODES:
        cfg.search_mode = settings.retrieval.rrf_search_mode
    cfg.enable_hyde = bool(cfg.enable_hyde)
    cfg.hyde_max_length = max(50, min(500, int(cfg.hyde_max_length)))
    cfg.enable_hype = bool(cfg.enable_hype) or bool(settings.hyde.hype_enabled)
    cfg.enable_medical_expansion = bool(cfg.enable_medical_expansion) or bool(
        settings.retrieval.medical_expansion_enabled
    )
    cfg.medical_expansion_provider = str(
        cfg.medical_expansion_provider or settings.retrieval.medical_expansion_provider
    ).lower()
    cfg.enable_reranking = bool(cfg.enable_reranking) or bool(settings.retrieval.enable_reranking)
    if cfg.rerank_top_k is None:
        cfg.rerank_top_k = settings.retrieval.rerank_top_k
    else:
        cfg.rerank_top_k = max(1, int(cfg.rerank_top_k))
    if cfg.rerank_score_threshold is None:
        cfg.rerank_score_threshold = settings.retrieval.rerank_score_threshold
    else:
        cfg.rerank_score_threshold = float(cfg.rerank_score_threshold)
    cfg.reranking_mode = str(cfg.reranking_mode or settings.retrieval.reranking_mode).lower()
    if cfg.reranking_mode not in {"cross_encoder", "mmr", "both"}:
        cfg.reranking_mode = "cross_encoder"
    cfg.enable_keyword_extraction = bool(cfg.enable_keyword_extraction) or bool(
        settings.enrichment.enable_keyword_extraction
    )
    cfg.enable_chunk_summaries = bool(cfg.enable_chunk_summaries) or bool(
        settings.enrichment.enable_chunk_summaries
    )
    cfg.enable_query_understanding = bool(cfg.enable_query_understanding) or bool(
        getattr(settings, "enable_query_understanding", False)
    )
    return cfg


def should_apply_diversification(cfg: RetrievalDiversityConfig) -> bool:
    return cfg.enable_diversification and cfg.reranking_mode in {"mmr", "both"}


def get_runtime_retrieval_config() -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(resolve_retrieval_config())
