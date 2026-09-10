"""Tests for ChromaVectorStore hybrid search and metadata filtering."""

from __future__ import annotations

import pytest

from src.ingestion.indexing.store import _FILTERED_PAGE_SIZE, ChromaVectorStore


# No live_api gate: the Qwen embedding API is stubbed via the
# fake_chroma_embeddings fixture; ChromaDB itself runs for real.
@pytest.fixture(autouse=True)
def _offline_embeddings(fake_chroma_embeddings):
    """Deterministic offline embeddings for every test in this module."""


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

    def test_keyword_score_computed_once_per_traced_query(self, store):
        """The traced path must not run BM25 twice for the same query."""
        calls = {"count": 0}
        original = store._keyword_score

        def counting(query):
            calls["count"] += 1
            return original(query)

        store._keyword_score = counting
        try:
            _, trace = store.similarity_search_with_trace(
                "cholesterol", top_k=3, search_mode="rrf_hybrid"
            )
        finally:
            del store._keyword_score
        assert calls["count"] == 1
        assert "keyword_timing_ms" in trace


class TestFilteredUnfilteredConsistency:
    """A filter matching the whole corpus must not change rankings."""

    @pytest.fixture
    def store(self):
        s = ChromaVectorStore(collection_name="test_chroma_filter_consistency")
        s.clear()
        s.add_documents(
            [
                {
                    "id": "plain_doc",
                    "content": "Aspirin therapy reduces fever and mild pain in adults.",
                    "source": "plain.pdf",
                    "page": 1,
                },
                {
                    "id": "keyword_doc",
                    "content": "Aspirin dosing guidance for secondary prevention.",
                    "source": "kw.pdf",
                    "page": 1,
                    "metadata": {"extracted_keywords": ["Aspirin", "Fever"]},
                },
            ]
        )
        yield s
        s.clear()

    def test_bm25_ranking_identical_with_and_without_filter(self, store):
        query = "aspirin fever"
        unfiltered, _ = store.similarity_search_with_trace(query, top_k=2, search_mode="bm25_only")
        filtered, _ = store.similarity_search_with_trace(
            query, top_k=2, search_mode="bm25_only", filter={"page": 1}
        )
        # The extracted-keywords BM25 boost applies to filtered queries too,
        # so the same candidate set ranks identically.
        assert [r["id"] for r in filtered] == [r["id"] for r in unfiltered]
        assert [r["keyword_score"] for r in filtered] == [r["keyword_score"] for r in unfiltered]

    def test_semantic_ranking_identical_with_and_without_filter(self, store):
        query = "aspirin fever"
        unfiltered, _ = store.similarity_search_with_trace(
            query, top_k=2, search_mode="semantic_only"
        )
        filtered, _ = store.similarity_search_with_trace(
            query, top_k=2, search_mode="semantic_only", filter={"page": 1}
        )
        assert [r["id"] for r in filtered] == [r["id"] for r in unfiltered]
        assert [r["semantic_score"] for r in filtered] == [r["semantic_score"] for r in unfiltered]


class TestFilteredSearchPagination:
    """Filtered candidate sets must not be truncated at one page."""

    def test_filtered_search_beyond_page_cap(self):
        store = ChromaVectorStore(collection_name="test_chroma_pagination")
        store.clear()
        total_docs = _FILTERED_PAGE_SIZE + 1
        docs = [
            {
                "id": f"bulk_{i}",
                "content": f"Bulk document number {i} about generic topics.",
                "source": "bulk.pdf",
                "page": 1,
            }
            for i in range(total_docs)
        ]
        store.add_documents(docs)
        try:
            results = store.similarity_search(
                "bulk document generic",
                top_k=total_docs,
                search_mode="bm25_only",
                filter={"source": "bulk.pdf"},
            )
            assert len(results) == total_docs
            ids = [r["id"] for r in results]
            assert len(set(ids)) == total_docs

            # Same collection via the semantic filtered path: the full
            # candidate set is fetched (paginated) and ranked.
            semantic = store.similarity_search(
                "bulk document generic",
                top_k=total_docs,
                search_mode="semantic_only",
                filter={"source": "bulk.pdf"},
            )
            assert len(semantic) == total_docs
        finally:
            store.clear()


class TestHypotheticalQuestionCache:
    @pytest.fixture
    def store(self):
        s = ChromaVectorStore(collection_name="test_chroma_hype_cache")
        s.clear()
        yield s
        s.clear()

    def test_stored_questions_not_retokenized_per_query(self, store):
        store.add_documents(
            [
                {
                    "id": "hype_cache_doc",
                    "content": "Content about statins.",
                    "source": "hype_cache.pdf",
                    "metadata": {
                        "hypothetical_questions": [
                            "What is the recommended statin dosage?",
                            "When should statins be prescribed?",
                        ]
                    },
                }
            ]
        )
        calls = {"count": 0}
        original = store._tokenize

        def counting(text):
            calls["count"] += 1
            return original(text)

        store._tokenize = counting
        try:
            store.search_hypothetical_questions("statin dosage")
            after_first = calls["count"]
            store.search_hypothetical_questions("statin dosage")
        finally:
            del store._tokenize
        # Only the query is tokenized per search; the stored questions were
        # tokenized once when the cache was built.
        assert after_first == 1
        assert calls["count"] == 2


class TestListDocumentsPaginated:
    def test_totals_and_counts_without_second_fetch(self):
        store = ChromaVectorStore(collection_name="test_chroma_paged_totals")
        store.clear()
        store.add_documents(
            [
                {
                    "id": "pdf1",
                    "content": "Pdf one content.",
                    "source": "a.pdf",
                    "metadata": {"source_type": "pdf"},
                },
                {
                    "id": "csv1",
                    "content": "Csv one content.",
                    "source": "b.csv",
                    "metadata": {"source_type": "csv"},
                },
                {
                    "id": "pdf2",
                    "content": "Pdf two content.",
                    "source": "c.pdf",
                    "metadata": {"source_type": "pdf"},
                },
            ]
        )
        try:
            all_page = store.list_documents_paginated(limit=2, offset=0)
            assert all_page["total"] == 3
            assert len(all_page["items"]) == 2
            assert all_page["source_type_counts"] == {"pdf": 2, "csv": 1}

            pdf_page = store.list_documents_paginated(limit=10, offset=0, source_type="pdf")
            assert pdf_page["total"] == 2
            assert {item["id"] for item in pdf_page["items"]} == {"pdf1", "pdf2"}
            assert pdf_page["source_type_counts"] == {"pdf": 2}

            second_page = store.list_documents_paginated(limit=2, offset=2)
            assert second_page["total"] == 3
            assert len(second_page["items"]) == 1
        finally:
            store.clear()


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
