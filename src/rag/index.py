"""Index initialization and runtime experiment configuration."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any

from src.config import settings
from src.config.context import get_runtime_state
from src.ingestion.indexing.chroma_store import (
    get_vector_store,
    get_vector_store_runtime_config,
)
from src.ingestion.steps.chunking import chunk_documents
from src.ingestion.steps.convert_html import main as convert_html_main
from src.ingestion.steps.load_markdown import get_markdown_documents
from src.ingestion.steps.load_pdfs import get_documents
from src.ingestion.steps.load_reference_data import ReferenceDataLoader
from src.rag.protocols import VectorStoreProtocol
from src.rag.runtime_config import apply_runtime_config, build_experiment_runtime_config

logger = logging.getLogger(__name__)
_INITIALIZATION_LOCK = threading.Lock()


def _vector_store_runtime_signature() -> str:
    return json.dumps(
        get_vector_store_runtime_config(),
        sort_keys=True,
        separators=(",", ":"),
    )


async def _build_index_from_sources(vector_store: VectorStoreProtocol) -> dict[str, Any]:
    build_start = time.time()
    runtime_cfg = get_vector_store_runtime_config()
    indexing_features = dict(runtime_cfg.get("indexing_features", {}) or {})
    loader = ReferenceDataLoader()
    pdf_docs = await asyncio.to_thread(get_documents)
    markdown_docs = await asyncio.to_thread(get_markdown_documents)
    chunked_docs = await asyncio.to_thread(chunk_documents, pdf_docs)
    chunked_docs.extend(chunk_documents(markdown_docs))

    hype_chunk_count = 0
    enriched_chunk_count = 0
    needs_enrichment = indexing_features.get("enable_keyword_extraction") or indexing_features.get(
        "enable_chunk_summaries"
    )

    if indexing_features.get("enable_hype") or needs_enrichment:
        from src.infra.llm.qwen_client import get_client

    if indexing_features.get("enable_hype"):
        from src.ingestion.steps.hypothetical_questions import generate_hype_questions_for_chunks

        hype_questions = await generate_hype_questions_for_chunks(
            chunks=chunked_docs,
            client=get_client(),
            sample_rate=float(
                indexing_features.get("hype_sample_rate", settings.hyde.hype_sample_rate)
            ),
            max_chunks=int(indexing_features.get("hype_max_chunks", settings.hyde.hype_max_chunks)),
            questions_per_chunk=int(
                indexing_features.get(
                    "hype_questions_per_chunk", settings.hyde.hype_questions_per_chunk
                )
            ),
        )
        hype_chunk_count = len(hype_questions)
        for doc in chunked_docs:
            if doc["id"] in hype_questions:
                doc.setdefault("metadata", {})
                doc["metadata"]["hypothetical_questions"] = hype_questions[doc["id"]]

    if needs_enrichment:
        from src.ingestion.steps.enrich_chunks import (
            apply_enrichment_to_chunks,
            enrich_chunks,
        )

        enrichment_results = await enrich_chunks(
            chunks=chunked_docs,
            client=get_client(),
            enable_keywords=bool(indexing_features.get("enable_keyword_extraction")),
            enable_summaries=bool(indexing_features.get("enable_chunk_summaries")),
            sample_rate=float(
                indexing_features.get(
                    "keyword_extraction_sample_rate",
                    settings.enrichment.keyword_extraction_sample_rate,
                )
            ),
            max_chunks=int(
                indexing_features.get(
                    "keyword_extraction_max_chunks",
                    settings.enrichment.keyword_extraction_max_chunks,
                )
            ),
        )
        enriched_chunk_count = apply_enrichment_to_chunks(
            chunked_docs,
            enrichment_results,
            enable_keywords=bool(indexing_features.get("enable_keyword_extraction")),
            enable_summaries=bool(indexing_features.get("enable_chunk_summaries")),
        )

    ref_docs = loader.load_reference_ranges_as_docs()
    chunked_docs.extend(ref_docs)
    stats: dict[str, Any] = vector_store.add_documents(chunked_docs)
    stats["build_elapsed_ms"] = int((time.time() - build_start) * 1000)
    stats["pdf_document_count"] = len(pdf_docs)
    stats["markdown_document_count"] = len(markdown_docs)
    stats["reference_document_count"] = len(ref_docs)
    stats["chunk_count"] = len(chunked_docs)
    stats["hype_chunk_count"] = hype_chunk_count
    stats["enriched_chunk_count"] = enriched_chunk_count
    logger.info(
        "Indexed document chunks (attempted=%d, inserted=%d, duplicate_content=%d)",
        stats["attempted"],
        stats["inserted"],
        stats["skipped_duplicate_content"],
    )
    return stats


async def initialize_vector_store_async(
    rebuild: bool = False,
    *,
    materialize_html: bool = False,
    force_html_reconvert: bool = False,
) -> dict[str, Any]:
    state = get_runtime_state()
    runtime_signature = _vector_store_runtime_signature()
    with _INITIALIZATION_LOCK:
        with state._lock:
            if state.vector_store_initialized_signature != runtime_signature:
                state.vector_store_initialized = False

        vector_store = get_vector_store()

        if rebuild:
            vector_store.clear()
            with state._lock:
                state.vector_store_initialized = False
                state.vector_store_initialized_signature = None

        if materialize_html:
            convert_html_main(force=force_html_reconvert)

        documents = vector_store.documents
        if documents.get("contents"):
            with state._lock:
                if not state.vector_store_initialized:
                    state.vector_store_initialized = True
                    state.vector_store_initialized_signature = runtime_signature
                    logger.info(
                        "Loaded existing vector store with %d documents",
                        len(documents["contents"]),
                    )
                else:
                    state.vector_store_initialized_signature = runtime_signature
            return {
                "status": "ready",
                "reused_existing_index": True,
                "vector_store_config": get_vector_store_runtime_config(),
                "index_metadata": documents.get("index_metadata", {}),
                "vector_document_count": len(documents.get("contents", [])),
                "indexing_stats": vector_store.last_indexing_stats,
            }

        build_stats = await _build_index_from_sources(vector_store)
        documents = vector_store.documents
        with state._lock:
            state.vector_store_initialized = True
            state.vector_store_initialized_signature = runtime_signature
        return {
            "status": "built",
            "reused_existing_index": False,
            "vector_store_config": get_vector_store_runtime_config(),
            "index_metadata": documents.get("index_metadata", {}),
            "vector_document_count": len(documents.get("contents", [])),
            "indexing_stats": build_stats,
        }


def initialize_vector_store(
    rebuild: bool = False,
    *,
    materialize_html: bool = False,
    force_html_reconvert: bool = False,
) -> dict[str, Any]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        raise RuntimeError("Use initialize_vector_store_async in async context")
    return asyncio.run(
        initialize_vector_store_async(
            rebuild=rebuild,
            materialize_html=materialize_html,
            force_html_reconvert=force_html_reconvert,
        )
    )


def initialize_runtime_index(
    rebuild: bool = False,
    *,
    materialize_html: bool = False,
    force_html_reconvert: bool = False,
) -> dict[str, Any]:
    return initialize_vector_store(
        rebuild=rebuild,
        materialize_html=materialize_html,
        force_html_reconvert=force_html_reconvert,
    )


async def initialize_runtime_index_async(
    rebuild: bool = False,
    *,
    materialize_html: bool = False,
    force_html_reconvert: bool = False,
) -> dict[str, Any]:
    return await initialize_vector_store_async(
        rebuild=rebuild,
        materialize_html=materialize_html,
        force_html_reconvert=force_html_reconvert,
    )


def reset_runtime_index_state() -> None:
    get_runtime_state().reset_vector_store_state()


def get_runtime_status() -> dict[str, Any]:
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
    runtime_config = build_experiment_runtime_config(experiment)
    apply_runtime_config(runtime_config)
    get_runtime_state().reset_vector_store_state()
    return {
        "ingestion": ingestion,
        "embedding_index": embedding_index,
        "vector_store": (
            runtime_config.vector_store.to_dict() if runtime_config.vector_store is not None else {}
        ),
    }
