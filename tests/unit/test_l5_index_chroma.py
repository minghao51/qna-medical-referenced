"""Unit tests that the L5 index check reads the ChromaDB store (not legacy JSON)."""

from pathlib import Path

import pytest

from src.config import settings
from src.evals.checks.l5_index import assess_l5_index_quality
from src.ingestion.indexing.chroma_store import ChromaVectorStoreFactory
from src.ingestion.indexing.vector_store import VectorStore

TEST_COLLECTION = "test_l5_chroma_unit"


@pytest.fixture
def chroma_store(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings.storage, "chroma_persist_directory", str(tmp_path / "chroma"))
    monkeypatch.setattr(settings.storage, "chroma_server_host", "")
    ChromaVectorStoreFactory.reset()
    store = VectorStore(collection_name=TEST_COLLECTION)
    store.clear()

    def fake_embed_with_stats(texts, batch_size=10, model=None):
        return [[0.1, 0.2, 0.3] for _ in texts], {
            "provider": "fake",
            "batch_size": batch_size,
        }

    store._embed_with_stats = fake_embed_with_stats
    yield store
    ChromaVectorStoreFactory.reset()


def test_l5_reports_missing_collection(tmp_path, monkeypatch):
    monkeypatch.setattr(settings.storage, "chroma_persist_directory", str(tmp_path / "missing"))
    monkeypatch.setattr(settings.storage, "chroma_server_host", "")
    ChromaVectorStoreFactory.reset()
    try:
        report = assess_l5_index_quality(collection_name="no_such_collection")
    finally:
        ChromaVectorStoreFactory.reset()

    assert report["aggregate"]["index_exists"] is False
    assert report["records"] == []
    assert report["findings"][0]["severity"] == "warning"
    assert report["findings"][0]["stage"] == "L5"


def test_l5_reads_document_counts_and_metadata_from_chroma(chroma_store, tmp_path):
    chroma_store.add_documents(
        [
            {
                "id": "pdf1",
                "content": "pdf chunk content",
                "source": "guide.pdf",
                "page": 1,
                "source_type": "pdf",
                "source_class": "guideline_pdf",
                "metadata": {"logical_name": "Guide PDF"},
            },
            {
                "id": "csv1",
                "content": "csv chunk content",
                "source": "reference_ranges.csv",
                "source_type": "reference_csv",
                "source_class": "reference_csv",
                "metadata": {"logical_name": "Lab reference ranges"},
            },
        ]
    )

    report = assess_l5_index_quality(
        vector_dir=tmp_path / "vectors", collection_name=TEST_COLLECTION
    )

    agg = report["aggregate"]
    assert agg["index_exists"] is True
    assert agg["ids_count"] == 2
    assert agg["contents_count"] == 2
    assert agg["embeddings_count"] == 2
    assert agg["metadatas_count"] == 2
    assert agg["lengths_consistent"] is True
    assert agg["embedding_dim_consistent"] is True
    assert agg["embedding_dim"] == 3
    assert agg["source_type_distribution"]["pdf"] == 1
    assert agg["source_type_distribution"]["reference_csv"] == 1
    assert agg["source_class_distribution"]["guideline_pdf"] == 1
    assert agg["source_class_distribution"]["reference_csv"] == 1
    assert agg["vector_path"]
    assert len(report["records"]) == 2
    assert report["findings"] == []
