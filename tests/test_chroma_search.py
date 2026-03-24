"""Tests for ChromaVectorStore hybrid search and metadata filtering."""

from __future__ import annotations

import pytest

from src.ingestion.indexing.chroma_store import ChromaVectorStore

pytestmark = pytest.mark.live_api


class TestChromaSearch:
    @pytest.fixture
    def store(self):
        s = ChromaVectorStore(
            collection_name="test_chroma_search",
            semantic_weight=0.6,
            keyword_weight=0.2,
            boost_weight=0.2,
        )
        s.clear()
        s.add_documents(
            [
                {
                    "id": "lipid_doc",
                    "content": "LDL cholesterol target for secondary prevention is less than 1.8 mmol/L. Statins are first-line therapy.",
                    "source": "lipid.pdf",
                    "page": 1,
                },
                {
                    "id": "diabetes_doc",
                    "content": "Pre-diabetes management includes lifestyle modification. Metformin may be considered if BMI is 23 or higher.",
                    "source": "diabetes.pdf",
                    "page": 1,
                },
                {
                    "id": "cv_risk_doc",
                    "content": "Cardiovascular risk assessment includes risk enhancers. Family history is an important factor.",
                    "source": "cv.pdf",
                    "page": 1,
                },
                {
                    "id": "diet_doc",
                    "content": "Dietary recommendations include vegetables, fruits, and whole grains. Avoid saturated fats.",
                    "source": "diet.pdf",
                    "page": 1,
                },
                {
                    "id": "generic_doc",
                    "content": "General health information about various medical conditions and treatments.",
                    "source": "general.pdf",
                    "page": 1,
                },
            ]
        )
        yield s
        s.clear()

    def test_similarity_search_returns_results(self, store):
        results = store.similarity_search("LDL cholesterol", top_k=3)
        assert len(results) > 0
        assert len(results) <= 3

    def test_similarity_search_top_k(self, store):
        results = store.similarity_search("cholesterol", top_k=2)
        assert len(results) <= 2

    def test_similarity_search_result_has_required_fields(self, store):
        results = store.similarity_search("cholesterol", top_k=1)
        assert len(results) > 0
        r = results[0]
        assert "id" in r
        assert "content" in r
        assert "source" in r
        assert "score" in r
        assert "semantic_rank" in r or "bm25_rank" in r

    def test_similarity_search_with_filter(self, store):
        results = store.similarity_search(
            "cholesterol cardiovascular",
            top_k=5,
            filter={"source": "lipid.pdf"},
        )
        for r in results:
            assert r["source"] == "lipid.pdf"

    def test_filter_with_no_match_returns_empty_or_filtered(self, store):
        results = store.similarity_search(
            "cholesterol",
            top_k=5,
            filter={"source": "nonexistent_file.pdf"},
        )
        assert all(r["source"] == "nonexistent_file.pdf" for r in results)

    def test_semantic_only_search(self, store):
        results = store.similarity_search(
            "statin therapy",
            top_k=3,
            hybrid=False,
            search_mode="semantic_only",
        )
        assert len(results) > 0
        for r in results:
            assert r["semantic_rank"] is not None
            assert r["bm25_rank"] is None

    def test_bm25_only_search(self, store):
        results = store.similarity_search(
            "cholesterol",
            top_k=3,
            hybrid=False,
            search_mode="bm25_only",
        )
        assert len(results) > 0
        for r in results:
            assert r["bm25_rank"] is not None
            assert r["semantic_rank"] is None

    def test_hybrid_rrf_search(self, store):
        results = store.similarity_search(
            "LDL cholesterol statins",
            top_k=5,
            hybrid=True,
            search_mode="rrf_hybrid",
        )
        assert len(results) > 0

    def test_hypothetical_questions_retrieval(self, store):
        store.add_documents(
            [
                {
                    "id": "hype_doc",
                    "content": "This document discusses lipid management.",
                    "source": "hype_test.pdf",
                    "metadata": {
                        "hypothetical_questions": [
                            "What is the LDL target?",
                            "Which statins are recommended?",
                        ]
                    },
                }
            ]
        )
        hype_map = store.get_hypothetical_questions()
        assert "hype_doc" in hype_map
        assert "What is the LDL target?" in hype_map["hype_doc"]

    def test_search_hypothetical_questions(self, store):
        store.add_documents(
            [
                {
                    "id": "hype_doc2",
                    "content": "Content about statins.",
                    "source": "hype_test2.pdf",
                    "metadata": {
                        "hypothetical_questions": [
                            "What is the recommended statin dosage?",
                            "When should statins be prescribed?",
                        ]
                    },
                }
            ]
        )
        questions = store.search_hypothetical_questions("statin dosage", limit=2)
        assert len(questions) <= 2

    def test_empty_query_returns_empty_or_all(self, store):
        results = store.similarity_search("", top_k=5)
        assert isinstance(results, list)


class TestChromaMetadataFields:
    @pytest.fixture
    def store(self):
        s = ChromaVectorStore(collection_name="test_chroma_metadata")
        s.clear()
        s.add_documents(
            [
                {
                    "id": "meta_doc1",
                    "content": "Guideline content about lipids.",
                    "source": "guideline.pdf",
                    "metadata": {
                        "source_type": "pdf",
                        "source_class": "guideline_pdf",
                        "domain": "lipid",
                        "quality_score": 0.9,
                    },
                    "page": 1,
                },
                {
                    "id": "meta_doc2",
                    "content": "Reference content about diabetes.",
                    "source": "reference.csv",
                    "metadata": {
                        "source_type": "csv",
                        "source_class": "reference_csv",
                        "domain": "diabetes",
                        "quality_score": 0.7,
                    },
                    "page": 1,
                },
            ]
        )
        yield s
        s.clear()

    def test_filter_by_source_class(self, store):
        results = store.similarity_search(
            "content",
            top_k=5,
            filter={"source_class": "guideline_pdf"},
        )
        for r in results:
            assert r["source_class"] == "guideline_pdf"

    def test_filter_by_domain(self, store):
        results = store.similarity_search(
            "content",
            top_k=5,
            filter={"domain": "diabetes"},
        )
        for r in results:
            assert r["domain"] == "diabetes"

    def test_filter_with_set_membership(self, store):
        results = store.similarity_search(
            "content",
            top_k=5,
            filter={"source_class": {"$in": ["guideline_pdf", "reference_csv"]}},
        )
        for r in results:
            assert r["source_class"] in ["guideline_pdf", "reference_csv"]

    def test_filter_with_quality_threshold(self, store):
        results = store.similarity_search(
            "content",
            top_k=5,
            filter={"quality_score": {"$gte": 0.8}},
        )
        for r in results:
            assert r["quality_score"] >= 0.8
