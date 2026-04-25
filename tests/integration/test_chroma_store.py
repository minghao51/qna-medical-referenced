"""Tests for ChromaVectorStore core operations."""

from __future__ import annotations

import pytest

from src.ingestion.indexing.chroma_store import (
    ChromaVectorStore,
    ChromaVectorStoreFactory,
)

pytestmark = pytest.mark.live_api


class TestChromaStoreBasic:
    @pytest.fixture
    def store(self):
        s = ChromaVectorStore(
            collection_name="test_chroma_basic",
            semantic_weight=0.6,
            keyword_weight=0.2,
            boost_weight=0.2,
        )
        s.clear()
        yield s
        s.clear()

    def test_clear_deletes_all(self, store):
        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "LDL cholesterol is bad.",
                    "source": "test.pdf",
                    "page": 1,
                }
            ]
        )
        assert store._collection.count() == 1
        store.clear()
        assert store._collection.count() == 0
        assert len(store.content_hashes) == 0

    def test_upsert_updates_existing_id(self, store):
        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Original content.",
                    "source": "test.pdf",
                    "page": 1,
                }
            ]
        )
        assert store._collection.count() == 1

        result = store._collection.get(ids=["doc1"], include=["documents"])
        assert result["documents"][0] == "Original content."

        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Updated content.",
                    "source": "test.pdf",
                    "page": 1,
                }
            ]
        )
        assert store._collection.count() == 1
        result = store._collection.get(ids=["doc1"], include=["documents"])
        assert result["documents"][0] == "Updated content."

    def test_deduplication_by_content_hash(self, store):
        doc = {
            "id": "doc1",
            "content": "Same content across adds.",
            "source": "test.pdf",
            "page": 1,
        }
        r1 = store.add_documents([doc])
        assert r1["inserted"] == 1
        r2 = store.add_documents([doc])
        assert r2["skipped_duplicate_content"] == 1
        r3 = store.add_documents([doc])
        assert r3["skipped_duplicate_content"] == 1
        assert store._collection.count() == 1

    def test_index_metadata_persistence(self, store):
        store.set_index_metadata({"experiment": "test_v1", "version": 1})
        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Content for metadata test.",
                    "source": "test.pdf",
                }
            ]
        )

        store2 = ChromaVectorStore(collection_name="test_chroma_basic")
        assert store2._index_metadata.get("experiment") == "test_v1"


class TestChromaStoreFactory:
    def test_factory_produces_chroma_store(self):
        store = ChromaVectorStoreFactory.get_vector_store({"collection_name": "test_factory"})
        assert isinstance(store, ChromaVectorStore)
        store.clear()
        ChromaVectorStoreFactory.reset()

    def test_factory_singleton_per_config(self):
        ChromaVectorStoreFactory.reset()
        s1 = ChromaVectorStoreFactory.get_vector_store({"collection_name": "test_singleton"})
        s2 = ChromaVectorStoreFactory.get_vector_store({"collection_name": "test_singleton"})
        assert s1 is s2
        s1.clear()
        ChromaVectorStoreFactory.reset()

    def test_factory_different_configs_different_instances(self):
        ChromaVectorStoreFactory.reset()
        s1 = ChromaVectorStoreFactory.get_vector_store(
            {"collection_name": "test_diff", "semantic_weight": 0.6}
        )
        s2 = ChromaVectorStoreFactory.get_vector_store(
            {"collection_name": "test_diff", "semantic_weight": 0.9}
        )
        assert s1 is not s2
        s1.clear()
        s2.clear()
        ChromaVectorStoreFactory.reset()

    def test_backward_compat_vector_store_alias(self):
        from src.ingestion.indexing.vector_store import VectorStore

        assert VectorStore is ChromaVectorStore

    def test_backward_compat_factory_alias(self):
        from src.ingestion.indexing.vector_store import VectorStoreFactory

        assert VectorStoreFactory is ChromaVectorStoreFactory

    def test_backward_compat_get_vector_store_function(self):
        from src.ingestion.indexing.vector_store import get_vector_store

        store1 = get_vector_store({"collection_name": "test_compat_fn"})
        assert isinstance(store1, ChromaVectorStore)
        store1.clear()
        ChromaVectorStoreFactory.reset()


class TestChromaStoreColdStart:
    def test_cold_start_loads_existing_data(self):
        name = "test_cold_start"
        s1 = ChromaVectorStore(collection_name=name)
        s1.clear()
        s1.add_documents(
            [
                {
                    "id": "cold_doc1",
                    "content": "Content persisted after cold start.",
                    "source": "cold.pdf",
                    "page": 1,
                }
            ]
        )
        assert s1._collection.count() == 1

        s2 = ChromaVectorStore(collection_name=name)
        assert s2._collection.count() == 1
        assert "cold_doc1" in s2._id_set

        s2.clear()
