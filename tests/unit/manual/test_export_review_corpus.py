"""Offline, hermetic tests for ``scripts/manual/export_review_corpus.py``.

The script under test opens a Chroma collection read-only and writes a
review-manifest corpus JSON. These tests never touch ``data/`` and never import
the real ``chromadb`` package: a fake ``chromadb`` module is injected into
``sys.modules`` (via ``monkeypatch``) so the script's ``import chromadb`` inside
``_read_records`` resolves to a stub client/collection that records its calls.

The script module is loaded once through ``importlib`` so the tests stay isolated
from the rest of the repository.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "manual" / "export_review_corpus.py"
)
_MODULE_NAME = "export_review_corpus_under_test"

# (doc_id, content, source, page, chunk_index)
_HAPPY_ROWS: list[tuple[str, str, str, Any, Any]] = [
    ("d2", "A_ch1", "src_a", 1, 1),
    ("d4", "B_pg2", "src_b", 2, 0),
    ("d1", "A_pg1ch2", "src_a", 1, 2),
    ("d3", "A_p10", "src_a", "p10", None),  # non-numeric page, missing chunk_index
]

# Determinism base: numeric-string ids to exercise str-vs-int ordering.
_DET_BASE: dict[str, tuple[str, int, int, str]] = {
    "1": ("src_x", 1, 0, "c1"),
    "2": ("src_x", 1, 1, "c2"),
    "10": ("src_x", 1, 2, "c10"),
    "3": ("src_y", 0, 0, "c3"),
}


class _StubCollection:
    """Minimal Chroma collection stub that records only read calls."""

    def __init__(self) -> None:
        self._ids: list[Any] = []
        self._documents: list[Any] = []
        self._metadatas: list[Any] = []
        self._count: int = 0
        self.calls: list[str] = []

    def set_records(
        self,
        ids: list[Any],
        documents: list[Any],
        metadatas: list[Any],
        *,
        count: int | None = None,
    ) -> None:
        self._ids = list(ids)
        self._documents = list(documents)
        self._metadatas = list(metadatas)
        self._count = len(self._ids) if count is None else count
        self.calls = []

    def count(self) -> int:
        self.calls.append("count")
        return self._count

    def get(self, include: list[str] | None = None) -> dict[str, Any]:
        self.calls.append("get")
        return {
            "ids": self._ids,
            "documents": self._documents,
            "metadatas": self._metadatas,
        }


class _StubClient:
    """Minimal Chroma PersistentClient stub."""

    def __init__(self, collection: _StubCollection) -> None:
        self._collection = collection
        self.collection_name: str | None = None

    def get_collection(self, name: str) -> _StubCollection:
        self.collection_name = name
        return self._collection


class _Harness:
    """Exposes the stub client/collection and a record-injection helper."""

    def __init__(self, client: _StubClient, collection: _StubCollection) -> None:
        self.client = client
        self.collection = collection

    def set_records(
        self,
        ids: list[Any],
        documents: list[Any],
        metadatas: list[Any],
        *,
        count: int | None = None,
    ) -> None:
        self.collection.set_records(ids, documents, metadatas, count=count)


def _load_script_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("export_review_corpus script could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows_to_records(
    rows: list[tuple[str, str, str, Any, Any]],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    for doc_id, content, source, page, chunk in rows:
        meta: dict[str, Any] = {"source": source}
        if page is not None:
            meta["page"] = page
        if chunk is not None:
            meta["chunk_index"] = chunk
        ids.append(doc_id)
        documents.append(content)
        metadatas.append(meta)
    return ids, documents, metadatas


def _base_to_records(
    base: dict[str, tuple[str, int, int, str]], ordering: list[str]
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    for doc_id in ordering:
        source, page, chunk, content = base[doc_id]
        ids.append(doc_id)
        documents.append(content)
        metadatas.append({"source": source, "page": page, "chunk_index": chunk})
    return ids, documents, metadatas


@pytest.fixture(scope="module")
def script() -> types.ModuleType:
    return _load_script_module()


@pytest.fixture
def fake_chromadb(monkeypatch: pytest.MonkeyPatch) -> _Harness:
    """Inject a fake ``chromadb`` module so the script never touches real Chroma."""
    collection = _StubCollection()
    client = _StubClient(collection)
    fake = types.ModuleType("chromadb")
    fake.PersistentClient = lambda path: client
    monkeypatch.setitem(sys.modules, "chromadb", fake)
    return _Harness(client, collection)


def test_read_only_does_not_mutate_collection(
    script: types.ModuleType, fake_chromadb: _Harness, tmp_path: Path
):
    ids, documents, metadatas = _rows_to_records(_HAPPY_ROWS)
    fake_chromadb.set_records(ids, documents, metadatas)
    output = tmp_path / "corpus.json"

    exit_code = script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(output)])

    assert exit_code == 0
    assert output.exists()
    # Only read calls are ever made against the collection.
    assert fake_chromadb.collection.calls == ["count", "get"]


def test_happy_path_exports_expected_corpus(
    script: types.ModuleType,
    fake_chromadb: _Harness,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    ids, documents, metadatas = _rows_to_records(_HAPPY_ROWS)
    fake_chromadb.set_records(ids, documents, metadatas)
    output = tmp_path / "corpus.json"

    exit_code = script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(output)])

    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert set(payload.keys()) == {"sources", "documents"}
    for doc in payload["documents"].values():
        assert set(doc.keys()) == {"source_id", "content"}

    expected_documents = {
        "d1": {"source_id": "src_a", "content": "A_pg1ch2"},
        "d2": {"source_id": "src_a", "content": "A_ch1"},
        "d3": {"source_id": "src_a", "content": "A_p10"},
        "d4": {"source_id": "src_b", "content": "B_pg2"},
    }
    expected_sources = {
        "src_a": {"content": "A_p10\n\nA_ch1\n\nA_pg1ch2"},
        "src_b": {"content": "B_pg2"},
    }
    assert payload["documents"] == expected_documents
    assert payload["sources"] == expected_sources

    out = capsys.readouterr().out
    assert out.count("\n") == 1
    assert "4 documents" in out
    assert "2 sources" in out


def test_output_deterministic_across_record_orderings(
    script: types.ModuleType, fake_chromadb: _Harness, tmp_path: Path
):
    ordering_a = ["1", "2", "10", "3"]  # str order would place "10" before "2"
    ordering_b = ["10", "3", "2", "1"]  # reversed str + numeric-conflicting order

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    ids_a, docs_a, metas_a = _base_to_records(_DET_BASE, ordering_a)
    fake_chromadb.set_records(ids_a, docs_a, metas_a)
    assert script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(first)]) == 0

    ids_b, docs_b, metas_b = _base_to_records(_DET_BASE, ordering_b)
    fake_chromadb.set_records(ids_b, docs_b, metas_b)
    assert script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(second)]) == 0

    assert first.read_bytes() == second.read_bytes()


def test_creates_nested_output_directory(
    script: types.ModuleType, fake_chromadb: _Harness, tmp_path: Path
):
    ids, documents, metadatas = _rows_to_records(_HAPPY_ROWS)
    fake_chromadb.set_records(ids, documents, metadatas)
    output = tmp_path / "a" / "b" / "c" / "corpus.json"

    exit_code = script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(output)])

    assert exit_code == 0
    assert output.exists()


def test_default_collection_name_is_medical_docs(
    script: types.ModuleType, fake_chromadb: _Harness, tmp_path: Path
):
    ids, documents, metadatas = _rows_to_records(_HAPPY_ROWS)
    fake_chromadb.set_records(ids, documents, metadatas)
    output = tmp_path / "corpus.json"

    exit_code = script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(output)])

    assert exit_code == 0
    assert fake_chromadb.client.collection_name == "medical_docs"
    assert output.exists()


def test_refuses_when_collection_count_is_zero(
    script: types.ModuleType,
    fake_chromadb: _Harness,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    fake_chromadb.set_records([], [], [], count=0)
    output = tmp_path / "corpus.json"

    with pytest.raises(SystemExit) as exc:
        script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(output)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert err.strip() != ""
    assert err.count("\n") == 1
    assert not output.exists()


def test_refuses_when_get_returns_empty_ids(
    script: types.ModuleType,
    fake_chromadb: _Harness,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    # count() is non-zero so the count guard passes, but get() yields no ids.
    fake_chromadb.set_records([], [], [], count=3)
    output = tmp_path / "corpus.json"

    with pytest.raises(SystemExit) as exc:
        script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(output)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert err.strip() != ""
    assert err.count("\n") == 1
    assert not output.exists()


def test_refuses_on_non_string_id(
    script: types.ModuleType,
    fake_chromadb: _Harness,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    fake_chromadb.set_records(
        [5, "d2"],
        ["x", "y"],
        [{"source": "s", "page": 1}, {"source": "s", "page": 1}],
    )
    output = tmp_path / "corpus.json"

    with pytest.raises(SystemExit) as exc:
        script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(output)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert err.strip() != ""
    assert err.count("\n") == 1
    assert not output.exists()


def test_refuses_on_non_string_document(
    script: types.ModuleType,
    fake_chromadb: _Harness,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    fake_chromadb.set_records(
        ["d1", "d2"],
        [123, "y"],
        [{"source": "s"}, {"source": "s"}],
    )
    output = tmp_path / "corpus.json"

    with pytest.raises(SystemExit) as exc:
        script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(output)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert err.strip() != ""
    assert err.count("\n") == 1
    assert not output.exists()


def test_refuses_when_source_missing(
    script: types.ModuleType,
    fake_chromadb: _Harness,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    fake_chromadb.set_records(["d1"], ["x"], [{"page": 1}])
    output = tmp_path / "corpus.json"

    with pytest.raises(SystemExit) as exc:
        script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(output)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert err.strip() != ""
    assert err.count("\n") == 1
    assert not output.exists()


def test_refuses_when_source_empty_or_none(
    script: types.ModuleType,
    fake_chromadb: _Harness,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    for bad_source in ("", None):
        fake_chromadb.set_records(["d1"], ["x"], [{"source": bad_source}])
        output = tmp_path / f"corpus_{id(bad_source)}.json"

        with pytest.raises(SystemExit) as exc:
            script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(output)])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert err.strip() != ""
        assert err.count("\n") == 1
        assert not output.exists()


def test_refuses_when_metadata_not_a_dict(
    script: types.ModuleType,
    fake_chromadb: _Harness,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    fake_chromadb.set_records(["d1"], ["x"], [["not", "a", "dict"]])
    output = tmp_path / "corpus.json"

    with pytest.raises(SystemExit) as exc:
        script.main(["--chroma-dir", str(tmp_path / "chroma"), "--output", str(output)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert err.strip() != ""
    assert err.count("\n") == 1
    assert not output.exists()
