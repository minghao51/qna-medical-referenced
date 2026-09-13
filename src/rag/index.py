"""Index initialization and runtime experiment configuration.

Since roadmap P3.2 the build path delegates to the Hamilton DAG via
``ingestion.pipeline.run_ingestion`` — the parallel chunk→HyPE→enrich→
embed→index sequence that used to live here (``_build_index_from_sources``)
is deleted. This module keeps the signature-check reuse logic and the
runtime-state bookkeeping.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from src.config.context import get_runtime_state
from src.ingestion.indexing.chroma_store import (
    get_vector_store,
    get_vector_store_runtime_config,
)
from src.ingestion.pipeline import IngestionRunConfig, run_ingestion
from src.ingestion.runtime_config import apply_runtime_config, build_experiment_runtime_config

logger = logging.getLogger(__name__)
_INITIALIZATION_LOCK = threading.Lock()


def _vector_store_runtime_signature() -> str:
    return json.dumps(
        get_vector_store_runtime_config(),
        sort_keys=True,
        separators=(",", ":"),
    )


async def initialize_vector_store_async(
    rebuild: bool = False,
    *,
    force_html_convert: bool = False,
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

        config = IngestionRunConfig.from_runtime_state(
            force_rebuild=rebuild,
            force_html_convert=force_html_convert,
        )
        ingestion = await asyncio.to_thread(run_ingestion, config)
        build_stats = ingestion.to_stats()
        logger.info(
            "Indexed document chunks (attempted=%d, inserted=%d, duplicate_content=%d)",
            build_stats["attempted"],
            build_stats["inserted"],
            build_stats["skipped_duplicate_content"],
        )
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
    force_html_convert: bool = False,
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
            force_html_convert=force_html_convert,
        )
    )


def initialize_runtime_index(
    rebuild: bool = False,
    *,
    force_html_convert: bool = False,
) -> dict[str, Any]:
    return initialize_vector_store(
        rebuild=rebuild,
        force_html_convert=force_html_convert,
    )


async def initialize_runtime_index_async(
    rebuild: bool = False,
    *,
    force_html_convert: bool = False,
) -> dict[str, Any]:
    return await initialize_vector_store_async(
        rebuild=rebuild,
        force_html_convert=force_html_convert,
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
