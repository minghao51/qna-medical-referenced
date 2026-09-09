"""Tests for the JSON → ChromaDB migration script."""

from __future__ import annotations

import json

import pytest


class TestMigrationScript:
    def test_migration_imports_all_documents(self, tmp_path):
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        from src.ingestion.indexing.migrate import migrate

        vector_dir = tmp_path / "vectors"
        vector_dir.mkdir()
        chroma_dir = tmp_path / "chroma"

        json_data = {
            "ids": ["mig_doc1", "mig_doc2", "mig_doc3"],
            "contents": [
                "LDL cholesterol is bad for you.",
                "Pre-diabetes can be managed with lifestyle changes.",
                "Cardiovascular risk factors include smoking.",
            ],
            "embeddings": [
                [0.1, 0.2, 0.3] * 256,
                [0.4, 0.5, 0.6] * 256,
                [0.7, 0.8, 0.9] * 256,
            ],
            "metadatas": [
                {"source": "lipid.pdf", "page": 1, "quality_score": 0.9},
                {"source": "diabetes.pdf", "page": 2, "quality_score": 0.8},
                {"source": "cv.pdf", "page": 1, "quality_score": 0.85},
            ],
            "content_hashes": ["hash1", "hash2", "hash3"],
            "index_metadata": {"experiment": "migration_test"},
        }

        json_file = vector_dir / "test_migration.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f)

        collection_name = "test_migration"
        report = migrate(
            collection_name=collection_name,
            vector_dir=str(vector_dir),
            chroma_dir=str(chroma_dir),
        )

        assert report["attempted"] == 3
        assert report["inserted"] == 3

        client = chromadb.PersistentClient(
            path=str(chroma_dir),
            settings=ChromaSettings(allow_reset=True),
        )
        col = client.get_or_create_collection(collection_name, embedding_function=None)
        assert col.count() == 3

        all_data = col.get(include=["documents", "metadatas"])
        assert len(all_data["ids"]) == 3
        assert all_data["documents"][0] == "LDL cholesterol is bad for you."

        # Index metadata (embedding model / config hash provenance) must land
        # on the Chroma collection, as ChromaVectorStore.set_index_metadata does.
        assert col.metadata == {"experiment": "migration_test"}

    def test_migration_aborts_on_missing_json(self, tmp_path):
        from src.ingestion.indexing.migrate import migrate

        with pytest.raises(SystemExit):
            migrate(
                collection_name="nonexistent_collection",
                vector_dir=str(tmp_path / "nonexistent_dir"),
                chroma_dir=str(tmp_path / "chroma"),
            )

    def test_migration_aborts_on_array_length_mismatch(self, tmp_path):
        """Snapshots with mismatched ids/embeddings/documents must abort, not pad.

        The old implementation silently padded missing embeddings with [] and
        missing documents with '', corrupting the migrated collection.
        """
        from src.ingestion.indexing.migrate import migrate

        vector_dir = tmp_path / "vectors"
        vector_dir.mkdir()

        json_data = {
            "ids": ["doc1", "doc2"],
            "contents": ["Only one document for two ids."],
            "embeddings": [[0.1] * 8],
            "metadatas": [{"source": "a.pdf"}],
            "content_hashes": ["hash1"],
            "index_metadata": {},
        }
        json_file = vector_dir / "mismatched_collection.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f)

        with pytest.raises(SystemExit):
            migrate(
                collection_name="mismatched_collection",
                vector_dir=str(vector_dir),
                chroma_dir=str(tmp_path / "chroma"),
            )

    def test_migration_aborts_if_chroma_collection_has_data(self, tmp_path):
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        from src.ingestion.indexing.migrate import migrate

        vector_dir = tmp_path / "vectors"
        vector_dir.mkdir()
        chroma_dir = tmp_path / "chroma"

        client = chromadb.PersistentClient(
            path=str(chroma_dir),
            settings=ChromaSettings(allow_reset=True),
        )
        col = client.get_or_create_collection("existing_collection", embedding_function=None)
        col.add(
            ids=["already_exists"],
            embeddings=[[0.1] * 768],
            documents=["existing"],
            metadatas=[{"source": "x"}],
        )

        json_data = {
            "ids": ["new_doc"],
            "contents": ["New content."],
            "embeddings": [[0.2] * 768],
            "metadatas": [{"source": "y"}],
            "content_hashes": ["hash"],
            "index_metadata": {},
        }
        json_file = vector_dir / "existing_collection.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f)

        with pytest.raises(SystemExit):
            migrate(
                collection_name="existing_collection",
                vector_dir=str(vector_dir),
                chroma_dir=str(chroma_dir),
            )


class TestMigrationRoundTrip:
    """Migrated docs must round-trip identically to pipeline-written docs.

    Regression guard for the metadata-loss bug: the old migration dropped
    list-valued metadata (section_path, hypothetical_questions,
    extracted_keywords), silently disabling HyPE retrieval and the
    extracted-keywords BM25 boost for migrated data.
    """

    def test_migrated_docs_behave_like_pipeline_written_docs(
        self, tmp_path, fake_chroma_embeddings
    ):
        from src.ingestion.indexing.chroma_store import ChromaVectorStore
        from src.ingestion.indexing.migrate import migrate

        vector_dir = tmp_path / "legacy"
        vector_dir.mkdir()
        chroma_dir = tmp_path / "chroma"  # same dir the fixture isolates settings to

        docs = [
            {
                "id": "doc_hype",
                "content": "Statin therapy reduces LDL cholesterol in dyslipidaemia patients.",
                "source": "esc_2019.pdf",
                "page": 3,
                "section_path": ["Dyslipidaemias", "Management"],
                "metadata": {
                    "logical_name": "ESC/EAS 2019",
                    "hypothetical_questions": [
                        "How do statins affect LDL cholesterol?",
                        "What therapy reduces LDL in dyslipidaemia?",
                    ],
                    "extracted_keywords": ["Statin", "LDL", "Cholesterol"],
                },
            },
            {
                "id": "doc_plain",
                "content": "Blood pressure targets differ by cardiovascular risk profile.",
                "source": "esc_2018.pdf",
                "page": 7,
            },
        ]

        pipeline_store = ChromaVectorStore(collection_name="rt_pipeline")
        migrated_store = None
        try:
            pipeline_store.clear()
            pipeline_store.set_index_metadata(
                {"embedding_model": "offline-stub", "config_hash": "abc123"}
            )
            pipeline_store.add_documents(docs)

            # Export exactly what the legacy JSON snapshot machinery wrote.
            legacy_payload = pipeline_store.documents
            legacy_payload["content_hashes"] = sorted(pipeline_store.content_hashes)
            json_file = vector_dir / "rt_migrated.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(legacy_payload, f, ensure_ascii=False)

            report = migrate(
                collection_name="rt_migrated",
                vector_dir=str(vector_dir),
                chroma_dir=str(chroma_dir),
            )
            assert report["inserted"] == 2

            migrated_store = ChromaVectorStore(collection_name="rt_migrated")

            def snapshot(store):
                res = store._collection.get(include=["documents", "metadatas", "embeddings"])
                order = sorted(range(len(res["ids"])), key=lambda i: res["ids"][i])
                return {
                    "ids": [res["ids"][i] for i in order],
                    "documents": [res["documents"][i] for i in order],
                    "metadatas": [res["metadatas"][i] for i in order],
                    "embeddings": [res["embeddings"][i] for i in order],
                }

            expected = snapshot(pipeline_store)
            actual = snapshot(migrated_store)

            # Storage-level parity: identical ids, documents, embeddings, and
            # metadata — including the native list fields the old migration
            # dropped and the recomputed content_hash.
            assert actual["ids"] == expected["ids"]
            assert actual["documents"] == expected["documents"]
            assert actual["metadatas"] == expected["metadatas"]
            for got, want in zip(actual["embeddings"], expected["embeddings"], strict=True):
                assert list(got) == pytest.approx(list(want))

            hype_meta = next(m for m in actual["metadatas"] if m.get("hypothetical_questions"))
            assert isinstance(hype_meta["hypothetical_questions"], list)
            assert isinstance(hype_meta["extracted_keywords"], list)
            assert isinstance(hype_meta["section_path"], list)

            # Index metadata provenance survived (read back the way l5 does).
            assert dict(migrated_store._collection.metadata or {}) == {
                "embedding_model": "offline-stub",
                "config_hash": "abc123",
            }

            # Behavioral parity: HyPE retrieval + keyword/BM25 boost.
            query = "How do statins affect LDL cholesterol?"
            assert migrated_store.search_hypothetical_questions(query) == (
                pipeline_store.search_hypothetical_questions(query)
            )
            assert migrated_store.get_hypothetical_questions()["doc_hype"] == [
                "How do statins affect LDL cholesterol?",
                "What therapy reduces LDL in dyslipidaemia?",
            ]

            for mode in ("bm25_only", "semantic_only", "rrf_hybrid"):
                m_res, _ = migrated_store.similarity_search_with_trace(
                    query, top_k=2, search_mode=mode
                )
                p_res, _ = pipeline_store.similarity_search_with_trace(
                    query, top_k=2, search_mode=mode
                )
                assert [r["id"] for r in m_res] == [r["id"] for r in p_res]
                assert [r["keyword_score"] for r in m_res] == [r["keyword_score"] for r in p_res]
                assert [r["semantic_score"] for r in m_res] == [r["semantic_score"] for r in p_res]
        finally:
            pipeline_store.clear()
            if migrated_store is not None:
                migrated_store.clear()
