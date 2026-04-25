"""Tests for search and ranking functions."""

import pytest

from src.ingestion.indexing.search import (
    cosine_similarity,
    rank_documents,
    reciprocal_rank_fusion,
    source_prior_for,
)


def test_cosine_similarity_identical_vectors():
    """Cosine similarity of identical vectors should be 1.0."""
    a = [1.0, 2.0, 3.0]
    b = [1.0, 2.0, 3.0]
    assert cosine_similarity(a, b) == 1.0


def test_cosine_similarity_orthogonal_vectors():
    """Cosine similarity of orthogonal vectors should be 0.0."""
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert cosine_similarity(a, b) == 0.0


def test_cosine_similarity_opposite_vectors():
    """Cosine similarity of opposite vectors should be -1.0."""
    a = [1.0, 2.0, 3.0]
    b = [-1.0, -2.0, -3.0]
    assert cosine_similarity(a, b) == -1.0


def test_cosine_similarity_zero_vectors():
    """Cosine similarity with zero vectors should be 0.0."""
    a = [0.0, 0.0]
    b = [1.0, 1.0]
    assert cosine_similarity(a, b) == 0.0


def test_source_prior_for_known_sources():
    """Source prior should return correct values for known sources."""
    assert source_prior_for("guideline_pdf") == 0.15
    assert source_prior_for("guideline_html") == 0.10
    assert source_prior_for("ace_drug_guidance") == 0.08
    assert source_prior_for("hpp_guideline") == 0.07
    assert source_prior_for("healthhub_html") == 0.06
    assert source_prior_for("reference_csv") == 0.12
    assert source_prior_for("international_html") == 0.03
    assert source_prior_for("index_page") == 0.02


def test_source_prior_for_unknown_source():
    """Source prior should return default 0.05 for unknown sources."""
    assert source_prior_for("unknown_source") == 0.05
    assert source_prior_for("") == 0.05


def test_rank_documents_basic_keyword_only():
    """Test basic ranking with keyword scores only."""
    documents = {
        "ids": ["doc1", "doc2"],
        "contents": ["content1", "content2"],
        "metadatas": [
            {"source_class": "guideline_pdf"},
            {"source_class": "guideline_html"},
        ],
    }
    keyword_scores = {0: 0.8, 1: 0.6}

    result = rank_documents(
        documents=documents,
        keyword_scores=keyword_scores,
        query_embedding=None,
        use_semantic=False,
        hybrid=False,
        semantic_weight=0.0,
        keyword_weight=1.0,
        boost_weight=1.0,
    )

    assert len(result) == 2
    assert result[0]["idx"] == 0
    assert result[0]["combined_score"] > result[1]["combined_score"]


def test_rank_documents_with_semantic():
    """Test ranking with semantic scores."""
    documents = {
        "ids": ["doc1", "doc2"],
        "contents": ["content1", "content2"],
        "embeddings": [[0.5, 0.5, 0.5], [0.2, 0.2, 0.2]],
        "metadatas": [
            {"source_class": "guideline_pdf"},
            {"source_class": "guideline_html"},
        ],
    }
    keyword_scores = {0: 0.5, 1: 0.5}

    result = rank_documents(
        documents=documents,
        keyword_scores=keyword_scores,
        query_embedding=[1.0, 0.0, 0.0],
        use_semantic=True,
        hybrid=False,
        semantic_weight=0.0,
        keyword_weight=1.0,
        boost_weight=1.0,
    )

    assert len(result) == 2
    assert result[0]["idx"] == 0
    assert result[0]["semantic_score"] > result[1]["semantic_score"]


def test_rank_documents_hybrid():
    """Test hybrid ranking combining semantic and keyword scores."""
    documents = {
        "ids": ["doc1", "doc2"],
        "contents": ["content1", "content2"],
        "embeddings": [[0.9, 0.1, 0.0], [0.1, 0.1, 0.0]],
        "metadatas": [
            {"source_class": "guideline_pdf"},
            {"source_class": "guideline_html"},
        ],
    }
    keyword_scores = {0: 0.3, 1: 0.9}

    result = rank_documents(
        documents=documents,
        keyword_scores=keyword_scores,
        query_embedding=[1.0, 0.0, 0.0],
        use_semantic=True,
        hybrid=True,
        semantic_weight=0.5,
        keyword_weight=0.5,
        boost_weight=0.2,
    )

    assert len(result) == 2


def test_rank_documents_empty_ids_allowed():
    """Test that empty ids list is allowed when other fields provide doc_count."""
    documents = {
        "contents": ["content1", "content2"],
        "metadatas": [
            {"source_class": "guideline_pdf"},
            {"source_class": "guideline_html"},
        ],
    }
    keyword_scores = {0: 0.8, 1: 0.6}

    result = rank_documents(
        documents=documents,
        keyword_scores=keyword_scores,
        query_embedding=None,
        use_semantic=False,
        hybrid=False,
        semantic_weight=0.0,
        keyword_weight=1.0,
        boost_weight=1.0,
    )

    assert len(result) == 2


def test_rank_documents_invalid_ids_length():
    """Test that mismatched ids length raises ValueError when ids is provided but shorter than max."""
    documents = {
        "ids": ["doc1", "doc2"],
        "contents": ["content1", "content2", "content3"],
        "metadatas": [
            {"source_class": "guideline_pdf"},
            {"source_class": "guideline_html"},
            {"source_class": "index_page"},
        ],
    }
    keyword_scores = {0: 0.8, 1: 0.6, 2: 0.4}

    with pytest.raises(ValueError, match="Document ids length does not match"):
        rank_documents(
            documents=documents,
            keyword_scores=keyword_scores,
            query_embedding=None,
            use_semantic=False,
            hybrid=False,
            semantic_weight=0.0,
            keyword_weight=1.0,
            boost_weight=1.0,
        )


def test_rank_documents_invalid_contents_length():
    """Test that mismatched contents length raises ValueError."""
    documents = {
        "ids": ["doc1", "doc2"],
        "contents": ["content1"],
        "metadatas": [
            {"source_class": "guideline_pdf"},
            {"source_class": "guideline_html"},
        ],
    }
    keyword_scores = {0: 0.8, 1: 0.6}

    with pytest.raises(ValueError, match="Document contents length does not match"):
        rank_documents(
            documents=documents,
            keyword_scores=keyword_scores,
            query_embedding=None,
            use_semantic=False,
            hybrid=False,
            semantic_weight=0.0,
            keyword_weight=1.0,
            boost_weight=1.0,
        )


def test_rank_documents_missing_metadata_padded():
    """Test that missing metadata entries are padded with None."""
    documents = {
        "ids": ["doc1", "doc2", "doc3"],
        "contents": ["content1", "content2", "content3"],
        "metadatas": [
            {"source_class": "guideline_pdf"},
        ],
    }
    keyword_scores = {0: 0.8, 1: 0.6, 2: 0.4}

    result = rank_documents(
        documents=documents,
        keyword_scores=keyword_scores,
        query_embedding=None,
        use_semantic=False,
        hybrid=False,
        semantic_weight=0.0,
        keyword_weight=1.0,
        boost_weight=1.0,
    )

    assert len(result) == 3
    assert result[0]["source_prior"] == 0.15
    assert result[1]["source_prior"] == 0.05
    assert result[2]["source_prior"] == 0.05


def test_rank_documents_semantic_without_embeddings():
    """Test that semantic ranking without embeddings raises ValueError."""
    documents = {
        "ids": ["doc1", "doc2"],
        "contents": ["content1", "content2"],
        "embeddings": [[0.5, 0.5]],
        "metadatas": [
            {"source_class": "guideline_pdf"},
            {"source_class": "guideline_html"},
        ],
    }
    keyword_scores = {0: 0.8, 1: 0.6}

    with pytest.raises(ValueError, match="Embedding count does not match documents"):
        rank_documents(
            documents=documents,
            keyword_scores=keyword_scores,
            query_embedding=[1.0, 0.0],
            use_semantic=True,
            hybrid=False,
            semantic_weight=0.0,
            keyword_weight=1.0,
            boost_weight=1.0,
        )


def test_rank_documents_empty_metadatas_allowed():
    """Test that empty metadatas list is handled correctly."""
    documents = {
        "ids": ["doc1", "doc2"],
        "contents": ["content1", "content2"],
    }
    keyword_scores = {0: 0.8, 1: 0.6}

    result = rank_documents(
        documents=documents,
        keyword_scores=keyword_scores,
        query_embedding=None,
        use_semantic=False,
        hybrid=False,
        semantic_weight=0.0,
        keyword_weight=1.0,
        boost_weight=1.0,
    )

    assert len(result) == 2
    assert result[0]["source_prior"] == 0.05
    assert result[1]["source_prior"] == 0.05


def test_rank_documents_keyword_only_no_embeddings():
    """Test keyword-only ranking doesn't require embeddings."""
    documents = {
        "ids": ["doc1", "doc2"],
        "contents": ["content1", "content2"],
        "metadatas": [
            {"source_class": "guideline_pdf"},
            {"source_class": "guideline_html"},
        ],
    }
    keyword_scores = {0: 0.8, 1: 0.6}

    result = rank_documents(
        documents=documents,
        keyword_scores=keyword_scores,
        query_embedding=None,
        use_semantic=False,
        hybrid=False,
        semantic_weight=0.0,
        keyword_weight=1.0,
        boost_weight=1.0,
    )

    assert len(result) == 2
    assert all(item["semantic_score"] == 0.0 for item in result)


def test_reciprocal_rank_fusion_basic():
    """Test basic reciprocal rank fusion."""
    semantic_ranked = [
        {"idx": 0, "semantic_score": 0.9, "source_prior": 0.1},
        {"idx": 1, "semantic_score": 0.8, "source_prior": 0.1},
    ]
    keyword_ranked = [
        {"idx": 1, "keyword_score": 0.9, "source_prior": 0.1},
        {"idx": 2, "keyword_score": 0.8, "source_prior": 0.1},
    ]

    result = reciprocal_rank_fusion(semantic_ranked, keyword_ranked)

    assert len(result) == 3
    assert result[0]["idx"] == 1
    assert result[0]["fused_rank"] == 1
    assert result[0]["semantic_rank"] == 2
    assert result[0]["bm25_rank"] == 1


def test_reciprocal_rank_fusion_custom_k():
    """Test reciprocal rank fusion with custom k parameter."""
    semantic_ranked = [
        {"idx": 0, "semantic_score": 0.9, "source_prior": 0.1},
    ]
    keyword_ranked = [
        {"idx": 0, "keyword_score": 0.8, "source_prior": 0.1},
    ]

    result_k_default = reciprocal_rank_fusion(semantic_ranked, keyword_ranked)
    result_k_100 = reciprocal_rank_fusion(semantic_ranked, keyword_ranked, k=100)

    assert result_k_default[0]["fused_score"] > result_k_100[0]["fused_score"]
