"""Synthetic regressions for verified index snapshot identity and strict measurements."""

from __future__ import annotations

import json

from src.config import settings
from src.evals.assessment.orchestrator import AssessmentPipeline, _index_snapshot_identity
from src.evals.assessment.thresholds import measurement_summary
from src.evals.index_snapshot import freeze_index_snapshot, write_snapshot_export

_SOURCE_DIGEST = "a" * 64


def _source_payload():
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
        "source_chunk_configs": {"default": {"chunk_size": 100}},
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
        "ids": ["doc-full-id-001", "doc-full-id-002"],
        "contents": ["synthetic document one", "synthetic document two"],
        "metadatas": [{"source": "one"}, {"source": "two"}],
        "embeddings": [[0.1, 0.2], [0.3, 0.4]],
        "index_metadata": metadata,
    }
    build_spec = {
        "collection_name": "verified-test",
        "collection_metadata": metadata,
        "embedder": {"model": "synthetic-embedder", "batch_size": 8, "dimensions": 2},
        "retrieval_weights": {"semantic": 0.7, "keyword": 0.2, "boost": 0.1},
    }
    return {"snapshot": snapshot, "build_spec": build_spec}


class _FakeSource:
    def read_consistent_index_snapshot(self):
        return _source_payload()


class _FakeCollection:
    def __init__(self, build_spec):
        self.metadata = {"embedding_dimensions": build_spec["embedder"]["dimensions"]}
        self.records = {}

    def upsert(self, *, ids, documents, metadatas, embeddings):
        self.records = {
            "ids": list(ids),
            "documents": list(documents),
            "metadatas": list(metadatas),
            "embeddings": [list(vector) for vector in embeddings],
        }

    def get(self, *, include):
        assert include == ["documents", "metadatas", "embeddings"]
        return self.records


class _FakeClient:
    pass


def _fake_backend(directory, build_spec):
    return _FakeClient(), _FakeCollection(build_spec)


def test_verified_snapshot_materializations_have_fresh_paths_and_full_ids(tmp_path):
    frozen = freeze_index_snapshot(_FakeSource())
    first = frozen.materialize(tmp_path, backend_factory=_fake_backend)
    second = frozen.materialize(tmp_path, backend_factory=_fake_backend)
    try:
        assert first.path != second.path
        assert first.collection.records["ids"] == ["doc-full-id-001", "doc-full-id-002"]
        assert second.collection.records["ids"] == first.collection.records["ids"]
        assert first.collection.records["documents"] == [
            "synthetic document one",
            "synthetic document two",
        ]
    finally:
        first.release_backend()
        second.release_backend()
        first.cleanup()
        second.cleanup()


def test_explicit_export_path_rehashes_complete_identity_and_rejects_mutation(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings.storage, "chroma_server_host", "")
    frozen = freeze_index_snapshot(_FakeSource())
    export_path = write_snapshot_export(frozen, tmp_path / "index-snapshot.json")
    pipeline = AssessmentPipeline()

    before = pipeline._capture_index_snapshot("verified-test", index_snapshot_path=export_path)
    before_identity = _index_snapshot_identity(before, corpus_sha256=_SOURCE_DIGEST)
    assert before_identity["status"] == "verified"
    assert before_identity["document_count"] == 2
    assert before_identity["embedding_dimensions"] == 2

    export_path.chmod(0o600)
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    payload["snapshot"]["contents"][0] = "mutated after capture"
    export_path.write_text(json.dumps(payload), encoding="utf-8")
    export_path.chmod(0o400)
    after = pipeline._capture_index_snapshot("verified-test", index_snapshot_path=export_path)
    after_identity = _index_snapshot_identity(after, corpus_sha256=_SOURCE_DIGEST)
    assert after_identity["status"] == "unverified"
    assert after_identity["reason"] == "collection_snapshot_unavailable"
    assert after_identity.get("fingerprint") is None


def test_snapshot_identity_rejects_source_corpus_mismatch():
    capture = freeze_index_snapshot(_FakeSource()).capture_payload()

    identity = _index_snapshot_identity(capture, corpus_sha256="b" * 64)

    assert identity["status"] == "unverified"
    assert identity["reason"] == "index_source_provenance_mismatch"


def test_incomplete_answer_measurements_remain_strictly_incomplete():
    measurement = measurement_summary(
        expected=1,
        retrieval_metrics={"query_count": 1},
        answer_metrics={"status": "error", "query_count": 1, "query_count_complete": 0},
        include_answer_eval=True,
        execution_mode="benchmark",
    )

    assert measurement["status"] == "incomplete"
    assert measurement["suites"]["answer"]["status"] == "incomplete"
    assert measurement["suites"]["answer"]["measured"] == 0
