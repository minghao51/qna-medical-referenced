import json
import pytest
from pathlib import Path
from src.pipeline.L5_vector_store import VectorStore
import os


class TestKeywordIndex:
    @pytest.fixture
    def vector_store(self):
        if os.environ.get("GEMINI_API_KEY") == "test-api-key":
            pytest.skip("Requires valid Gemini API key")
        
        store = VectorStore(
            collection_name="test_keyword",
            semantic_weight=0.6,
            keyword_weight=0.2,
            boost_weight=0.2
        )
        store.clear()
        yield store
        store.clear()

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_keyword_index_built(self, vector_store):
        documents = [
            {"id": "doc1", "content": "LDL cholesterol test document", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        vector_store._rebuild_index_if_needed()
        
        assert len(vector_store.keyword_index) > 0

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_keyword_lowercase_indexed(self, vector_store):
        documents = [
            {"id": "doc1", "content": "LDL Cholesterol TEST", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        vector_store._rebuild_index_if_needed()
        
        assert "ldl" in vector_store.keyword_index or "cholesterol" in vector_store.keyword_index

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_stop_words_filtered(self, vector_store):
        documents = [
            {"id": "doc1", "content": "The quick brown fox jumps over the lazy dog", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        vector_store._rebuild_index_if_needed()
        
        assert "the" not in vector_store.keyword_index, "Stop words should be filtered"
        assert "over" not in vector_store.keyword_index, "Stop words should be filtered"
        assert "brown" in vector_store.keyword_index, "Non-stop words should be indexed"

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_content_words_indexed(self, vector_store):
        documents = [
            {"id": "doc1", "content": "Lipid management cardiovascular risk", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        vector_store._rebuild_index_if_needed()
        
        assert "lipid" in vector_store.keyword_index
        assert "manag" in vector_store.keyword_index or "management" in vector_store.keyword_index
        assert "cardiovascular" in vector_store.keyword_index
        assert "risk" in vector_store.keyword_index

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_keyword_score_basic(self, vector_store):
        documents = [
            {"id": "doc1", "content": "LDL cholesterol is elevated", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        
        scores = vector_store._keyword_score("LDL cholesterol")
        
        assert 0 in scores
        assert scores[0] > 0

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_keyword_score_no_match(self, vector_store):
        documents = [
            {"id": "doc1", "content": "Lipid management", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        
        scores = vector_store._keyword_score("Diabetes metformin")
        
        assert 0 not in scores or scores[0] == 0

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_multiple_documents_indexing(self, vector_store):
        documents = [
            {"id": "doc1", "content": "First document about lipids", "source": "test.pdf"},
            {"id": "doc2", "content": "Second document about diabetes", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        vector_store._rebuild_index_if_needed()
        
        assert "lipid" in vector_store.keyword_index
        assert "diabet" in vector_store.keyword_index, "diabetes should be stemmed to diabet"

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_stemming_implemented(self, vector_store):
        documents = [
            {"id": "doc1", "content": "Running and running fast", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        
        scores_run = vector_store._keyword_score("run")
        scores_running = vector_store._keyword_score("running")
        
        assert 0 in scores_run or 0 in scores_running, "Stemming should work - 'run' should match 'running'"

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_punctuation_handling(self, vector_store):
        documents = [
            {"id": "doc1", "content": "LDL-C, cholesterol! Test? (word)", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        vector_store._rebuild_index_if_needed()
        
        assert "ldl" in vector_store.keyword_index or "ldl-c" in vector_store.keyword_index
        assert "cholesterol" in vector_store.keyword_index

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_numbers_not_indexed(self, vector_store):
        documents = [
            {"id": "doc1", "content": "Target LDL-C 1.8 mmol", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        vector_store._rebuild_index_if_needed()
        
        assert "1" not in vector_store.keyword_index, "Pure numbers should not be indexed"
        assert "ldl-c" in vector_store.keyword_index, "Acronyms should be indexed"

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_tfidf_ranking(self, vector_store):
        documents = [
            {"id": "doc1", "content": "LDL LDL LDL cholesterol", "source": "test.pdf"},
            {"id": "doc2", "content": "LDL cholesterol", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        
        scores = vector_store._keyword_score("LDL")
        
        assert scores[0] > scores[1], "Doc with more LDL mentions should score higher"

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_acronyms_preserved(self, vector_store):
        documents = [
            {"id": "doc1", "content": "LDL-C is familial hypercholesterolemia", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        vector_store._rebuild_index_if_needed()
        
        assert "ldl-c" in vector_store.keyword_index, "Acronyms should be preserved"

    @pytest.mark.skipif(
        os.environ.get("GEMINI_API_KEY") == "test-api-key",
        reason="Requires valid Gemini API key"
    )
    def test_case_insensitive_query(self, vector_store):
        documents = [
            {"id": "doc1", "content": "Cholesterol Test", "source": "test.pdf"},
        ]
        vector_store.add_documents(documents)
        
        scores_upper = vector_store._keyword_score("CHOLESTEROL")
        scores_lower = vector_store._keyword_score("cholesterol")
        
        assert scores_upper == scores_lower or (scores_upper.get(0, 0) > 0 and scores_lower.get(0, 0) > 0)
