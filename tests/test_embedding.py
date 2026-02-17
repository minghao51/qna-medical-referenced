import json
import time
import pytest
from pathlib import Path
from src.vectorstore.store import VectorStore
import os


GEMINI_EMBEDDING_DIM = 3072

requires_api_key = pytest.mark.skipif(
    os.environ.get("GEMINI_API_KEY") == "test-api-key",
    reason="Requires valid Gemini API key"
)


class TestEmbedding:
    @pytest.fixture
    def vector_store(self):
        if os.environ.get("GEMINI_API_KEY") == "test-api-key":
            pytest.skip("Requires valid Gemini API key")
        
        store = VectorStore(
            collection_name="test_embedding",
            semantic_weight=0.6,
            keyword_weight=0.2,
            boost_weight=0.2
        )
        store.clear()
        yield store
        store.clear()

    @requires_api_key
    def test_embedding_dimension(self, vector_store):
        texts = ["Test sentence for embedding dimension"]
        embeddings = vector_store._embed(texts)
        
        assert len(embeddings) == 1
        assert len(embeddings[0]) == GEMINI_EMBEDDING_DIM, f"Expected {GEMINI_EMBEDDING_DIM} dimensions"

    @requires_api_key
    def test_batch_embedding_dimension(self, vector_store):
        texts = [f"Test sentence number {i}" for i in range(10)]
        embeddings = vector_store._embed(texts)
        
        assert len(embeddings) == 10
        for emb in embeddings:
            assert len(emb) == GEMINI_EMBEDDING_DIM

    @requires_api_key
    def test_embedding_consistency(self, vector_store):
        text = "Consistent embedding test"
        
        emb1 = vector_store._embed([text])[0]
        emb2 = vector_store._embed([text])[0]
        
        assert emb1 == emb2, "Same text should produce same embedding"

    @requires_api_key
    def test_different_texts_different_embeddings(self, vector_store):
        texts = ["First text", "Second text"]
        embeddings = vector_store._embed(texts)
        
        assert embeddings[0] != embeddings[1], "Different texts should have different embeddings"

    @requires_api_key
    def test_batch_latency_100_chunks(self, vector_store):
        texts = [f"Medical document chunk number {i} with relevant content about lipid management and cardiovascular risk." for i in range(100)]
        
        start = time.time()
        embeddings = vector_store._embed(texts)
        elapsed = time.time() - start
        
        assert len(embeddings) == 100
        print(f"\n100 chunks embedding time: {elapsed:.2f}s")
        assert elapsed < 60, "100 chunks should embed in under 60 seconds"

    @requires_api_key
    def test_batch_latency_1000_chunks(self, vector_store):
        texts = [f"Medical document chunk number {i} about diabetes prevention and treatment." for i in range(1000)]
        
        start = time.time()
        embeddings = vector_store._embed(texts)
        elapsed = time.time() - start
        
        assert len(embeddings) == 1000
        print(f"\n1000 chunks embedding time: {elapsed:.2f}s")

    @requires_api_key
    def test_add_documents_stores_embeddings(self, vector_store):
        documents = [
            {"id": "doc1", "content": "LDL cholesterol test", "source": "test.pdf", "page": 1},
            {"id": "doc2", "content": "Pre-diabetes management", "source": "test.pdf", "page": 1}
        ]
        
        vector_store.add_documents(documents)
        
        assert len(vector_store.documents["embeddings"]) == 2
        assert len(vector_store.documents["embeddings"][0]) == GEMINI_EMBEDDING_DIM

    @requires_api_key
    def test_embedding_batch_size(self, vector_store):
        texts = [f"Text {i}" for i in range(25)]
        
        embeddings = vector_store._embed(texts, batch_size=10)
        
        assert len(embeddings) == 25

    def test_empty_text_list(self, vector_store):
        embeddings = vector_store._embed([])
        assert len(embeddings) == 0

    @requires_api_key
    def test_single_char_embedding(self, vector_store):
        embeddings = vector_store._embed(["a"])
        
        assert len(embeddings) == 1
        assert len(embeddings[0]) == GEMINI_EMBEDDING_DIM

    @requires_api_key
    def test_medical_term_embedding(self, vector_store):
        texts = [
            "Hyperlipidaemia LDL cholesterol ASCVD",
            "Pre-diabetes metformin BMI glycemic"
        ]
        embeddings = vector_store._embed(texts)
        
        assert len(embeddings) == 2
        assert all(len(e) == GEMINI_EMBEDDING_DIM for e in embeddings)
