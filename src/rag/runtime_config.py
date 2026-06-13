"""Runtime configuration orchestration helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.config import settings
from src.ingestion.indexing.vector_store import set_vector_store_runtime_config
from src.ingestion.steps.chunk_text import set_auto_select_strategy, set_source_chunk_configs
from src.ingestion.steps.chunking.config import (
    resolve_source_chunk_configs,
    set_structured_chunking_enabled,
)
from src.ingestion.steps.convert_html import (
    set_html_extractor_mode,
    set_html_extractor_strategy,
    set_page_classification_enabled,
)
from src.ingestion.steps.load_markdown import set_index_only_classified_pages
from src.ingestion.steps.load_pdfs import (
    set_pdf_extractor_strategy,
    set_pdf_table_extractor,
)


@dataclass(frozen=True)
class HtmlRuntimeConfig:
    extractor_strategy: str = settings.ingestion.html_extractor_strategy
    extractor_mode: str = settings.ingestion.html_extractor_mode
    page_classification_enabled: bool = settings.ingestion.page_classification_enabled


@dataclass(frozen=True)
class PdfRuntimeConfig:
    extractor_strategy: str = settings.ingestion.pdf_extractor_strategy
    table_extractor: str = settings.ingestion.pdf_table_extractor


@dataclass(frozen=True)
class ChunkingRuntimeConfig:
    structured_chunking_enabled: bool = settings.ingestion.structured_chunking_enabled
    index_only_classified_pages: bool = settings.ingestion.index_only_classified_pages
    source_chunk_configs: dict[str, Any] | None = None
    auto_select_strategy: bool = settings.ingestion.auto_select_strategy


@dataclass(frozen=True)
class VectorStoreRuntimeConfig:
    collection_name: str
    semantic_weight: float
    keyword_weight: float
    boost_weight: float
    embedding_model: str
    embedding_batch_size: int
    indexing_features: dict[str, Any] = field(default_factory=dict)
    index_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_name": self.collection_name,
            "semantic_weight": self.semantic_weight,
            "keyword_weight": self.keyword_weight,
            "boost_weight": self.boost_weight,
            "embedding_model": self.embedding_model,
            "embedding_batch_size": self.embedding_batch_size,
            "indexing_features": dict(self.indexing_features),
            "index_metadata": dict(self.index_metadata),
        }


@dataclass(frozen=True)
class RuntimeConfig:
    html: HtmlRuntimeConfig = field(default_factory=HtmlRuntimeConfig)
    pdf: PdfRuntimeConfig = field(default_factory=PdfRuntimeConfig)
    chunking: ChunkingRuntimeConfig = field(default_factory=ChunkingRuntimeConfig)
    vector_store: VectorStoreRuntimeConfig | None = None


def build_default_runtime_config(
    *,
    disable_page_classification: bool = False,
    disable_structured_chunking: bool = False,
) -> RuntimeConfig:
    return RuntimeConfig(
        html=HtmlRuntimeConfig(
            extractor_strategy=settings.ingestion.html_extractor_strategy,
            extractor_mode="auto",
            page_classification_enabled=not disable_page_classification,
        ),
        pdf=PdfRuntimeConfig(),
        chunking=ChunkingRuntimeConfig(
            structured_chunking_enabled=not disable_structured_chunking,
            index_only_classified_pages=not disable_page_classification,
            source_chunk_configs=None,
            auto_select_strategy=settings.ingestion.auto_select_strategy,
        ),
        vector_store=None,
    )


def build_experiment_runtime_config(experiment: dict[str, Any]) -> RuntimeConfig:
    ingestion = dict(experiment.get("ingestion", {}))
    embedding_index = dict(experiment.get("embedding_index", {}))
    chunking = ChunkingRuntimeConfig(
        structured_chunking_enabled=bool(
            ingestion.get(
                "structured_chunking_enabled", settings.ingestion.structured_chunking_enabled
            )
        ),
        index_only_classified_pages=bool(
            ingestion.get(
                "index_only_classified_pages", settings.ingestion.index_only_classified_pages
            )
        ),
        source_chunk_configs=ingestion.get("source_chunk_configs"),
        auto_select_strategy=bool(
            ingestion.get("auto_select_chunk_strategy", settings.ingestion.auto_select_strategy)
        ),
    )
    resolved_source_chunk_configs = resolve_source_chunk_configs(
        chunking.source_chunk_configs,
        auto_select_strategy=chunking.auto_select_strategy,
    )
    indexing_features = {
        "enable_hype": bool(ingestion.get("enable_hype", settings.hyde.hype_enabled)),
        "hype_sample_rate": float(
            ingestion.get("hype_sample_rate", settings.hyde.hype_sample_rate)
        ),
        "hype_max_chunks": int(ingestion.get("hype_max_chunks", settings.hyde.hype_max_chunks)),
        "hype_questions_per_chunk": int(
            ingestion.get("hype_questions_per_chunk", settings.hyde.hype_questions_per_chunk)
        ),
        "enable_keyword_extraction": bool(
            ingestion.get(
                "enable_keyword_extraction", settings.enrichment.enable_keyword_extraction
            )
        ),
        "enable_chunk_summaries": bool(
            ingestion.get("enable_chunk_summaries", settings.enrichment.enable_chunk_summaries)
        ),
        "keyword_extraction_sample_rate": float(
            ingestion.get(
                "keyword_extraction_sample_rate",
                settings.enrichment.keyword_extraction_sample_rate,
            )
        ),
        "keyword_extraction_max_chunks": int(
            ingestion.get(
                "keyword_extraction_max_chunks", settings.enrichment.keyword_extraction_max_chunks
            )
        ),
    }
    vector_store = VectorStoreRuntimeConfig(
        collection_name=embedding_index.get("collection_name", settings.storage.collection_name),
        semantic_weight=embedding_index.get("semantic_weight", 0.6),
        keyword_weight=embedding_index.get("keyword_weight", 0.2),
        boost_weight=embedding_index.get("boost_weight", 0.2),
        embedding_model=embedding_index.get("embedding_model", settings.llm.embedding_model),
        embedding_batch_size=int(
            embedding_index.get("embedding_batch_size", settings.llm.embedding_batch_size)
        ),
        indexing_features=indexing_features,
        index_metadata={
            "experiment_name": experiment.get("metadata", {}).get("name"),
            "experiment_file": experiment.get("experiment_file"),
            "experiment_config_hash": experiment.get("experiment_config_hash"),
            "index_config_hash": experiment.get("index_config_hash"),
            "collection_name": embedding_index.get(
                "collection_name", settings.storage.collection_name
            ),
            "embedding_model": embedding_index.get("embedding_model", settings.llm.embedding_model),
            "embedding_batch_size": int(
                embedding_index.get("embedding_batch_size", settings.llm.embedding_batch_size)
            ),
            "semantic_weight": embedding_index.get("semantic_weight", 0.6),
            "keyword_weight": embedding_index.get("keyword_weight", 0.2),
            "boost_weight": embedding_index.get("boost_weight", 0.2),
            "page_classification_enabled": ingestion.get(
                "page_classification_enabled", settings.ingestion.page_classification_enabled
            ),
            "index_only_classified_pages": ingestion.get(
                "index_only_classified_pages", settings.ingestion.index_only_classified_pages
            ),
            "html_extractor_mode": ingestion.get(
                "html_extractor_mode", settings.ingestion.html_extractor_mode
            ),
            "html_extractor_strategy": ingestion.get(
                "html_extractor_strategy", settings.ingestion.html_extractor_strategy
            ),
            "pdf_extractor_strategy": ingestion.get(
                "pdf_extractor_strategy", settings.ingestion.pdf_extractor_strategy
            ),
            "pdf_table_extractor": ingestion.get(
                "pdf_table_extractor", settings.ingestion.pdf_table_extractor
            ),
            "structured_chunking_enabled": ingestion.get(
                "structured_chunking_enabled", settings.ingestion.structured_chunking_enabled
            ),
            "source_chunk_configs": json.dumps(resolved_source_chunk_configs),
            **indexing_features,
        },
    )
    return RuntimeConfig(
        html=HtmlRuntimeConfig(
            extractor_strategy=ingestion.get(
                "html_extractor_strategy", settings.ingestion.html_extractor_strategy
            ),
            extractor_mode=ingestion.get(
                "html_extractor_mode", settings.ingestion.html_extractor_mode
            ),
            page_classification_enabled=bool(
                ingestion.get(
                    "page_classification_enabled",
                    settings.ingestion.page_classification_enabled,
                )
            ),
        ),
        pdf=PdfRuntimeConfig(
            extractor_strategy=ingestion.get(
                "pdf_extractor_strategy", settings.ingestion.pdf_extractor_strategy
            ),
            table_extractor=ingestion.get(
                "pdf_table_extractor", settings.ingestion.pdf_table_extractor
            ),
        ),
        chunking=chunking,
        vector_store=vector_store,
    )


def apply_runtime_config(config: RuntimeConfig) -> None:
    set_page_classification_enabled(config.html.page_classification_enabled)
    set_index_only_classified_pages(config.chunking.index_only_classified_pages)
    set_html_extractor_mode(config.html.extractor_mode)
    set_html_extractor_strategy(config.html.extractor_strategy)
    set_pdf_extractor_strategy(config.pdf.extractor_strategy)
    set_pdf_table_extractor(config.pdf.table_extractor)
    set_structured_chunking_enabled(config.chunking.structured_chunking_enabled)
    set_source_chunk_configs(config.chunking.source_chunk_configs)
    set_auto_select_strategy(config.chunking.auto_select_strategy)
    set_vector_store_runtime_config(
        config.vector_store.to_dict() if config.vector_store is not None else None
    )
