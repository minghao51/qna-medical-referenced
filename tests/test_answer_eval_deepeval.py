"""Tests for DeepEval-based answer evaluation.

Tests the evaluate_answers_deepeval function for proper integration
with DeepEval metrics and RAG pipeline.
"""

import pytest

from src.evals.assessment.answer_eval import evaluate_answers_deepeval


@pytest.mark.deepeval
@pytest.mark.slow
@pytest.mark.asyncio
async def test_evaluate_answers_deepeval_basic():
    """Test basic functionality of DeepEval answer evaluation."""
    dataset = [
        {"query": "What is the LDL-C target for secondary prevention?", "query_id": "test_001"}
    ]

    results, aggregate = await evaluate_answers_deepeval(dataset, top_k=3)

    # Check we got results
    assert len(results) == 1
    assert results[0]["query"] == "What is the LDL-C target for secondary prevention?"
    assert results[0]["query_id"] == "test_001"
    assert "answer" in results[0]
    assert "sources" in results[0]
    assert "metrics" in results[0]

    # Check metrics were computed
    metrics = results[0]["metrics"]
    # Custom GEval metrics have their name
    assert "factual_accuracy" in metrics
    assert "completeness" in metrics
    assert "clinical_relevance" in metrics
    assert "clarity" in metrics
    assert "answer_relevancy" in metrics
    assert "faithfulness" in metrics

    # Check each metric has a score or error status
    for metric_name, metric_data in metrics.items():
        assert "score" in metric_data
        assert "status" in metric_data
        score = metric_data["score"]
        if score is not None:
            assert 0 <= score <= 1, f"{metric_name} score {score} not in range [0, 1]"
        else:
            assert metric_data["status"] == "error", f"{metric_name} has None score but status is {metric_data['status']}"
            assert metric_data.get("error") is not None, f"{metric_name} has None score but no error message"

    # Check aggregate stats
    assert aggregate["query_count"] == 1
    assert "factual_accuracy" in aggregate
    assert "completeness" in aggregate
    assert "clinical_relevance" in aggregate
    assert "clarity" in aggregate
    assert "answer_relevancy" in aggregate
    assert "faithfulness" in aggregate


@pytest.mark.deepeval
@pytest.mark.slow
@pytest.mark.asyncio
async def test_evaluate_answers_deepeval_multiple_queries():
    """Test evaluation with multiple queries."""
    dataset = [
        {"query": "What are statin side effects?"},
        {"query": "What is the LDL-C target?"},
        {"query": "Explain primary prevention."},
    ]

    results, aggregate = await evaluate_answers_deepeval(dataset, top_k=3)

    # Check all queries were evaluated
    assert len(results) == 3
    assert aggregate["query_count"] == 3

    # Check each result has required fields
    for result in results:
        assert "query" in result
        assert "answer" in result
        assert "sources" in result
        assert "metrics" in result
        assert len(result["metrics"]) == 6  # 6 metrics

    # Check aggregate means are calculated (may be None if all metrics failed)
    for metric_key in [
        "factual_accuracy",
        "completeness",
        "clinical_relevance",
        "clarity",
        "answer_relevancy",
        "faithfulness",
    ]:
        assert metric_key in aggregate
        assert "mean" in aggregate[metric_key]
        assert "count" in aggregate[metric_key]
        # Count should be <= 3 (some metrics may have failed)
        assert 0 <= aggregate[metric_key]["count"] <= 3
        # If count > 0, mean should be valid
        if aggregate[metric_key]["count"] > 0:
            mean = aggregate[metric_key]["mean"]
            assert mean is not None, f"{metric_key} has count > 0 but None mean"
            assert 0 <= mean <= 1, f"{metric_key} mean {mean} not in range [0, 1]"


@pytest.mark.deepeval
@pytest.mark.slow
@pytest.mark.asyncio
async def test_evaluate_answers_deepeval_includes_trace():
    """Test that pipeline trace information is included in results."""
    dataset = [{"query": "What is cholesterol?", "query_id": "trace_test"}]

    results, _ = await evaluate_answers_deepeval(dataset, top_k=3)

    assert len(results) == 1
    result = results[0]

    # Check trace is present
    assert "trace" in result
    trace = result["trace"]

    # Check trace has expected structure
    assert "retrieval" in trace
    assert "context" in trace
    assert "generation" in trace
    assert "total_time_ms" in trace

    # Check retrieval stage
    retrieval = trace["retrieval"]
    assert "query" in retrieval
    assert retrieval["query"] == "What is cholesterol?"
    assert "documents" in retrieval
    assert "timing_ms" in retrieval
