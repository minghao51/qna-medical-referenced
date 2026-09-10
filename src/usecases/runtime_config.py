"""Read-only runtime configuration view for API consumers.

Usecase facade (roadmap P3.3): the config route no longer imports
``ingestion.steps.*`` directly. The view is assembled from the
``RuntimeState`` overlay (``config/``), static settings, and the
runtime retrieval config exposed by ``rag``.
"""

from __future__ import annotations

from typing import Any

from src.config import settings
from src.config.context import get_runtime_state
from src.rag import get_runtime_retrieval_config


def get_runtime_config_view() -> dict[str, Any]:
    """Return a read-only snapshot of the active runtime configuration."""
    state = get_runtime_state()
    retrieval_cfg = get_runtime_retrieval_config()

    return {
        "retrieval": {
            "search_mode": retrieval_cfg["search_mode"],
            "enable_diversification": retrieval_cfg["enable_diversification"],
            "mmr_lambda": retrieval_cfg["mmr_lambda"],
            "overfetch_multiplier": retrieval_cfg["overfetch_multiplier"],
            "max_chunks_per_source_page": retrieval_cfg["max_chunks_per_source_page"],
            "max_chunks_per_source": retrieval_cfg["max_chunks_per_source"],
            "top_k": retrieval_cfg.get("top_k", 5),
            "enable_hyde": retrieval_cfg["enable_hyde"],
            "hyde_max_length": retrieval_cfg["hyde_max_length"],
            "enable_hype": retrieval_cfg["enable_hype"],
            "enable_reranking": retrieval_cfg["enable_reranking"],
            "reranking_mode": retrieval_cfg["reranking_mode"],
            "enable_medical_expansion": retrieval_cfg["enable_medical_expansion"],
            "medical_expansion_provider": retrieval_cfg["medical_expansion_provider"],
            "enable_query_understanding": retrieval_cfg["enable_query_understanding"],
        },
        "ingestion": {
            "structured_chunking_enabled": bool(state.structured_chunking_enabled),
            "page_classification_enabled": bool(state.page_classification_enabled),
            "index_only_classified_pages": bool(state.index_only_classified_pages),
            "html_extractor_strategy": str(state.html_extractor_strategy),
            "html_extractor_mode": str(state.html_extractor_mode),
            "pdf_extractor_strategy": str(state.pdf_extractor_strategy),
            "pdf_table_extractor": str(state.pdf_table_extractor),
        },
        "enrichment": {
            "enable_keyword_extraction": retrieval_cfg.get("enable_keyword_extraction", False),
            "enable_chunk_summaries": retrieval_cfg.get("enable_chunk_summaries", False),
        },
        "llm": {
            "provider": settings.llm.provider,
            "model_name": settings.llm.model_name,
            "embedding_model": settings.llm.embedding_model,
        },
        "production_profile": settings.production.production_profile,
    }
