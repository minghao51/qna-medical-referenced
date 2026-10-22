"""Focused contracts for frozen-index execution and chunk measurements."""

from __future__ import annotations

from pathlib import Path

from src.evals.assessment.orchestrator import AssessmentPipeline, _index_snapshot_identity
from src.evals.index_snapshot import freeze_index_snapshot
from src.evals.schemas import AssessmentConfig
from src.ingestion.indexing.store import ChromaVectorStore

_SOURCE_DIGEST = "a" * 64


def _frozen_source_payload():
    metadata = {
        "source_snapshot_sha256": _SOURCE_DIGEST,
        "embedding_model": "synthetic-embedder",
        "embedding_batch_size": 8,
        "semantic_weight": 0.7,
        "keyword_weight": 0.2,
        "boost_weight": 0.1,
        "page_classification_enabled": True,
        "index_only_classified_pages": False,
        "html_extractor_mode": "synthetic",
        "html_extractor_strategy": "synthetic-html",
        "pdf_extractor_strategy": "synthetic-pdf",
        "pdf_table_extractor": "synthetic-table",
        "structured_chunking_enabled": True,
        "source_chunk_configs": {
            "html": {"chunk_size": 100, "chunk_overlap": 10},
            "pdf": {"chunk_size": 100, "chunk_overlap": 10},
        },
        "enable_hype": False,
        "hype_sample_rate": 0.0,
        "hype_max_chunks": 0,
        "hype_questions_per_chunk": 0,
        "enable_keyword_extraction": False,
        "enable_chunk_summaries": False,
        "keyword_extraction_sample_rate": 0.0,
        "keyword_extraction_max_chunks": 0,
    }
    snapshot = {
        "ids": ["full-id-1", "full-id-2"],
        "contents": ["first chunk", "second chunk"],
        "metadatas": [
            {"source": "source-a", "page": 1},
            {"source": "source-a", "page": 2},
        ],
        "embeddings": [[1.0, 0.0], [0.0, 1.0]],
        "index_metadata": metadata,
    }
    build_spec = {
        "collection_name": "synthetic-snapshot",
        "collection_metadata": metadata,
        "embedder": {"model": "synthetic-embedder", "batch_size": 8, "dimensions": 2},
        "retrieval_weights": {"semantic": 0.7, "keyword": 0.2, "boost": 0.1},
    }
    return {"snapshot": snapshot, "build_spec": build_spec}


class _ConsistentSource:
    def read_consistent_index_snapshot(self):
        return _frozen_source_payload()


class _Collection:
    def __init__(self):
        self.metadata = {"embedding_dimensions": 2}
        self.records = {"ids": [], "documents": [], "metadatas": [], "embeddings": []}
        self.query_calls = 0

    def upsert(self, *, ids, documents, metadatas, embeddings):
        self.records = {
            "ids": list(ids),
            "documents": list(documents),
            "metadatas": list(metadatas),
            "embeddings": [list(vector) for vector in embeddings],
        }

    def get(self, *, include):
        return {key: self.records[key] for key in include if key in self.records} | {
            "ids": self.records["ids"]
        }

    def count(self):
        return len(self.records["ids"])

    def query(self, **kwargs):
        self.query_calls += 1
        raise AssertionError("The exact local ranking path must not call Chroma query")


class _Client:
    pass


def _step(aggregate=None):
    return {"aggregate": aggregate or {}, "records": [], "findings": []}


def test_private_copy_is_rehashed_from_its_public_read_snapshot(tmp_path):
    frozen = freeze_index_snapshot(_ConsistentSource())
    collection = _Collection()
    materialization = frozen.materialize(
        tmp_path, backend_factory=lambda directory, spec: (_Client(), collection)
    )
    try:
        copied = freeze_index_snapshot(materialization)
        assert copied.fingerprint == frozen.fingerprint
        collection.records["documents"][0] = "mutated private record"
        changed = freeze_index_snapshot(materialization)
        assert changed.fingerprint != frozen.fingerprint
    finally:
        materialization.release_backend()
        materialization.cleanup()


def test_private_store_uses_injected_query_vectors_without_chroma_query_calls():
    collection = _Collection()
    collection.records = {
        "ids": ["doc-1"],
        "documents": ["synthetic medical evidence"],
        "metadatas": [{"source": "synthetic.txt", "quality_score": 1.0}],
        "embeddings": [[1.0, 0.0]],
    }
    supplied_queries = []
    store = ChromaVectorStore(
        collection_name="synthetic-snapshot",
        embedding_model="synthetic-embedder",
        client=_Client(),
        collection=collection,
        query_embedding_fn=lambda query: supplied_queries.append(query) or [1.0, 0.0],
        strict_query_embedding=True,
    )

    results, trace = store.similarity_search_with_trace(
        "synthetic question", top_k=1, search_mode="semantic_only"
    )

    assert supplied_queries == ["synthetic question"]
    assert collection.query_calls == 0
    assert results[0]["id"] == "doc-1"
    assert trace["search_mode"] == "semantic_only"


def test_unverified_capture_is_not_reported_as_an_empty_chunk_measurement():
    seen = {}
    pipeline = AssessmentPipeline(
        audit_l0_download_fn=_step,
        assess_l1_html_markdown_quality_fn=_step,
        assess_l2_pdf_quality_fn=_step,
        assess_l3_chunking_quality_fn=lambda **kwargs: seen.update(kwargs) or _step(),
        assess_l4_reference_quality_fn=_step,
        assess_l5_index_quality_fn=lambda **kwargs: _step(),
        sha256_file_fn=lambda _path: None,
    )

    pipeline._run_step_checks(
        AssessmentConfig(artifact_dir=Path(".")),
        {"vector_store": {"collection_name": "synthetic"}},
        {
            "status": "unverified",
            "snapshot": {
                "ids": [],
                "contents": [],
                "metadatas": [],
                "index_metadata": {},
            },
        },
    )

    assert seen["chunks"] is None
    assert seen["document_count"] is None


def test_verified_chunk_measurement_uses_unique_sources_and_known_uniform_config():
    seen = {}
    pipeline = AssessmentPipeline(
        audit_l0_download_fn=_step,
        assess_l1_html_markdown_quality_fn=_step,
        assess_l2_pdf_quality_fn=_step,
        assess_l3_chunking_quality_fn=lambda **kwargs: seen.update(kwargs) or _step(),
        assess_l4_reference_quality_fn=_step,
        assess_l5_index_quality_fn=lambda **kwargs: _step(),
        sha256_file_fn=lambda _path: None,
    )
    capture = {
        "status": "verified",
        "snapshot": {
            "ids": ["chunk-a", "chunk-b"],
            "contents": ["one", "two"],
            "metadatas": [{"source": "same-source"}, {"source": "same-source"}],
            "index_metadata": _frozen_source_payload()["snapshot"]["index_metadata"],
        },
    }
    pipeline._run_step_checks(
        AssessmentConfig(artifact_dir=Path(".")),
        {"vector_store": {"collection_name": "synthetic"}},
        capture,
    )

    assert len(seen["chunks"]) == 2
    assert seen["document_count"] == 1
    assert seen["chunk_size"] == 100
    assert seen["chunk_overlap"] == 10


def test_snapshot_identity_retains_source_fingerprint_and_hype_capture_status():
    payload = _frozen_source_payload()
    payload["snapshot"]["metadatas"][0]["hypothetical_questions"] = ["synthetic question"]
    capture = freeze_index_snapshot(
        type("Source", (), {"read_consistent_index_snapshot": lambda _self: payload})()
    ).capture_payload()

    identity = _index_snapshot_identity(capture, corpus_sha256=_SOURCE_DIGEST)

    assert identity["status"] == "verified"
    assert identity["hype_auxiliary_captured"] is True
    assert identity["fingerprint"] == capture["fingerprint"]
