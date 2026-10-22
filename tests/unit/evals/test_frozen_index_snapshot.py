"""Offline guarantees for immutable frozen index snapshots and private copies."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import pytest

from src.evals.checks import l5_index
from src.evals.index_snapshot import (
    SnapshotError,
    freeze_index_snapshot,
    load_snapshot_export,
    materialize_index_snapshot,
    write_snapshot_export,
)


def _fixture_data() -> dict[str, Any]:
    metadata = {
        "source_snapshot_sha256": "a" * 64,
        "embedding_model": "test-embedder",
        "embedding_batch_size": 8,
        "semantic_weight": 0.6,
        "keyword_weight": 0.2,
        "boost_weight": 0.2,
        "page_classification_enabled": True,
        "index_only_classified_pages": False,
        "html_extractor_mode": "auto",
        "html_extractor_strategy": "primary",
        "pdf_extractor_strategy": "pymupdf",
        "pdf_table_extractor": "none",
        "structured_chunking_enabled": True,
        "source_chunk_configs": "{}",
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
        "ids": ["doc-b", "doc-a"],
        "contents": ["Second document", "First document"],
        "metadatas": [{"source": "b.pdf"}, {"source": "a.pdf"}],
        "embeddings": [[0.0, 1.0], [1.0, 0.0]],
        "index_metadata": metadata,
    }
    build_spec = {
        "collection_name": "frozen-test",
        "collection_metadata": metadata,
        "embedder": {"model": "test-embedder", "batch_size": 8, "dimensions": 2},
        "retrieval_weights": {"semantic": 0.6, "keyword": 0.2, "boost": 0.2},
    }
    return {"snapshot": snapshot, "build_spec": build_spec}


class _FrozenSource:
    def __init__(self, payload: dict[str, Any] | None = None):
        self.payload = payload or _fixture_data()

    def read_consistent_index_snapshot(self) -> dict[str, Any]:
        return self.payload


class _FakeCollection:
    def __init__(self, metadata: dict[str, Any]):
        self.metadata = metadata
        self.rows: dict[str, tuple[str, dict[str, Any], list[float]]] = {}
        self.query_args: dict[str, Any] | None = None

    def upsert(self, *, ids, documents, metadatas, embeddings):
        for doc_id, content, metadata, embedding in zip(
            ids, documents, metadatas, embeddings, strict=True
        ):
            self.rows[doc_id] = (content, dict(metadata), list(embedding))

    def get(self, *, include):
        ordered = sorted(self.rows.items())
        return {
            "ids": [item[0] for item in ordered],
            "documents": [item[1][0] for item in ordered],
            "metadatas": [item[1][1] for item in ordered],
            "embeddings": [item[1][2] for item in ordered],
        }

    def query(self, **kwargs):
        self.query_args = kwargs
        return {"ids": [["doc-a"]], "distances": [[0.0]]}


class _FakeClient:
    pass


def _fake_backend_factory(paths: list[Path]):
    collections: list[_FakeCollection] = []

    def factory(path: Path, build_spec: dict[str, Any]):
        paths.append(path)
        collection = _FakeCollection(
            {
                **build_spec["collection_metadata"],
                "embedding_dimensions": build_spec["embedder"]["dimensions"],
            }
        )
        collections.append(collection)
        return _FakeClient(), collection

    return factory, collections


def test_freeze_copies_data_and_exposes_only_immutable_identity():
    source_payload = _fixture_data()
    frozen = freeze_index_snapshot(_FrozenSource(source_payload))
    source_payload["snapshot"]["contents"][0] = "mutated outside the snapshot"

    captured = frozen.capture_payload()
    assert captured["status"] == "verified"
    assert captured["freeze_guarantee"] is True
    assert captured["snapshot"]["contents"] == ["First document", "Second document"]
    assert captured["snapshot_sha256"] == frozen.snapshot_sha256
    with pytest.raises((AttributeError, TypeError)):
        frozen._snapshot_sha256 = "tampered"  # type: ignore[misc]
    captured["snapshot"]["contents"][0] = "mutated response"
    assert frozen.capture_payload()["snapshot"]["contents"][0] == "First document"


def test_freeze_rejects_legacy_missing_provenance_and_credentials():
    payload = _fixture_data()
    payload["snapshot"]["index_metadata"].pop("source_snapshot_sha256", None)
    payload["build_spec"]["collection_metadata"].pop("source_snapshot_sha256", None)
    with pytest.raises(SnapshotError, match="source provenance"):
        freeze_index_snapshot(_FrozenSource(payload))

    payload = _fixture_data()
    payload["build_spec"]["collection_metadata"]["embedding_api_key"] = "not-a-secret"
    payload["snapshot"]["index_metadata"]["embedding_api_key"] = "not-a-secret"
    with pytest.raises(SnapshotError, match="credentials"):
        freeze_index_snapshot(_FrozenSource(payload))


def test_export_is_read_only_and_load_rehashes_actual_content(tmp_path: Path):
    frozen = freeze_index_snapshot(_FrozenSource())
    export_path = write_snapshot_export(frozen, tmp_path / "frozen.json")
    assert stat.S_IMODE(export_path.stat().st_mode) & 0o222 == 0
    assert load_snapshot_export(export_path).fingerprint == frozen.fingerprint

    export_path.chmod(0o600)
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    payload["status"] = "verified"
    payload["snapshot"]["contents"][0] = "modified bytes"
    export_path.write_text(json.dumps(payload), encoding="utf-8")
    export_path.chmod(0o400)
    with pytest.raises(SnapshotError, match="digest mismatch"):
        load_snapshot_export(export_path)


def test_export_and_materialization_reject_symlink_paths(tmp_path: Path):
    frozen = freeze_index_snapshot(_FrozenSource())
    source = tmp_path / "real.json"
    write_snapshot_export(frozen, source)
    link = tmp_path / "alias.json"
    try:
        link.symlink_to(source)
    except (NotImplementedError, OSError):
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(SnapshotError, match="non-symlink"):
        load_snapshot_export(link)
    linked_parent = tmp_path / "linked-dir"
    linked_parent.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(SnapshotError, match="Snapshot export path"):
        write_snapshot_export(frozen, linked_parent / "other.json")
    with pytest.raises(SnapshotError, match="non-symlink"):
        materialize_index_snapshot(frozen, linked_parent)


def test_each_private_copy_is_fresh_and_queries_use_supplied_vectors(tmp_path: Path):
    frozen = freeze_index_snapshot(_FrozenSource())
    paths: list[Path] = []
    factory, collections = _fake_backend_factory(paths)
    first = materialize_index_snapshot(frozen, tmp_path, backend_factory=factory)
    second = materialize_index_snapshot(frozen, tmp_path, backend_factory=factory)

    assert first.path != second.path
    assert first.path.parent == second.path.parent == tmp_path
    assert (first.path / "snapshot.json").is_file()
    assert stat.S_IMODE((first.path / "snapshot.json").stat().st_mode) & 0o222 == 0
    result = first.query_with_embedding([1.0, 0.0], n_results=1)
    assert result["ids"] == [["doc-a"]]
    assert collections[0].query_args == {
        "query_embeddings": [[1.0, 0.0]],
        "n_results": 1,
    }
    assert collections[0].get(include=[])["ids"] == ["doc-a", "doc-b"]
    assert collections[1].get(include=[])["ids"] == ["doc-a", "doc-b"]

    first.release_backend()
    first.cleanup()
    assert not first.path.exists()
    assert second.path.exists()
    second.release_backend()
    second.cleanup()


def test_unverified_or_fresh_payload_cannot_be_copied(tmp_path: Path, monkeypatch):
    def forbidden_open(*args, **kwargs):
        pytest.fail("capture must not read the shared runtime collection")

    monkeypatch.setattr(l5_index, "_open_store_for_collection", forbidden_open)
    monkeypatch.setattr(l5_index.settings.storage, "chroma_server_host", "")
    unavailable = l5_index.capture_index_snapshot("served")
    assert unavailable == {
        "status": "unverified",
        "reason": "private_frozen_snapshot_required",
    }
    with pytest.raises(SnapshotError, match="Only a revalidated frozen"):
        materialize_index_snapshot({"status": "verified"}, tmp_path)  # type: ignore[arg-type]

    frozen = freeze_index_snapshot(_FrozenSource())
    capture = l5_index.capture_index_snapshot("frozen-test", frozen_snapshot=frozen)
    assert capture["status"] == "verified"
    assert l5_index.capture_index_snapshot("other", frozen_snapshot=frozen)["reason"] == (
        "snapshot_collection_mismatch"
    )
