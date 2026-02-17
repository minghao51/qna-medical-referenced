import json
import pytest
from pathlib import Path
from src.vectorstore.store import VectorStore
import os


class TestRetrieval:
    @pytest.fixture
    def vector_store(self):
        if os.environ.get("GEMINI_API_KEY") == "test-api-key":
            pytest.skip("Requires valid Gemini API key")
        
        store = VectorStore(
            collection_name="test_retrieval",
            semantic_weight=0.6,
            keyword_weight=0.2,
            boost_weight=0.2
        )
        store.clear()
        
        test_docs = [
            {"id": "lipid_doc", "content": "LDL cholesterol target for secondary prevention is less than 1.8 mmol/L. Statins are first-line therapy.", "source": "lipid.pdf", "page": 1},
            {"id": "diabetes_doc", "content": "Pre-diabetes management includes lifestyle modification. Metformin may be considered if BMI is 23 or higher.", "source": "diabetes.pdf", "page": 1},
            {"id": "cv_risk_doc", "content": "Cardiovascular risk assessment includes risk enhancers. Family history is an important factor.", "source": "cv.pdf", "page": 1},
            {"id": "diet_doc", "content": "Dietary recommendations include vegetables, fruits, and whole grains. Avoid saturated fats.", "source": "diet.pdf", "page": 1},
            {"id": "generic_doc", "content": "General health information about various medical conditions and treatments.", "source": "general.pdf", "page": 1},
        ]
        store.add_documents(test_docs)
        
        yield store
        store.clear()

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_similarity_search_returns_results(self, vector_store):
        results = vector_store.similarity_search("LDL cholesterol", top_k=3)
        
        assert len(results) > 0
        assert len(results) <= 3

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_recall_at_5(self, vector_store):
        test_queries = [
            {"query": "LDL cholesterol target", "expected_id": "lipid_doc"},
            {"query": "pre-diabetes metformin BMI", "expected_id": "diabetes_doc"},
            {"query": "cardiovascular risk factors", "expected_id": "cv_risk_doc"},
            {"query": "diet vegetables fruits", "expected_id": "diet_doc"},
        ]
        
        recalls = []
        for tq in test_queries:
            results = vector_store.similarity_search(tq["query"], top_k=5)
            result_ids = [r["id"] for r in results]
            recall = 1 if tq["expected_id"] in result_ids else 0
            recalls.append(recall)
        
        recall_at_5 = sum(recalls) / len(recalls)
        print(f"\nRecall@5: {recall_at_5:.2f}")
        assert recall_at_5 >= 0.5, f"Recall@5 should be >= 0.5, got {recall_at_5}"

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_mean_reciprocal_rank(self, vector_store):
        test_queries = [
            {"query": "LDL cholesterol", "expected_id": "lipid_doc"},
            {"query": "pre-diabetes", "expected_id": "diabetes_doc"},
            {"query": "cardiovascular risk", "expected_id": "cv_risk_doc"},
            {"query": "diet recommendations", "expected_id": "diet_doc"},
        ]
        
        reciprocal_ranks = []
        for tq in test_queries:
            results = vector_store.similarity_search(tq["query"], top_k=5)
            result_ids = [r["id"] for r in results]
            
            if tq["expected_id"] in result_ids:
                rank = result_ids.index(tq["expected_id"]) + 1
                reciprocal_ranks.append(1.0 / rank)
            else:
                reciprocal_ranks.append(0.0)
        
        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
        print(f"\nMRR: {mrr:.2f}")
        assert mrr > 0

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_hybrid_vs_keyword_only(self, vector_store):
        query = "LDL cholesterol"
        
        hybrid_results = vector_store.similarity_search(query, top_k=5, hybrid=True)
        keyword_results = vector_store.similarity_search(query, top_k=5, hybrid=False)
        
        assert len(hybrid_results) > 0
        assert len(keyword_results) > 0

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_hybrid_vs_semantic_only(self, vector_store):
        store_no_hybrid = VectorStore(
            collection_name="test_retrieval",
            semantic_weight=1.0,
            keyword_weight=0.0,
            boost_weight=0.0
        )
        store_no_hybrid.clear()
        
        test_docs = [
            {"id": "doc1", "content": "LDL cholesterol target", "source": "test.pdf"},
            {"id": "doc2", "content": "Unrelated content", "source": "test.pdf"},
        ]
        store_no_hybrid.add_documents(test_docs)
        
        results = store_no_hybrid.similarity_search("cholesterol", top_k=1, hybrid=False)
        
        assert results[0]["id"] == "doc1"
        
        store_no_hybrid.clear()

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_acronym_query_favors_keyword(self, vector_store):
        store = VectorStore(
            collection_name="test_acronym",
            semantic_weight=0.3,
            keyword_weight=0.5,
            boost_weight=0.2
        )
        store.clear()
        
        test_docs = [
            {"id": "fh_doc", "content": "FH is familial hypercholesterolemia. Genetic testing is recommended.", "source": "test.pdf"},
            {"id": "other_doc", "content": "General health information", "source": "test.pdf"},
        ]
        store.add_documents(test_docs)
        
        results = store.similarity_search("FH genetic", top_k=1)
        
        assert results[0]["id"] == "fh_doc"
        
        store.clear()

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_synonym_query_favors_semantic(self, vector_store):
        results = vector_store.similarity_search("heart disease prevention", top_k=3)
        
        assert len(results) > 0

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_top_k_parameter(self, vector_store):
        results_1 = vector_store.similarity_search("cholesterol", top_k=1)
        results_3 = vector_store.similarity_search("cholesterol", top_k=3)
        
        assert len(results_1) == 1
        assert len(results_3) == 3

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_results_have_required_fields(self, vector_store):
        results = vector_store.similarity_search("test", top_k=1)
        
        for r in results:
            assert "id" in r
            assert "content" in r
            assert "source" in r
            assert "score" in r

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_score_ordering(self, vector_store):
        results = vector_store.similarity_search("cholesterol", top_k=5)
        
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_empty_query_handling(self, vector_store):
        results = vector_store.similarity_search("", top_k=5)
        
        assert isinstance(results, list)

    def test_empty_store_handling(self):
        store = VectorStore(
            collection_name="test_empty",
            semantic_weight=0.6,
            keyword_weight=0.2,
            boost_weight=0.2
        )
        store.clear()
        
        results = store.similarity_search("any query", top_k=5)
        
        assert results == []
        
        store.clear()

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_weight_parameterization(self, vector_store):
        store_semantic = VectorStore(
            collection_name="test_weights_sem",
            semantic_weight=1.0,
            keyword_weight=0.0,
            boost_weight=0.0
        )
        store_semantic.clear()
        
        store_semantic.add_documents([
            {"id": "match", "content": "exact match keyword", "source": "test.pdf"},
            {"id": "semantic", "content": "similar meaning text", "source": "test.pdf"},
        ])
        
        results = store_semantic.similarity_search("keyword", top_k=2, hybrid=True)
        
        assert len(results) >= 1
        
        store_semantic.clear()
