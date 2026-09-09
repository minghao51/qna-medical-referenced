"""Tests for ChromaVectorStore core operations."""

from __future__ import annotations

import pytest

from src.ingestion.indexing.chroma_store import (
    ChromaVectorStore,
    ChromaVectorStoreFactory,
)


# No live_api gate: the Qwen embedding API is stubbed via the
# fake_chroma_embeddings fixture; ChromaDB itself runs for real.
@pytest.fixture(autouse=True)
def _offline_embeddings(fake_chroma_embeddings):
    """Deterministic offline embeddings for every test in this module."""


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

    def test_stats_have_no_dead_duplicate_id_key(self, store):
        """skipped_duplicate_id was always 0 (upserts replace); it is gone."""
        stats = store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Content for stats keys.",
                    "source": "test.pdf",
                    "page": 1,
                }
            ]
        )
        assert "skipped_duplicate_id" not in stats
        assert stats["skipped_duplicate_content"] == 0

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


class TestChromaStoreUpsertMirror:
    """Re-adding an existing doc_id must keep the in-memory mirrors in sync.

    Regression guard: Chroma upserts in place, but the mirrors used to append
    unconditionally, so the stale and fresh copies of the same id both ranked
    in unfiltered searches and documents_for_ranking returned the id twice.
    """

    @pytest.fixture
    def store(self):
        s = ChromaVectorStore(collection_name="test_chroma_upsert_mirror")
        s.clear()
        yield s
        s.clear()

    def test_readd_replaces_in_place_no_duplicate_ids(self, store):
        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Original content about aspirin dosing.",
                    "source": "test.pdf",
                    "page": 1,
                }
            ]
        )
        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Updated content about statin potency.",
                    "source": "test.pdf",
                    "page": 1,
                }
            ]
        )

        assert store._collection.count() == 1
        assert store._doc_ids.count("doc1") == 1
        assert len(store._doc_ids) == len(store._id_set) == 1
        assert store._doc_contents == ["Updated content about statin potency."]

    def test_readd_unfiltered_search_ranks_only_new_content(self, store):
        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Original content about aspirin dosing.",
                    "source": "test.pdf",
                    "page": 1,
                }
            ]
        )
        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Updated content about statin potency.",
                    "source": "test.pdf",
                    "page": 1,
                }
            ]
        )

        results = store.similarity_search("aspirin statin content", top_k=10, hybrid=False)
        ids = [r["id"] for r in results]
        assert len(ids) == len(set(ids))
        assert ids == ["doc1"]
        # Only the fresh copy may rank; the stale content must be gone.
        assert all(r["content"] == "Updated content about statin potency." for r in results)

        _, trace = store.similarity_search_with_trace(
            "aspirin statin content", top_k=10, search_mode="rrf_hybrid"
        )
        assert trace["candidate_counts"]["final"] == 1

    def test_readd_discards_stale_content_hash(self, store):
        """The replaced version's hash must not dedup future re-adds."""
        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Original content about aspirin dosing.",
                    "source": "test.pdf",
                    "page": 1,
                }
            ]
        )
        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Updated content about statin potency.",
                    "source": "test.pdf",
                    "page": 1,
                }
            ]
        )
        # Re-adding the ORIGINAL content under a new id must insert (its hash
        # belonged to the replaced version and was discarded), and re-adding
        # the updated content must be skipped as a duplicate.
        stats = store.add_documents(
            [
                {
                    "id": "doc2",
                    "content": "Original content about aspirin dosing.",
                    "source": "test.pdf",
                    "page": 2,
                },
                {
                    "id": "doc3",
                    "content": "Updated content about statin potency.",
                    "source": "test.pdf",
                    "page": 3,
                },
            ]
        )
        assert stats["inserted"] == 1
        assert stats["skipped_duplicate_content"] == 1
        assert store._collection.count() == 2

    def test_readd_updates_mirror_after_cold_restart(self, store):
        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Cold start original.",
                    "source": "test.pdf",
                    "page": 1,
                }
            ]
        )
        name = store.collection_name

        store2 = ChromaVectorStore(collection_name=name)
        store2.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Cold start updated.",
                    "source": "test.pdf",
                    "page": 1,
                }
            ]
        )
        assert store2._collection.count() == 1
        assert store2._doc_ids.count("doc1") == 1
        assert store2._doc_contents == ["Cold start updated."]


class TestChromaStoreSearchModeValidation:
    def test_invalid_search_mode_raises(self):
        store = ChromaVectorStore(collection_name="test_chroma_mode_validation")
        store.clear()
        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Content for mode validation.",
                    "source": "test.pdf",
                }
            ]
        )
        try:
            with pytest.raises(ValueError, match="valid modes"):
                store.similarity_search("content", search_mode="bogus_mode")
            with pytest.raises(ValueError, match="valid modes"):
                store.similarity_search_with_trace("content", search_mode="bogus_mode")
        finally:
            store.clear()


class TestChromaStoreDocumentsGetter:
    def test_documents_served_from_mirrors_with_embeddings(self):
        store = ChromaVectorStore(collection_name="test_chroma_documents_getter")
        store.clear()
        store.add_documents(
            [
                {
                    "id": "doc1",
                    "content": "Documents getter content one.",
                    "source": "a.pdf",
                },
                {
                    "id": "doc2",
                    "content": "Documents getter content two.",
                    "source": "b.pdf",
                },
            ]
        )
        try:
            payload = store.documents
            assert payload["ids"] == ["doc1", "doc2"]
            assert len(payload["contents"]) == 2
            assert len(payload["embeddings"]) == 2
            assert all(len(emb) > 0 for emb in payload["embeddings"])
            assert payload["metadatas"][0]["source"] == "a.pdf"
            assert payload["index_metadata"] == {}
        finally:
            store.clear()


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
