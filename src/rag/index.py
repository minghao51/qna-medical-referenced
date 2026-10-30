"""Index initialization and runtime experiment configuration.

Since roadmap P3.2 the build path delegates to the Hamilton DAG via
``ingestion.pipeline.run_ingestion`` — the parallel chunk→HyPE→enrich→
embed→index sequence that used to live here (``_build_index_from_sources``)
is deleted. This module keeps the signature-check reuse logic and the
runtime-state bookkeeping.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import threading
from typing import Any

from src.config.context import RuntimeState, get_runtime_state
from src.ingestion.indexing.chroma_store import (
    get_vector_store,
    get_vector_store_runtime_config,
)
from src.ingestion.indexing.store import build_collection_build_metadata
from src.ingestion.pipeline import IngestionRunConfig, run_ingestion
from src.ingestion.runtime_config import apply_runtime_config, build_experiment_runtime_config

logger = logging.getLogger(__name__)
_INITIALIZATION_LOCK = threading.Lock()

# Provenance keys recorded at build time. Indexes built before provenance was
# introduced lack them; warn instead of failing startup for those artifacts.
_PROVENANCE_KEYS = ("source_snapshot_sha256",)

# Fallback build-critical keys, used only when the build payload itself cannot
# be produced (see ``_required_build_keys``). Provenance keys stay WARN-only,
# but a map missing any required build key must fail closed instead of earning
# validation credit.
_REQUIRED_BUILD_KEYS = (
    "embedding_model",
    "embedding_batch_size",
    "semantic_weight",
    "keyword_weight",
    "boost_weight",
)

# Validation credit for the no-build metadata gate. Tracked separately from
# ``vector_store_initialized``: a permissive initialization (allow_build=True)
# loads a populated index without checking its metadata, so it marks the store
# initialized but must never earn validation credit. Credit is bound to both
# the runtime signature and the concrete store instance, because the factory
# can hand back a different store under an unchanged signature.
_VALIDATED_SIGNATURE_ATTR = "vector_store_validated_signature"


def _store_identity(vector_store: Any) -> int:
    """Identity of the concrete store instance owning the validated index."""
    return id(vector_store)


def _validation_credit(state: RuntimeState) -> tuple[str, int] | None:
    value = getattr(state, _VALIDATED_SIGNATURE_ATTR, None)
    if (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    ):
        return value
    return None


def _expected_index_metadata() -> dict[str, Any]:
    """Effective build metadata implied by the live configuration.

    Starts from the same payload written at build time and overlays the
    resolved vector-store runtime config, so extractor, chunking and
    enrichment keys are compared on equal terms. When the raw corpus is
    unavailable the source digest cannot be re-derived, but the rest of the
    build configuration is still compared.
    """
    built = build_collection_build_metadata()
    if built is None:
        built = build_collection_build_metadata(include_source_digest=False) or {}
    expected: dict[str, Any] = dict(built)
    for key, value in get_vector_store_runtime_config().items():
        if key == "index_metadata":
            expected.update(dict(value or {}))
        else:
            expected[key] = value
    return expected


def _required_build_keys() -> tuple[str, ...]:
    """Build keys a loaded index must record before it may earn credit.

    Derived from the payload the index is certified with, i.e. the same build
    metadata written at build time, with the corpus digest skipped (provenance
    is WARN-only at startup). A newly added build key therefore becomes
    required automatically. Runtime-only keys such as ``collection_name`` are
    not part of that build payload and are never required here.
    """
    built = build_collection_build_metadata(include_source_digest=False)
    if built is None:
        return _REQUIRED_BUILD_KEYS
    return tuple(key for key in built if key not in _PROVENANCE_KEYS)


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
    allow_build: bool = True,
) -> dict[str, Any]:
    """Initialize off-loop; cancellation stops waiting, not an active build.

    If caller cancellation is observed before the worker's post-lock checkpoint,
    it skips all store work. Passing that checkpoint admits initialization: later
    cancellation cannot undo it, even before the first store access. An admitted
    build keeps the lock until completion or failure so another cannot overlap.
    """
    cancelled = threading.Event()
    try:
        return await asyncio.to_thread(
            _initialize_vector_store,
            rebuild=rebuild,
            force_html_convert=force_html_convert,
            allow_build=allow_build,
            cancelled=cancelled,
        )
    except asyncio.CancelledError:
        cancelled.set()
        raise


def _initialize_vector_store(
    rebuild: bool = False,
    *,
    force_html_convert: bool = False,
    allow_build: bool = True,
    cancelled: threading.Event | None = None,
) -> dict[str, Any]:
    """Keep synchronous storage/build work and its thread lock in one worker."""
    with _INITIALIZATION_LOCK:
        # Cooperative cancellation boundary, not a guarantee about when Task.cancel()
        # was requested: the loop may not have delivered it to the caller yet.
        if cancelled is not None and cancelled.is_set():
            raise asyncio.CancelledError
        if not allow_build and rebuild:
            raise RuntimeError("Index rebuild is disabled because allow_build=False")
        state = get_runtime_state()
        runtime_signature = _vector_store_runtime_signature()
        with state._lock:
            if state.vector_store_initialized_signature != runtime_signature:
                state.vector_store_initialized = False

        vector_store = get_vector_store()

        if rebuild:
            # Drop validation credit first: a failed clear must not leave an
            # index certified as verified while it is being replaced.
            setattr(state, _VALIDATED_SIGNATURE_ATTR, None)
            vector_store.clear()
            with state._lock:
                state.vector_store_initialized = False
                state.vector_store_initialized_signature = None

        documents = vector_store.documents
        if documents.get("contents"):
            # Only validate until this store/config is known-good: the expected
            # view re-derives the corpus digest, so re-checking it on every
            # retrieval would hash the raw tree per request. Credit is recorded
            # only by this gate, so a permissive load cannot grant it.
            credit = (runtime_signature, _store_identity(vector_store))
            if not allow_build and _validation_credit(state) != credit:
                metadata = documents.get("index_metadata") or {}
                expected = _expected_index_metadata()
                missing_required = [key for key in _required_build_keys() if key not in metadata]
                mismatched = sorted(
                    key
                    for key, value in metadata.items()
                    if key in expected and expected[key] != value
                )
                for key in _PROVENANCE_KEYS:
                    if key not in metadata:
                        logger.warning(
                            "Existing index metadata is missing provenance key '%s'; "
                            "the index predates provenance recording. Rebuild the index "
                            "to record its source snapshot.",
                            key,
                        )
                if missing_required:
                    collection_label = getattr(vector_store, "collection_name", "<unknown>")
                    raise RuntimeError(
                        "Existing index metadata is missing required build keys "
                        f"({', '.join(missing_required)}) for collection "
                        f"'{collection_label}'; it cannot be verified at startup. "
                        "Use the frozen index "
                        "(APP__STORAGE__CHROMA_PERSIST_DIRECTORY=data/chroma-d11) "
                        "or rebuild with `python -m src.cli.ingest --force-rebuild`."
                    )
                if mismatched:
                    raise RuntimeError(
                        "Existing index configuration does not match runtime settings "
                        f"({', '.join(mismatched)}); "
                        "allow_build=False prevents rebuilding"
                    )
                setattr(state, _VALIDATED_SIGNATURE_ATTR, credit)
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

        if not allow_build:
            raise RuntimeError("Index is empty; allow_build=False prevents ingestion")
        config = IngestionRunConfig.from_runtime_state(
            force_rebuild=rebuild,
            force_html_convert=force_html_convert,
        )
        ingestion = run_ingestion(config)
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
    allow_build: bool = True,
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
            allow_build=allow_build,
        )
    )


def initialize_runtime_index(
    rebuild: bool = False,
    *,
    force_html_convert: bool = False,
    allow_build: bool = True,
) -> dict[str, Any]:
    return initialize_vector_store(
        rebuild=rebuild,
        force_html_convert=force_html_convert,
        allow_build=allow_build,
    )


async def initialize_runtime_index_async(
    rebuild: bool = False,
    *,
    force_html_convert: bool = False,
    allow_build: bool = True,
) -> dict[str, Any]:
    return await initialize_vector_store_async(
        rebuild=rebuild,
        force_html_convert=force_html_convert,
        allow_build=allow_build,
    )


def reset_runtime_index_state() -> None:
    state = get_runtime_state()
    state.reset_vector_store_state()
    setattr(state, _VALIDATED_SIGNATURE_ATTR, None)


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
    state = get_runtime_state()
    state.retrieval_overrides = copy.deepcopy(dict(experiment.get("retrieval", {})))
    state.production_profile = None
    state.reset_vector_store_state()
    # A reset runtime may be served by a different store instance, so any prior
    # validation credit for the old store/config must be dropped as well.
    setattr(state, _VALIDATED_SIGNATURE_ATTR, None)
    return {
        "ingestion": ingestion,
        "embedding_index": embedding_index,
        "vector_store": (
            runtime_config.vector_store.to_dict() if runtime_config.vector_store is not None else {}
        ),
    }
