"""Offline tests for the D11 collection build-metadata backfill script.

Loads ``scripts/manual/backfill_d11_collection_metadata.py`` through importlib
and exercises it against real local Chroma stores inside ``tmp_path`` with
synthetic vectors only; no network and no real ``data/`` reads.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import pytest

from src.evals.index_snapshot import _REQUIRED_BUILD_METADATA

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "manual"
    / "backfill_d11_collection_metadata.py"
)
_MODULE_NAME = "backfill_d11_collection_metadata_under_test"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("backfill script could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return _load_script_module()


def _make_store_without_metadata(tmp_path: Path, collection_name: str) -> Path:
    import chromadb

    chroma_dir = tmp_path / "chroma"
    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_or_create_collection(name=collection_name, embedding_function=None)
    fixture_vectors: list[Sequence[float]] = [[0.25, 0.75, 0.5], [0.75, 0.25, 0.5]]
    collection.upsert(
        ids=["fixture-1", "fixture-2"],
        documents=["fixture document one", "fixture document two"],
        metadatas=[{"source": "fixture-a.md"}, {"source": "fixture-b.md"}],
        embeddings=fixture_vectors,
    )
    return chroma_dir


def _make_corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "raw-corpus"
    corpus.mkdir()
    (corpus / "guide.md").write_text("public fixture text", encoding="utf-8")
    return corpus


def _use_synthetic_corpus(monkeypatch: pytest.MonkeyPatch, corpus: Path) -> str:
    """Point the store's configured raw corpus at a tmp tree; return its digest."""
    from src.ingestion.indexing import store

    monkeypatch.setattr(store, "DATA_RAW_DIR", corpus)
    return store._corpus_source_digest(corpus)


def _backfill_args(chroma_dir: Path, collection_name: str) -> list[str]:
    return [
        "--chroma-dir",
        str(chroma_dir),
        "--collection",
        collection_name,
    ]


def test_backfill_attaches_required_metadata_and_keeps_embeddings(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    chroma_dir = _make_store_without_metadata(tmp_path, "medical_docs")
    expected_digest = _use_synthetic_corpus(monkeypatch, _make_corpus(tmp_path))

    exit_code = script.main(_backfill_args(chroma_dir, "medical_docs"))

    assert exit_code == 0
    assert "keys added" in capsys.readouterr().out
    import chromadb

    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_collection(name="medical_docs", embedding_function=None)
    metadata = dict(collection.metadata or {})
    assert _REQUIRED_BUILD_METADATA.issubset(metadata)
    assert metadata["source_snapshot_sha256"] == expected_digest
    assert collection.count() == 2


def test_second_run_reports_already_up_to_date(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    chroma_dir = _make_store_without_metadata(tmp_path, "medical_docs")
    _use_synthetic_corpus(monkeypatch, _make_corpus(tmp_path))
    assert script.main(_backfill_args(chroma_dir, "medical_docs")) == 0

    exit_code = script.main(_backfill_args(chroma_dir, "medical_docs"))

    assert exit_code == 0
    assert "already up to date" in capsys.readouterr().out


def test_backfill_preserves_unrelated_existing_metadata_keys(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    chroma_dir = _make_store_without_metadata(tmp_path, "medical_docs")
    expected_digest = _use_synthetic_corpus(monkeypatch, _make_corpus(tmp_path))
    import chromadb

    seeded = chromadb.PersistentClient(path=str(chroma_dir)).get_collection(
        name="medical_docs", embedding_function=None
    )
    seeded.modify(metadata={"custom_note": "keep-me"})

    exit_code = script.main(_backfill_args(chroma_dir, "medical_docs"))

    assert exit_code == 0
    reloaded = chromadb.PersistentClient(path=str(chroma_dir)).get_collection(
        name="medical_docs", embedding_function=None
    )
    metadata = dict(reloaded.metadata or {})
    assert metadata["custom_note"] == "keep-me"
    assert metadata["source_snapshot_sha256"] == expected_digest
    assert _REQUIRED_BUILD_METADATA.issubset(metadata)


def test_missing_corpus_digest_fails_closed(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    chroma_dir = _make_store_without_metadata(tmp_path, "medical_docs")
    from src.ingestion.indexing import store

    monkeypatch.setattr(store, "DATA_RAW_DIR", tmp_path / "missing-corpus")

    exit_code = script.main(_backfill_args(chroma_dir, "medical_docs"))

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "corpus digest unavailable" in captured.err
    assert "source_tree" not in captured.err  # no internal exception reason leaks
    assert "already up to date" not in captured.out


def test_missing_collection_fails_closed(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    import chromadb

    chroma_dir = tmp_path / "chroma"
    chromadb.PersistentClient(path=str(chroma_dir))
    _use_synthetic_corpus(monkeypatch, _make_corpus(tmp_path))

    exit_code = script.main(_backfill_args(chroma_dir, "medical_docs"))

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "collection unavailable" in captured.err
    assert "already up to date" not in captured.out
