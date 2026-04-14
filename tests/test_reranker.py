"""Tests for cross-encoder reranking."""

from unittest.mock import MagicMock, patch

from src.rag.reranker import CrossEncoderReranker, RerankResult, get_reranker


class TestRerankResult:
    def test_empty_result(self):
        result = RerankResult(
            original_results=[],
            reranked_results=[],
            model_name="test-model",
            batch_size=16,
            timing_ms=0,
            candidates_count=0,
            output_count=0,
        )
        assert result.reranked_results == []
        assert result.candidates_count == 0


class TestCrossEncoderReranker:
    def test_rerank_empty(self):
        reranker = CrossEncoderReranker(model_name="test-model")
        result = reranker.rerank(query="test", results=[], top_k=5)
        assert result.reranked_results == []
        assert result.candidates_count == 0
        assert result.output_count == 0

    def test_rerank_single_result(self):
        reranker = CrossEncoderReranker(model_name="test-model")
        results = [{"id": "1", "content": "test content", "score": 0.5}]

        with patch.object(reranker, "_load_model"):
            reranker._model = MagicMock()
            reranker._model.predict.return_value = [0.8]
            result = reranker.rerank(query="test", results=results, top_k=5)

        assert len(result.reranked_results) == 1
        assert result.reranked_results[0]["rerank_score"] == 0.8
        assert result.reranked_results[0]["rerank_rank"] == 1

    def test_rerank_orders_by_score(self):
        reranker = CrossEncoderReranker(model_name="test-model")
        results = [
            {"id": "1", "content": "low relevance", "score": 0.3},
            {"id": "2", "content": "high relevance", "score": 0.9},
            {"id": "3", "content": "medium relevance", "score": 0.6},
        ]

        with patch.object(reranker, "_load_model"):
            reranker._model = MagicMock()
            reranker._model.predict.return_value = [0.2, 0.9, 0.5]
            result = reranker.rerank(query="test", results=results, top_k=5)

        assert len(result.reranked_results) == 3
        assert result.reranked_results[0]["id"] == "2"
        assert result.reranked_results[1]["id"] == "3"
        assert result.reranked_results[2]["id"] == "1"

    def test_rerank_respects_top_k(self):
        reranker = CrossEncoderReranker(model_name="test-model")
        results = [
            {"id": str(i), "content": f"content {i}", "score": 0.5}
            for i in range(10)
        ]

        with patch.object(reranker, "_load_model"):
            reranker._model = MagicMock()
            reranker._model.predict.return_value = [0.1] * 10
            result = reranker.rerank(query="test", results=results, top_k=3)

        assert len(result.reranked_results) == 3
        assert result.output_count == 3

    def test_rerank_records_timing(self):
        reranker = CrossEncoderReranker(model_name="test-model")
        results = [{"id": "1", "content": "test", "score": 0.5}]

        with patch.object(reranker, "_load_model"):
            reranker._model = MagicMock()
            reranker._model.predict.return_value = [0.5]
            result = reranker.rerank(query="test", results=results, top_k=5)

        assert result.timing_ms >= 0
        assert result.model_name == "test-model"
        assert result.batch_size == 16

    def test_rerank_assigns_ranks(self):
        reranker = CrossEncoderReranker(model_name="test-model")
        results = [
            {"id": "1", "content": "a", "score": 0.1},
            {"id": "2", "content": "b", "score": 0.2},
        ]

        with patch.object(reranker, "_load_model"):
            reranker._model = MagicMock()
            reranker._model.predict.return_value = [0.3, 0.7]
            result = reranker.rerank(query="test", results=results, top_k=5)

        assert result.reranked_results[0]["rerank_rank"] == 1
        assert result.reranked_results[1]["rerank_rank"] == 2

    def test_rerank_applies_score_threshold(self):
        reranker = CrossEncoderReranker(model_name="test-model")
        results = [
            {"id": "1", "content": "a", "score": 0.1},
            {"id": "2", "content": "b", "score": 0.2},
            {"id": "3", "content": "c", "score": 0.3},
        ]

        with patch.object(reranker, "_load_model"):
            reranker._model = MagicMock()
            reranker._model.predict.return_value = [0.2, 0.7, 0.4]
            result = reranker.rerank(query="test", results=results, top_k=5, min_score=0.5)

        assert [item["id"] for item in result.reranked_results] == ["2"]
        assert result.filtered_out_count == 2

    def test_predict_batch_splits_into_batches(self):
        reranker = CrossEncoderReranker(model_name="test-model", batch_size=2)
        pairs = [(f"q{i}", f"d{i}") for i in range(5)]

        with patch.object(reranker, "_load_model"):
            reranker._model = MagicMock()
            reranker._model.predict.side_effect = [[0.1, 0.2], [0.3, 0.4], [0.5]]
            scores = reranker._predict_batch(pairs)

        assert len(scores) == 5
        assert reranker._model.predict.call_count == 3


class TestGetReranker:
    def test_returns_singleton(self):
        from src.rag.reranker import _reranker_instance

        original = _reranker_instance
        try:
            reranker1 = get_reranker(model_name="test-a")
            reranker2 = get_reranker(model_name="test-a")
            assert reranker1 is reranker2
        finally:
            from src.rag import reranker
            reranker._reranker_instance = original

    def test_recreates_on_config_change(self):
        from src.rag import reranker
        original = reranker._reranker_instance
        try:
            reranker._reranker_instance = None
            r1 = get_reranker(model_name="model-a")
            r2 = get_reranker(model_name="model-b")
            assert r1 is not r2
            assert r1.model_name == "model-a"
            assert r2.model_name == "model-b"
        finally:
            reranker._reranker_instance = original
