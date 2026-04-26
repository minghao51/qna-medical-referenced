"""Runtime configuration API endpoints.

Exposes current runtime configuration for the frontend to display,
including retrieval strategy, feature toggles, chunking settings,
and LLM parameters. Read-only — no mutation from the UI.
"""

import logging

from fastapi import APIRouter

from src.config import settings
from src.ingestion.steps.chunking.config import is_structured_chunking_enabled
from src.ingestion.steps.convert_html import (
    get_html_extractor_mode,
    get_html_extractor_strategy,
    is_page_classification_enabled,
)
from src.ingestion.steps.load_markdown import get_index_only_classified_pages
from src.ingestion.steps.load_pdfs import get_pdf_extractor_strategy, get_pdf_table_extractor
from src.rag.runtime import get_runtime_retrieval_config

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/config",
    summary="Get current runtime configuration",
    description="Read-only snapshot of the active runtime configuration",
)
def get_config() -> dict:
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
            "structured_chunking_enabled": is_structured_chunking_enabled(),
            "page_classification_enabled": is_page_classification_enabled(),
            "index_only_classified_pages": get_index_only_classified_pages(),
            "html_extractor_strategy": get_html_extractor_strategy(),
            "html_extractor_mode": get_html_extractor_mode(),
            "pdf_extractor_strategy": get_pdf_extractor_strategy(),
            "pdf_table_extractor": get_pdf_table_extractor(),
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
