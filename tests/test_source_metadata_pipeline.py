import json

from src.evals.checks.l5_index import assess_l5_index_quality
from src.ingestion.indexing.vector_store import VectorStore


def test_vector_store_preserves_source_metadata_and_l5_distributions(tmp_path):
    vector_dir = tmp_path / "vectors"
    vector_dir.mkdir()
    store = VectorStore(collection_name="test_source_metadata")
    store.embeddings_file = vector_dir / "test_source_metadata.json"
    store.clear()

    def fake_embed_with_stats(texts, batch_size=10):
        return [[0.1, 0.2, 0.3] for _ in texts], {"provider": "fake", "batch_size": batch_size}

    store._embed_with_stats = fake_embed_with_stats  # type: ignore[method-assign]
    store._embed = lambda texts, batch_size=10: [[0.1, 0.2, 0.3] for _ in texts]  # type: ignore[method-assign]

    store.add_documents(
        [
            {
                "id": "pdf1",
                "content": "pdf chunk",
                "source": "guide.pdf",
                "page": 1,
                "source_type": "pdf",
                "source_class": "guideline_pdf",
                "metadata": {
                    "logical_name": "Guide PDF",
                    "source_url": "https://example.org/guide.pdf",
                    "domain": "example.org",
                    "domain_type": "organization",
                },
            },
            {
                "id": "csv1",
                "content": "csv chunk",
                "source": "reference_ranges.csv",
                "source_type": "reference_csv",
                "source_class": "reference_csv",
                "metadata": {"logical_name": "Lab reference ranges"},
            },
        ]
    )

    results = store.similarity_search("guide", top_k=2)
    assert results
    assert results[0]["metadata"]["source_type"] in {"pdf", "reference_csv"}
    assert "canonical_label" in results[0]["metadata"]

    report = assess_l5_index_quality(vector_dir=vector_dir, collection_name="test_source_metadata")

    assert report["aggregate"]["source_type_distribution"]["pdf"] == 1
    assert report["aggregate"]["source_type_distribution"]["reference_csv"] == 1
    assert report["aggregate"]["source_class_distribution"]["guideline_pdf"] == 1
    assert report["aggregate"]["source_class_distribution"]["reference_csv"] == 1

    payload = json.loads((vector_dir / "test_source_metadata.json").read_text(encoding="utf-8"))
    first_meta = payload["metadatas"][0]
    assert first_meta["canonical_label"] == "Guide PDF"
    assert first_meta["source_url"] == "https://example.org/guide.pdf"
    assert first_meta["source_type"] == "pdf"
