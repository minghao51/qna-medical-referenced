"""Collection metadata writes: runtime overlays merge, explicit restores replace.

Chroma's ``collection.modify(metadata=...)`` replaces the whole metadata map,
so a partial runtime overlay used to drop frozen keys such as
``source_snapshot_sha256``; constructor/``documents``-setter overlays now
merge. ``set_index_metadata`` stays authoritative (it is the migration/restore
path) and replaces the map on purpose. These tests use an in-memory fake
collection: no ChromaDB files, no network, no ``data/`` reads.
"""

from __future__ import annotations

from typing import Any

from src.ingestion.indexing.store import ChromaVectorStore

_PROVENANCE = {"source_snapshot_sha256": "a" * 64, "embedding_model": "built-embedder"}


class _FakeCollection:
    """Minimal ChromaDB collection surface used by ChromaVectorStore."""

    def __init__(self, metadata: dict[str, Any] | None = None):
        self.metadata = dict(metadata) if metadata else None
        self.records: dict[str, dict[str, Any]] = {}
        self.modify_calls: list[dict[str, Any]] = []

    def modify(self, metadata: dict[str, Any] | None = None) -> None:
        assert metadata is not None
        self.modify_calls.append(dict(metadata))
        self.metadata = dict(metadata)

    def get(self, include: Any = None, ids: Any = None) -> dict[str, Any]:
        selected = list(self.records)
        return {
            "ids": selected,
            "documents": [self.records[doc_id]["document"] for doc_id in selected],
            "metadatas": [self.records[doc_id]["metadata"] for doc_id in selected],
        }

    def count(self) -> int:
        return len(self.records)

    def upsert(self, **payload: Any) -> None:
        for index, doc_id in enumerate(payload["ids"]):
            self.records[doc_id] = {
                "document": payload["documents"][index],
                "metadata": payload["metadatas"][index],
            }

    def delete(self, ids: Any = None) -> None:
        for doc_id in list(ids or []):
            self.records.pop(doc_id, None)


def _store(collection: _FakeCollection, **kwargs: Any) -> ChromaVectorStore:
    return ChromaVectorStore(
        collection_name="metadata-merge",
        client=object(),
        collection=collection,
        **kwargs,
    )


def test_documents_setter_overlay_preserves_unknown_persisted_keys():
    collection = _FakeCollection(_PROVENANCE)
    store = _store(collection)
    assert collection.modify_calls == []  # adoption of identical metadata is a no-op

    store.documents = {
        "ids": ["chunk-1"],
        "contents": ["synthetic chunk"],
        "metadatas": [{"source": "synthetic.txt"}],
        "index_metadata": {"embedding_model": "runtime-embedder", "semantic_weight": 0.7},
    }

    assert collection.modify_calls == [
        {
            "source_snapshot_sha256": "a" * 64,
            "embedding_model": "runtime-embedder",
            "semantic_weight": 0.7,
        }
    ]
    assert collection.metadata is not None
    assert collection.metadata["source_snapshot_sha256"] == "a" * 64
    # Callers reading metadata back see the merged view, not the partial overlay.
    assert store.documents["index_metadata"] == collection.metadata


def test_documents_setter_does_not_rewrite_unchanged_metadata():
    collection = _FakeCollection(_PROVENANCE)
    store = _store(collection)

    store.documents = {
        "ids": ["chunk-1"],
        "contents": ["synthetic chunk"],
        "metadatas": [{"source": "synthetic.txt"}],
        "index_metadata": {"embedding_model": "built-embedder"},
    }

    assert collection.modify_calls == []
    assert collection.metadata == _PROVENANCE
    assert store.documents["index_metadata"] == _PROVENANCE


def test_init_runtime_overlay_merges_into_persisted_metadata():
    collection = _FakeCollection(_PROVENANCE)
    # index_metadata is the runtime overlay the factory passes ("{}" means unset).
    store = _store(collection, index_metadata={"embedding_model": "runtime-embedder"})

    assert collection.modify_calls == [
        {"source_snapshot_sha256": "a" * 64, "embedding_model": "runtime-embedder"}
    ]
    assert collection.metadata is not None
    assert collection.metadata["source_snapshot_sha256"] == "a" * 64
    assert store._index_metadata == collection.metadata


def test_init_with_empty_overlay_never_drops_persisted_metadata():
    collection = _FakeCollection(_PROVENANCE)
    store = _store(collection, index_metadata={})

    assert collection.modify_calls == []
    assert store._index_metadata == _PROVENANCE


def test_set_index_metadata_replaces_persisted_metadata():
    """set_index_metadata is the authoritative restore path, not an overlay."""
    collection = _FakeCollection(_PROVENANCE)
    store = _store(collection)

    store.set_index_metadata({"embedding_model": "source-embedder", "config_hash": "abc123"})

    expected = {"embedding_model": "source-embedder", "config_hash": "abc123"}
    assert collection.modify_calls == [expected]
    assert collection.metadata == expected
    assert store._index_metadata == expected
    assert store.documents["index_metadata"] == expected
