"""Tests for the JSON → ChromaDB migration script."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


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
        assert report["skipped_duplicate_id"] == 0

        client = chromadb.PersistentClient(
            path=str(chroma_dir),
            settings=ChromaSettings(allow_reset=True),
        )
        col = client.get_or_create_collection(collection_name, embedding_function=None)
        assert col.count() == 3

        all_data = col.get(include=["documents", "metadatas"])
        assert len(all_data["ids"]) == 3
        assert all_data["documents"][0] == "LDL cholesterol is bad for you."

    def test_migration_aborts_on_missing_json(self, tmp_path):
        from src.ingestion.indexing.migrate import migrate

        with pytest.raises(SystemExit):
            migrate(
                collection_name="nonexistent_collection",
                vector_dir=str(tmp_path / "nonexistent_dir"),
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
        col.add(ids=["already_exists"], embeddings=[[0.1] * 768], documents=["existing"], metadatas=[{"source": "x"}])

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
