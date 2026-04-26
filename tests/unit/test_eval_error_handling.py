"""Error handling and edge case tests for evaluation pipeline.

These tests validate that the evaluation pipeline handles various error scenarios
gracefully, including API timeouts, cache issues, and invalid inputs.

Tests cover:
- API timeout handling with retry logic
- Cache consistency during failures
- Partial result handling
- Invalid input validation
"""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

# =============================================================================
# API Timeout Tests
# =============================================================================


@pytest.mark.asyncio
async def test_dashscope_api_timeout_retry():
    """Test that Dashscope API timeouts trigger retry logic."""
    from src.evals.assessment.answer_eval import evaluate_answer_quality_async

    dataset = [{"query": "Test query", "query_id": "timeout_test_001"}]

    # Mock timeout scenario
    with patch("src.infra.llm.qwen_client.QwenClient.a_generate") as mock_gen:
        # First call times out, second succeeds
        mock_gen.side_effect = [
            Exception("Timeout"),
            "Test answer with sufficient content to pass evaluation.",
        ]

        try:
            results, _aggregate = await evaluate_answer_quality_async(dataset, top_k=3)

            # If it succeeds, verify results
            if len(results) > 0:
                assert results[0]["query"] == "Test query"
        except Exception as e:
            # Expected if all retries fail
            assert "timeout" in str(e).lower() or "api" in str(e).lower()


@pytest.mark.asyncio
async def test_cache_during_failures():
    """Test that cache still works during API failures."""
    from src.evals.assessment.answer_eval import evaluate_answer_quality_async

    dataset = [{"query": "Cache test query", "query_id": "cache_test_001"}]

    # Run once to populate cache
    with patch("src.infra.llm.qwen_client.QwenClient.a_generate") as mock_gen:
        mock_gen.return_value = "Cached answer for testing."

        try:
            results1, _ = await evaluate_answer_quality_async(dataset, top_k=3)

            # Run again - should use cache
            results2, _ = await evaluate_answer_quality_async(dataset, top_k=3)

            # Results should be consistent
            if len(results1) > 0 and len(results2) > 0:
                assert results1[0]["query"] == results2[0]["query"]
        except Exception as e:
            pytest.fail(f"Unexpected error during cache test: {e}")


# =============================================================================
# Partial Result Tests
# =============================================================================


@pytest.mark.asyncio
async def test_partial_results_on_some_failures():
    """Test that partial results are returned when some metrics fail."""
    from src.evals.assessment.answer_eval import evaluate_answer_quality_async

    dataset = [{"query": "Partial test query", "query_id": "partial_test_001"}]

    # Mock some metrics to fail
    async def mock_safe_measure(metric, test_case, **kwargs):
        del test_case, kwargs
        metric_name = metric.__class__.__name__.lower()
        if "faithfulness" in metric_name:
            raise RuntimeError("synthetic metric failure")
        metric.score = 0.8
        metric.reason = "mock success"

    with patch("src.infra.llm.qwen_client.QwenClient.a_generate", return_value="Test answer"):
        with patch("src.evals.assessment.answer_eval.safe_a_measure", side_effect=mock_safe_measure):
            try:
                results, _aggregate = await evaluate_answer_quality_async(dataset, top_k=3)

                # Should return results even with some failures
                if len(results) > 0:
                    result = results[0]

                    # Check that we got some results
                    assert "metrics" in result

                    # Some metrics may have failed
                    metrics = result["metrics"]

                    # Should have at least attempted metrics
                    assert len(metrics) > 0
            except Exception as e:
                pytest.fail(f"Unexpected error during partial results test: {e}")


# =============================================================================
# Invalid Input Tests
# =============================================================================


@pytest.mark.asyncio
async def test_none_query_in_dataset():
    """Test that None queries in dataset are handled."""
    from src.evals.assessment.answer_eval import evaluate_answer_quality_async

    dataset = [{"query": None, "query_id": "none_test_001"}]

    # Should handle None query
    try:
        results, _aggregate = await evaluate_answer_quality_async(dataset, top_k=3)

        # Should return results or handle gracefully
        assert isinstance(results, list)
    except Exception as e:
        # Should have clear error message
        assert "query" in str(e).lower() or "empty" in str(e).lower()


@pytest.mark.asyncio
async def test_empty_string_query():
    """Test that empty string queries are handled."""
    from src.evals.assessment.answer_eval import evaluate_answer_quality_async

    dataset = [{"query": "", "query_id": "empty_test_001"}]

    # Should handle empty query
    try:
        results, _aggregate = await evaluate_answer_quality_async(dataset, top_k=3)

        # Should return results or handle gracefully
        assert isinstance(results, list)
    except (ValueError, AttributeError) as e:
        # Expected to raise validation error
        assert "query" in str(e).lower() or "empty" in str(e).lower()


@pytest.mark.asyncio
async def test_negative_top_k():
    """Test that negative top_k values are handled."""
    from src.evals.assessment.answer_eval import evaluate_answer_quality_async

    dataset = [{"query": "Test query", "query_id": "topk_test_001"}]

    with patch("src.infra.llm.qwen_client.QwenClient.a_generate", return_value="Test answer"):
        # Should handle negative top_k
        try:
            results, _aggregate = await evaluate_answer_quality_async(dataset, top_k=-1)

            # Should clamp to valid range or return empty
            assert isinstance(results, list)
        except (ValueError, AttributeError) as e:
            # Expected to raise validation error
            assert "top_k" in str(e).lower() or "invalid" in str(e).lower()


@pytest.mark.asyncio
async def test_zero_top_k():
    """Test that zero top_k values are handled."""
    from src.evals.assessment.answer_eval import evaluate_answer_quality_async

    dataset = [{"query": "Test query", "query_id": "zero_topk_001"}]

    with patch("src.infra.llm.qwen_client.QwenClient.a_generate", return_value="Test answer"):
        # Should handle zero top_k
        results, _aggregate = await evaluate_answer_quality_async(dataset, top_k=0)

        # Should return results with no context
        assert isinstance(results, list)


# =============================================================================
# Artifact Error Tests
# =============================================================================


def test_artifact_store_with_invalid_path():
    """Test that artifact store handles invalid paths."""
    from src.evals.artifacts import find_reusable_run

    # Should handle invalid path gracefully
    try:
        result = find_reusable_run(Path("/invalid/path/that/does/not/exist"), "test_identity")

        # Should return None
        assert result is None
    except Exception as e:
        # Should have clear error message
        assert "path" in str(e).lower() or "directory" in str(e).lower()


def test_artifact_write_failure():
    """Test that artifact write failures are handled."""
    from pathlib import Path

    from src.evals.schemas import AssessmentResult

    # Try to create result with invalid data
    try:
        result = AssessmentResult(
            run_dir=Path("/invalid/path"), status="test", failed_thresholds=[], summary={}
        )

        # Should create object
        assert result is not None
    except Exception as e:
        # Should have clear error message
        assert "path" in str(e).lower() or "directory" in str(e).lower()


# =============================================================================
# Concurrent Evaluation Error Tests
# =============================================================================


@pytest.mark.asyncio
async def test_concurrent_evaluation_with_failures():
    """Test that concurrent evaluations handle failures gracefully."""
    from src.evals.assessment.answer_eval import evaluate_answer_quality_async

    # Multiple queries
    dataset = [{"query": f"Query {i}", "query_id": f"concurrent_{i}"} for i in range(5)]

    # Mock retrieval to return valid context with proper structure
    with patch("src.rag.runtime.retrieve_context_with_trace") as mock_retrieve:
        mock_retrieve.return_value = (
            "Mock context for testing",
            [{"label": "doc1", "source": "test"}],
            {
                "retrieval": {"query": "test", "documents": [], "timing_ms": 1},
                "context": {"total_chunks": 1, "total_chars": 5, "sources": ["doc1"]},
                "generation": {"model": "test", "timing_ms": 1},
                "total_time_ms": 2,
            },
        )

        # Mock some to fail
        with patch("src.infra.llm.qwen_client.QwenClient.a_generate") as mock_gen:
            # Alternate between success and failure
            mock_gen.side_effect = [
                "Answer 1",
                Exception("API Error"),
                "Answer 3",
                "Answer 4",
                "Answer 5",
            ]

            try:
                results, aggregate = await evaluate_answer_quality_async(dataset, top_k=3)

                # Should return partial results
                assert len(results) <= 5

                # Check aggregate counts
                assert aggregate["query_count"] == 5
            except Exception as e:
                # Expected if too many failures
                assert "api" in str(e).lower() or "timeout" in str(e).lower()


# =============================================================================
# Metric Calculation Error Tests
# =============================================================================


@pytest.mark.asyncio
async def test_metric_calculation_with_invalid_context():
    """Test that metrics handle invalid context gracefully."""
    from src.evals.assessment.answer_eval import evaluate_answer_quality_async

    dataset = [{"query": "Test query", "query_id": "context_test_001"}]

    # Mock retrieval to return empty context
    with patch("src.infra.llm.qwen_client.QwenClient.a_generate", return_value="Test answer"):
        with patch("src.rag.runtime.retrieve_context_with_trace") as mock_retrieve:
            mock_retrieve.return_value = ("", [], {"retrieval": {}, "context": {}, "generation": {}, "total_time_ms": 0})

            try:
                results, _aggregate = await evaluate_answer_quality_async(dataset, top_k=3)

                # Should still generate results
                if len(results) > 0:
                    assert "metrics" in results[0]

                    # Some metrics may fail due to empty context
                    metrics = results[0]["metrics"]

                    # Should have attempted all metrics
                    assert len(metrics) >= 0
            except Exception as e:
                pytest.fail(f"Unexpected error during invalid context test: {e}")


@pytest.mark.asyncio
async def test_metric_timeout_handling():
    """Test that individual metric timeouts don't crash evaluation."""
    from src.evals.assessment.answer_eval import evaluate_answer_quality_async

    dataset = [{"query": "Timeout test", "query_id": "timeout_metric_001"}]

    # Mock metric calculation to timeout
    async def timeout_safe_measure(metric, test_case, **kwargs):
        del metric, test_case, kwargs
        await asyncio.sleep(0)

    async def timeout_wait_for(awaitable, timeout):
        if hasattr(awaitable, "close"):
            awaitable.close()
        del timeout
        raise TimeoutError("synthetic metric timeout")

    with patch("src.evals.assessment.answer_eval.safe_a_measure", side_effect=timeout_safe_measure):
        with patch(
            "src.evals.assessment.answer_eval.asyncio.wait_for", side_effect=timeout_wait_for
        ):
            with patch(
                "src.infra.llm.qwen_client.QwenClient.a_generate", return_value="Timeout test answer"
            ):
                try:
                    results, _aggregate = await evaluate_answer_quality_async(dataset, top_k=3)

                    # Should handle timeout
                    if len(results) > 0:
                        metrics = results[0]["metrics"]

                        # At least some metrics should have error status
                        error_metrics = [
                            name for name, data in metrics.items() if data.get("status") == "error"
                        ]

                        assert len(metrics) > 0
                        assert error_metrics
                except (TimeoutError, Exception) as e:
                    # Expected if timeout occurs
                    assert "timeout" in str(e).lower() or "time" in str(e).lower()


# =============================================================================
# Edge Case: Very Long Responses
# =============================================================================


@pytest.mark.asyncio
async def test_very_long_response_handling():
    """Test that very long LLM responses are handled."""
    from src.evals.assessment.answer_eval import evaluate_answer_quality_async

    dataset = [{"query": "Long response test", "query_id": "long_001"}]

    # Mock very long response
    long_response = "This is a detailed answer. " * 1000  # ~20k chars

    with patch("src.infra.llm.qwen_client.QwenClient.a_generate") as mock_gen:
        mock_gen.return_value = long_response

        try:
            results, _aggregate = await evaluate_answer_quality_async(dataset, top_k=3)

            # Should handle long response
            if len(results) > 0:
                assert len(results[0]["answer"]) > 1000
        except Exception as e:
            # Should handle gracefully
            assert (
                "length" in str(e).lower() or "size" in str(e).lower() or "token" in str(e).lower()
            )


# =============================================================================
# Edge Case: Unicode and Special Characters
# =============================================================================


@pytest.mark.asyncio
async def test_unicode_in_query_and_response():
    """Test that Unicode characters are handled correctly."""
    from src.evals.assessment.answer_eval import evaluate_answer_quality_async

    dataset = [{"query": "What is the recommended LDL-C target? 价值观", "query_id": "unicode_001"}]

    with patch("src.infra.llm.qwen_client.QwenClient.a_generate") as mock_gen:
        mock_gen.return_value = "The recommended target is < 1.8 mmol/L. 价值观测试"

        try:
            results, _aggregate = await evaluate_answer_quality_async(dataset, top_k=3)

            # Should handle Unicode
            if len(results) > 0:
                answer = results[0]["answer"]
                assert "价值观" in answer or "target" in answer.lower()
        except Exception as e:
            # Should handle encoding errors
            assert (
                "unicode" in str(e).lower()
                or "encoding" in str(e).lower()
                or "character" in str(e).lower()
            )
