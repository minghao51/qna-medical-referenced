"""Offline guarantees for the D11 frozen-identity snapshot builder script.

Drives ``scripts/manual/build_d11_frozen_identity.py`` through importlib with
synthetic fixtures only: no network, no real ``data/`` reads, and the only
Chroma usage is a local persistent store inside ``tmp_path``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from src.config import settings
from src.evals import deepeval_models
from src.evals.assessment.reporting import content_directory_provenance

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "manual" / "build_d11_frozen_identity.py"
)
_MODULE_NAME = "build_d11_frozen_identity_under_test"


def _load_builder_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("D11 builder script could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder() -> ModuleType:
    return _load_builder_module()


_UNVERIFIED_IDENTITY_FIELD_NAMES = (
    "snapshot_sha256",
    "fingerprint",
    "build_spec_sha256",
    "document_count",
    "embedding_dimensions",
    "embedding_model",
    "collection_name",
    "retrieval_weights",
    "source_snapshot_sha256",
)


def _fixture_metadata() -> dict[str, Any]:
    return {
        "source_snapshot_sha256": "b" * 64,
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


def _fixture_payload() -> dict[str, Any]:
    metadata = _fixture_metadata()
    snapshot = {
        "ids": ["doc-beta", "doc-alpha"],
        "contents": ["beta document body", "alpha document body"],
        "metadatas": [{"source": "beta.pdf"}, {"source": "alpha.pdf"}],
        "embeddings": [[0.0, 1.0], [1.0, 0.0]],
        "index_metadata": metadata,
    }
    build_spec = {
        "collection_name": "d11-fixture",
        "collection_metadata": metadata,
        "embedder": {"model": "test-embedder", "batch_size": 8, "dimensions": 2},
        "retrieval_weights": {"semantic": 0.6, "keyword": 0.2, "boost": 0.2},
    }
    return {"snapshot": snapshot, "build_spec": build_spec}


def _embedder_role(dimensions: int = 768) -> dict[str, Any]:
    return {
        "provider": "qwen",
        "model": "text-embedding-v4",
        "endpoint": "https://dashscope-us.aliyuncs.com/compatible-mode/v1",
        "dimensions": dimensions,
        "batch_size": 10,
    }


def _verified_document(builder: ModuleType) -> tuple[dict[str, Any], str]:
    capture = builder.freeze_from_payload(_fixture_payload())
    document = builder.build_output_document(
        embedding_identity=builder.build_embedding_identity(_embedder_role()),
        # Matches the fixture capture's source_snapshot_sha256 ("b" * 64) so
        # the provenance cross-check keeps the index identity verified.
        corpus_identity={
            "version": 1,
            "status": "verified",
            "content_sha256": "b" * 64,
            "file_count": 2,
            "reason": None,
        },
        index_identity=builder.build_index_identity_from_capture(capture),
    )
    return document, builder.serialize_output(document)


def _collect_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            keys |= _collect_keys(item)
    elif isinstance(value, list):
        for item in value:
            keys |= _collect_keys(item)
    return keys


def _make_local_chroma_dir(
    tmp_path: Path, collection_name: str, *, add_document: bool = False
) -> Path:
    import chromadb

    chroma_dir = tmp_path / "chroma"
    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_or_create_collection(name=collection_name, embedding_function=None)
    if add_document:
        fixture_vectors: list[Sequence[float]] = [[0.25, 0.75]]
        collection.upsert(
            ids=["doc-extra"],
            documents=["unreviewed fixture content"],
            metadatas=[{"source": "extra.pdf"}],
            embeddings=fixture_vectors,
        )
    return chroma_dir


def test_verified_capture_extracts_all_identity_fields(builder: ModuleType):
    capture = builder.freeze_from_payload(_fixture_payload())
    identity = builder.build_index_identity_from_capture(capture)

    assert identity["status"] == "verified"
    assert identity["reason"] is None
    assert identity["freeze_guarantee"] is True
    assert identity["snapshot_sha256"] == capture["snapshot_sha256"]
    assert identity["fingerprint"] == capture["fingerprint"]
    assert identity["build_spec_sha256"] == capture["build_spec_sha256"]
    assert identity["document_count"] == 2
    assert identity["embedding_dimensions"] == 2
    assert identity["embedding_model"] == "test-embedder"
    assert identity["collection_name"] == "d11-fixture"
    assert identity["retrieval_weights"] == {"semantic": 0.6, "keyword": 0.2, "boost": 0.2}
    assert identity["source_snapshot_sha256"] == "b" * 64


def test_output_document_downgrades_index_identity_on_provenance_mismatch(
    builder: ModuleType,
):
    capture = builder.freeze_from_payload(_fixture_payload())
    index_identity = builder.build_index_identity_from_capture(capture)
    assert index_identity["status"] == "verified"
    corpus_identity = {
        "version": 1,
        "status": "verified",
        "content_sha256": "c" * 64,  # differs from the captured "b" * 64
        "file_count": 2,
        "reason": None,
    }

    document = builder.build_output_document(
        embedding_identity=builder.build_embedding_identity(_embedder_role()),
        corpus_identity=corpus_identity,
        index_identity=index_identity,
    )

    downgraded = document["index_identity"]
    assert downgraded["status"] == "unverified"
    assert downgraded["reason"] == "index_source_provenance_mismatch"
    assert downgraded["freeze_guarantee"] is False
    for field in _UNVERIFIED_IDENTITY_FIELD_NAMES:
        assert downgraded[field] is None
    # The other blocks stay exactly as computed.
    assert document["embedding_identity"]["status"] == "verified"
    assert document["corpus_identity"] == corpus_identity


def test_output_document_keeps_verified_index_identity_on_matching_provenance(
    builder: ModuleType,
):
    capture = builder.freeze_from_payload(_fixture_payload())
    index_identity = builder.build_index_identity_from_capture(capture)

    document = builder.build_output_document(
        embedding_identity=builder.build_embedding_identity(_embedder_role()),
        corpus_identity={
            "version": 1,
            "status": "verified",
            "content_sha256": index_identity["source_snapshot_sha256"],
            "file_count": 2,
            "reason": None,
        },
        index_identity=index_identity,
    )

    assert document["index_identity"] == dict(index_identity)


def test_provenance_cross_check_downgrades_on_missing_corpus_digest_and_passes_unverified(
    builder: ModuleType,
):
    capture = builder.freeze_from_payload(_fixture_payload())
    index_identity = builder.build_index_identity_from_capture(capture)

    unavailable_corpus = builder.index_identity_with_provenance_cross_check(
        {
            "version": 1,
            "status": "unverified",
            "content_sha256": None,
            "file_count": 0,
            "reason": "source_tree_unavailable",
        },
        index_identity,
    )
    assert unavailable_corpus["status"] == "unverified"
    assert unavailable_corpus["reason"] == "index_source_provenance_mismatch"

    # An already-unverified index identity passes through untouched.
    untouched = builder.index_identity_with_provenance_cross_check(
        {"version": 1, "status": "verified", "content_sha256": "c" * 64, "file_count": 2},
        builder.unverified_index_identity("chroma_directory_missing"),
    )
    assert untouched["reason"] == "chroma_directory_missing"
    assert untouched["status"] == "unverified"


def test_serialized_output_holds_only_identity_and_no_content(builder: ModuleType):
    document, text = _verified_document(builder)

    forbidden_keys = {"contents", "metadatas", "embeddings", "snapshot", "build_spec"}
    assert forbidden_keys.isdisjoint(_collect_keys(document))
    for fixture_string in ("alpha document body", "beta document body", "alpha.pdf", "beta.pdf"):
        assert fixture_string not in text

    parsed = json.loads(text)
    assert parsed == json.loads(builder.serialize_output(document))
    assert builder.serialize_output(document) == text  # deterministic serialization
    assert parsed["schema_version"] == 1
    assert parsed["generation"] == {
        "script": "scripts/manual/build_d11_frozen_identity.py",
        "offline_only": True,
    }
    decision = parsed["d11_decision"]
    assert decision["cross_encoder_reranker"] == "not_selected_not_downloaded"
    assert decision["live_claims"] is False
    assert decision["clinical_quality_verified"] is False
    assert "test-api-key" not in text  # no credential material from the environment


def test_missing_build_provenance_is_recorded_unverified_without_exception(
    builder: ModuleType,
):
    payload = _fixture_payload()
    payload["snapshot"]["index_metadata"].pop("source_snapshot_sha256", None)
    payload["build_spec"]["collection_metadata"].pop("source_snapshot_sha256", None)

    capture = builder.freeze_from_payload(payload)  # must not raise
    identity = builder.build_index_identity_from_capture(capture)

    assert capture["status"] == "unverified"
    assert capture["reason"] == "Index build metadata is missing; rebuild with source provenance"
    assert identity["status"] == "unverified"
    assert identity["reason"] == capture["reason"]
    assert identity["freeze_guarantee"] is False
    for field in _UNVERIFIED_IDENTITY_FIELD_NAMES:
        assert identity[field] is None


def test_forged_success_shaped_capture_is_rejected_unverified(builder: ModuleType):
    forged: dict[str, Any] = {
        "status": "verified",
        "reason": None,
        "freeze_guarantee": True,
        "snapshot_sha256": None,
        "fingerprint": None,
        "build_spec_sha256": None,
        "snapshot": {},
        "build_spec": {},
    }

    identity = builder.build_index_identity_from_capture(forged)

    assert identity["status"] == "unverified"
    assert identity["reason"] == "index_capture_invalid"
    assert identity["freeze_guarantee"] is False
    for field in _UNVERIFIED_IDENTITY_FIELD_NAMES:
        assert identity[field] is None

    # Even well-formed digests cannot rescue empty/minimal nested shapes: the
    # document count and embedder identity fields are validated on the way to
    # verified, so a forged capture is never emitted with null identity fields.
    dressed = dict(forged)
    dressed.update(
        {
            "snapshot_sha256": "a" * 64,
            "fingerprint": "b" * 64,
            "build_spec_sha256": "c" * 64,
            "snapshot": {"ids": []},
            "build_spec": {
                "collection_name": "d11-fixture",
                "collection_metadata": {},
                "embedder": {"model": "test-embedder", "dimensions": 2},
                "retrieval_weights": {},
            },
        }
    )
    dressed_identity = builder.build_index_identity_from_capture(dressed)
    assert dressed_identity["status"] == "unverified"
    assert dressed_identity["reason"] == "index_capture_invalid"
    assert dressed_identity["document_count"] is None
    assert dressed_identity["snapshot_sha256"] is None


def test_forged_verified_capture_without_provenance_or_weights_is_rejected(
    builder: ModuleType,
):
    # Reaches the strict validation checks: positive document count,
    # valid-shaped digests, non-empty embedder and collection identity -
    # but {} retrieval weights and missing source provenance must still
    # fail closed with null identity fields (mirrors the upstream
    # _validate_build_spec contract).
    forged: dict[str, Any] = {
        "status": "verified",
        "reason": None,
        "freeze_guarantee": True,
        "snapshot_sha256": "a" * 64,
        "fingerprint": "b" * 64,
        "build_spec_sha256": "c" * 64,
        "snapshot": {"ids": ["doc-1"]},
        "build_spec": {
            "collection_name": "d11-fixture",
            "collection_metadata": {},
            "embedder": {"model": "test-embedder", "dimensions": 2},
            "retrieval_weights": {},
        },
    }

    identity = builder.build_index_identity_from_capture(forged)
    assert identity["status"] == "unverified"
    assert identity["reason"] == "index_capture_invalid"
    assert identity["freeze_guarantee"] is False
    for field in _UNVERIFIED_IDENTITY_FIELD_NAMES:
        assert identity[field] is None

    # A null source provenance digest is not accepted either: upstream
    # requires the 64-char lowercase hex digest, and so does this extractor.
    provenanceless = dict(forged)
    provenanceless["build_spec"] = dict(forged["build_spec"])
    provenanceless["build_spec"]["retrieval_weights"] = {
        "semantic": 0.6,
        "keyword": 0.2,
        "boost": 0.2,
    }
    provenanceless["build_spec"]["collection_metadata"] = {
        "source_snapshot_sha256": None,
    }
    null_provenance = builder.build_index_identity_from_capture(provenanceless)
    assert null_provenance["status"] == "unverified"
    assert null_provenance["reason"] == "index_capture_invalid"
    assert null_provenance["source_snapshot_sha256"] is None

    # Non-finite weight values are rejected, mirroring the upstream check.
    nonfinite = dict(forged)
    nonfinite["build_spec"] = dict(forged["build_spec"])
    nonfinite["build_spec"]["collection_metadata"] = {
        "source_snapshot_sha256": "b" * 64,
    }
    nonfinite["build_spec"]["retrieval_weights"] = {
        "semantic": float("nan"),
        "keyword": 0.2,
        "boost": 0.2,
    }
    nan_weights = builder.build_index_identity_from_capture(nonfinite)
    assert nan_weights["status"] == "unverified"
    assert nan_weights["reason"] == "index_capture_invalid"
    assert nan_weights["retrieval_weights"] is None


def test_corpus_identity_passes_through_content_directory_provenance_verbatim(
    builder: ModuleType, tmp_path: Path
):
    corpus = tmp_path / "raw"
    corpus.mkdir()
    (corpus / "guide.md").write_text("public fixture text", encoding="utf-8")
    (corpus / "nested").mkdir()
    (corpus / "nested" / "table.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    direct = content_directory_provenance(corpus)
    document = builder.build_output_document(
        embedding_identity=builder.build_embedding_identity(_embedder_role()),
        corpus_identity=direct,
        index_identity=builder.unverified_index_identity("unused"),
    )
    assert document["corpus_identity"] == direct
    assert direct["status"] == "verified"
    assert direct["file_count"] == 2
    assert set(direct) == {"version", "status", "content_sha256", "file_count", "reason"}

    empty = builder.build_output_document(
        embedding_identity=builder.build_embedding_identity(_embedder_role()),
        corpus_identity=content_directory_provenance(tmp_path / "missing-corpus"),
        index_identity=builder.unverified_index_identity("unused"),
    )
    assert empty["corpus_identity"] == {
        "version": 1,
        "status": "unverified",
        "content_sha256": None,
        "file_count": 0,
        "reason": "source_tree_unavailable",
    }


def test_embedding_identity_records_roles_values_not_hardcoded_dimensions(
    builder: ModuleType,
):
    identity = builder.build_embedding_identity(_embedder_role(dimensions=768))
    assert identity["status"] == "verified"
    assert identity["dimensions"] == 768
    assert identity["dimensions_match_d11_decision"] is True
    assert identity["provider"] == "qwen"
    assert identity["model"] == "text-embedding-v4"
    assert identity["batch_size"] == 10
    assert identity["endpoint"] == "https://dashscope-us.aliyuncs.com/compatible-mode/v1"

    drifted = builder.build_embedding_identity(_embedder_role(dimensions=512))
    assert drifted["status"] == "verified"
    assert drifted["dimensions"] == 512  # value recorded regardless of the decision
    assert drifted["dimensions_match_d11_decision"] is False

    incomplete = builder.build_embedding_identity({"provider": "qwen"})
    assert incomplete["status"] == "unverified"
    assert incomplete["reason"] == "embedder_role_incomplete"
    assert incomplete["role_source"] == "src.evals.deepeval_models.effective_roles"
    assert incomplete["provider"] is None
    assert incomplete["model"] is None
    assert incomplete["dimensions"] is None
    assert incomplete["batch_size"] is None
    assert incomplete["endpoint"] is None
    assert incomplete["dimensions_match_d11_decision"] is False
    assert not any("key" in key or "secret" in key or "token" in key for key in identity)


def test_offline_refusal_mirrors_l5_remote_check(builder: ModuleType):
    assert builder.offline_refusal_reason("") is None
    assert builder.offline_refusal_reason("   ") is None
    assert builder.offline_refusal_reason("chroma.example.com") == (
        "remote_snapshot_verification_unsupported"
    )


def test_main_refuses_remote_chroma_configuration_without_touching_chroma(
    builder: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    monkeypatch.setattr(settings.storage, "chroma_server_host", "chroma.example.com")
    output = tmp_path / "identity.json"

    exit_code = builder.main(["--output", str(output)])

    assert exit_code == 2
    assert "remote_snapshot_verification_unsupported" in capsys.readouterr().err
    assert not output.exists()
    assert "chromadb" not in vars(builder)  # the refusal path cannot touch Chroma


def test_missing_chroma_source_or_collection_is_honestly_unverified(
    builder: ModuleType, tmp_path: Path
):
    missing_dir = builder.capture_index_identity_from_chroma_dir(
        tmp_path / "absent",
        collection_name="d11-fixture",
        embedder_role=_embedder_role(),
    )
    assert missing_dir["status"] == "unverified"
    assert missing_dir["reason"] == "chroma_directory_missing"
    assert missing_dir["snapshot_sha256"] is None

    empty_store = _make_local_chroma_dir(tmp_path, "unrelated-collection")
    absent_collection = builder.capture_index_identity_from_chroma_dir(
        empty_store,
        collection_name="d11-fixture",
        embedder_role=_embedder_role(),
    )
    assert absent_collection["status"] == "unverified"
    assert absent_collection["reason"] == "chroma_collection_missing_or_unreadable"
    assert absent_collection["fingerprint"] is None


def test_source_store_mutated_during_copy_is_reported_unstable(
    builder: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    chroma_dir = _make_local_chroma_dir(tmp_path, "d11-unstable", add_document=True)
    real_signature: Callable[[Path], dict[str, tuple[int, int]]] = builder._source_tree_signature
    calls = {"count": 0}

    def signature_with_mid_copy_mutation(directory: Path) -> dict[str, tuple[int, int]]:
        # Between the before-copy and after-copy signature captures, a writer
        # mutates the shared store; the quiescence check must detect it.
        calls["count"] += 1
        if calls["count"] == 2:
            os.utime(directory / "chroma.sqlite3", (1, 1))
        return real_signature(directory)

    monkeypatch.setattr(builder, "_source_tree_signature", signature_with_mid_copy_mutation)

    identity = builder.capture_index_identity_from_chroma_dir(
        chroma_dir,
        collection_name="d11-unstable",
        embedder_role=_embedder_role(),
    )

    assert calls["count"] == 2
    assert identity["status"] == "unverified"
    assert identity["reason"] == "chroma_source_unstable"
    assert identity["freeze_guarantee"] is False
    assert identity["snapshot_sha256"] is None


def test_sqlite_write_lock_excludes_concurrent_writers(builder: ModuleType, tmp_path: Path):
    # Deterministic lock protocol check: exactly two connections, no
    # threads. While the helper holds BEGIN EXCLUSIVE on the source store's
    # sqlite file (the boundary Chroma writers coordinate through), a second
    # connection cannot commit a write.
    db_path = tmp_path / "chroma.sqlite3"
    setup = sqlite3.connect(db_path)
    try:
        setup.execute("CREATE TABLE acquire_write (id INTEGER)")
        setup.execute("INSERT INTO acquire_write VALUES (1)")
        setup.commit()
    finally:
        setup.close()

    with builder._source_sqlite_write_lock(db_path) as held:
        assert held.in_transaction
        blocked = sqlite3.connect(db_path, timeout=0.1)
        try:
            with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                blocked.execute("INSERT INTO acquire_write VALUES (2)")
        finally:
            blocked.close()

    # The lock is released on exit and the source store is unmodified.
    verify = sqlite3.connect(db_path)
    try:
        assert verify.execute("SELECT COUNT(*) FROM acquire_write").fetchone()[0] == 1
        verify.execute("INSERT INTO acquire_write VALUES (2)")
    finally:
        verify.close()


def test_missing_source_sqlite_is_reported_lock_unavailable(builder: ModuleType, tmp_path: Path):
    bare_dir = tmp_path / "chroma-no-sqlite"
    bare_dir.mkdir()
    (bare_dir / "some-hnsw-file.bin").write_bytes(b"not a database")

    identity = builder.capture_index_identity_from_chroma_dir(
        bare_dir,
        collection_name="d11-fixture",
        embedder_role=_embedder_role(),
    )

    assert identity["status"] == "unverified"
    assert identity["reason"] == "chroma_source_lock_unavailable"
    assert identity["freeze_guarantee"] is False
    for field in _UNVERIFIED_IDENTITY_FIELD_NAMES:
        assert identity[field] is None


def test_prelocked_source_sqlite_is_reported_lock_unavailable(builder: ModuleType, tmp_path: Path):
    chroma_dir = _make_local_chroma_dir(tmp_path, "d11-prelocked")
    holder = sqlite3.connect(chroma_dir / "chroma.sqlite3", timeout=1.0)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        identity = builder.capture_index_identity_from_chroma_dir(
            chroma_dir,
            collection_name="d11-prelocked",
            embedder_role=_embedder_role(),
        )
    finally:
        holder.execute("ROLLBACK")
        holder.close()

    assert identity["status"] == "unverified"
    assert identity["reason"] == "chroma_source_lock_unavailable"
    assert identity["freeze_guarantee"] is False
    for field in _UNVERIFIED_IDENTITY_FIELD_NAMES:
        assert identity[field] is None


def test_corrupt_chroma_store_is_honestly_unverified(builder: ModuleType, tmp_path: Path):
    corrupt = tmp_path / "chroma-corrupt"
    corrupt.mkdir()
    (corrupt / "chroma.sqlite3").write_bytes(b"definitely not a sqlite database")

    identity = builder.capture_index_identity_from_chroma_dir(
        corrupt,
        collection_name="d11-corrupt",
        embedder_role=_embedder_role(),
    )

    assert identity["status"] == "unverified"
    # The corrupt source sqlite is now rejected at the writer-coordination
    # lock boundary, before the copied store is ever opened.
    assert identity["reason"] == "chroma_source_lock_unavailable"
    assert identity["freeze_guarantee"] is False
    assert identity["snapshot_sha256"] is None
    assert identity["reason"] != ""  # an exact, non-empty reason is always recorded


def test_empty_collection_is_honestly_unverified(builder: ModuleType, tmp_path: Path):
    chroma_dir = _make_local_chroma_dir(tmp_path, "d11-empty")

    identity = builder.capture_index_identity_from_chroma_dir(
        chroma_dir,
        collection_name="d11-empty",
        embedder_role=_embedder_role(),
    )

    assert identity["status"] == "unverified"
    assert identity["reason"] == ("Index snapshot is empty or exceeds the supported document count")
    assert identity["freeze_guarantee"] is False
    assert identity["document_count"] is None


def test_collection_without_build_metadata_stays_unverified(builder: ModuleType, tmp_path: Path):
    chroma_dir = _make_local_chroma_dir(tmp_path, "d11-unprovenanced", add_document=True)

    identity = builder.capture_index_identity_from_chroma_dir(
        chroma_dir,
        collection_name="d11-unprovenanced",
        embedder_role=_embedder_role(),
    )

    assert identity["status"] == "unverified"
    assert identity["reason"] == "Index build metadata is missing; rebuild with source provenance"


def test_main_writes_honest_offline_document_end_to_end(
    builder: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings.storage, "chroma_server_host", "")
    chroma_dir = _make_local_chroma_dir(tmp_path, settings.storage.collection_name)
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    output = tmp_path / "identity.json"

    exit_code = builder.main(
        [
            "--output",
            str(output),
            "--chroma-dir",
            str(chroma_dir),
            "--corpus-dir",
            str(corpus_dir),
        ]
    )

    assert exit_code == 0
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    assert document["corpus_identity"]["status"] == "unverified"
    assert document["corpus_identity"]["reason"] == "source_tree_empty"
    assert document["index_identity"]["status"] == "unverified"
    assert document["index_identity"]["reason"] == (
        "Index snapshot is empty or exceeds the supported document count"
    )
    embedding = document["embedding_identity"]
    assert embedding["status"] == "verified"
    assert embedding["provider"] == "qwen"
    assert embedding["model"] == "text-embedding-v4"
    assert embedding["dimensions"] == 768
    assert embedding["dimensions_match_d11_decision"] is True
    assert document["d11_decision"]["cross_encoder_reranker"] == "not_selected_not_downloaded"


def test_main_serializes_unverified_embedding_identity_when_role_is_missing(
    builder: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings.storage, "chroma_server_host", "")
    monkeypatch.setattr(deepeval_models, "effective_roles", lambda *, task: {})
    chroma_dir = _make_local_chroma_dir(tmp_path, settings.storage.collection_name)
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    output = tmp_path / "identity.json"

    exit_code = builder.main(
        [
            "--output",
            str(output),
            "--chroma-dir",
            str(chroma_dir),
            "--corpus-dir",
            str(corpus_dir),
        ]
    )

    assert exit_code == 0
    document = json.loads(output.read_text(encoding="utf-8"))
    embedding = document["embedding_identity"]
    assert embedding["status"] == "unverified"
    assert embedding["reason"] == "embedder_role_unavailable"
    assert embedding["role_source"] == "src.evals.deepeval_models.effective_roles"
    assert embedding["provider"] is None
    assert embedding["model"] is None
    assert embedding["dimensions"] is None
    assert embedding["batch_size"] is None
    assert embedding["endpoint"] is None
    assert embedding["dimensions_match_d11_decision"] is False
    # The index path still records an honest diagnosis of its own source.
    assert document["index_identity"]["status"] == "unverified"
    assert document["index_identity"]["reason"] == (
        "Index snapshot is empty or exceeds the supported document count"
    )
