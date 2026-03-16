"""Unit tests for the async DeepEval answer evaluation path."""

import asyncio

import pytest

from src.evals.assessment.answer_eval import evaluate_answers_deepeval


class _FakeTrace:
    def model_dump(self):
        return {
            "retrieval": {"query": "test query", "documents": [], "timing_ms": 1},
            "context": {"total_chunks": 1, "total_chars": 12, "sources": ["doc"]},
            "generation": {"model": "fake", "timing_ms": 1},
            "total_time_ms": 2,
        }


class _FakeMetric:
    def __init__(self, name: str, score: float):
        self.name = name
        self.score = score
        self.reason = f"{name} ok"
        self.error = None

    async def a_measure(self, test_case, _show_indicator=False, _log_metric_to_confident=False):
        return self.score


@pytest.mark.asyncio
async def test_evaluate_answers_deepeval_uses_async_generation_and_fresh_metrics(
    monkeypatch, tmp_path
):
    """The async evaluator should use async answer generation and aggregate fresh metric results."""

    async def fake_a_generate(prompt: str, context: str = "") -> str:
        assert prompt == "test query"
        assert context == "retrieved context"
        return "generated answer"

    class _FakeClient:
        async def a_generate(self, prompt: str, context: str = "") -> str:
            return await fake_a_generate(prompt, context)

    monkeypatch.setattr("src.infra.llm.get_client", lambda: _FakeClient())
    monkeypatch.setattr(
        "src.rag.runtime.retrieve_context_with_trace",
        lambda query, top_k, retrieval_options=None: ("retrieved context", ["doc"], _FakeTrace()),
    )
    monkeypatch.setattr(
        "src.evals.metrics.medical.create_medical_metrics",
        lambda: [
            _FakeMetric("Factual Accuracy", 0.9),
            _FakeMetric("Completeness", 0.8),
            _FakeMetric("Clinical Relevance", 0.7),
            _FakeMetric("Clarity", 0.6),
            _FakeMetric("AnswerRelevancyMetric", 0.5),
            _FakeMetric("FaithfulnessMetric", 0.4),
        ],
    )

    results, aggregate = await evaluate_answers_deepeval(
        [{"query_id": "q1", "query": "test query"}],
        top_k=3,
        cache_dir=tmp_path / "cache",
    )

    assert len(results) == 1
    assert results[0]["answer"] == "generated answer"
    assert results[0]["metrics"]["factual_accuracy"]["score"] == 0.9
    assert results[0]["metrics"]["factual_accuracy"]["status"] == "ok"
    assert aggregate["query_count"] == 1
    assert aggregate["query_count_scored"] == 1
    assert aggregate["metric_error_rate"] == 0.0
    assert aggregate["factual_accuracy"]["mean"] == 0.9
    assert aggregate["answer_relevancy"]["mean"] == 0.5
    assert aggregate["faithfulness"]["mean"] == 0.4


@pytest.mark.asyncio
async def test_evaluate_answers_deepeval_excludes_metric_errors_from_means(monkeypatch, tmp_path):
    class _FailingMetric(_FakeMetric):
        async def a_measure(self, test_case, _show_indicator=False, _log_metric_to_confident=False):
            raise RuntimeError("judge unavailable")

    class _FakeClient:
        async def a_generate(self, prompt: str, context: str = "") -> str:
            return "generated answer"

    monkeypatch.setattr("src.infra.llm.get_client", lambda: _FakeClient())
    monkeypatch.setattr(
        "src.rag.runtime.retrieve_context_with_trace",
        lambda query, top_k, retrieval_options=None: ("retrieved context", ["doc"], _FakeTrace()),
    )
    monkeypatch.setattr(
        "src.evals.metrics.medical.create_medical_metrics",
        lambda: [
            _FakeMetric("Factual Accuracy", 0.9),
            _FailingMetric("Completeness", 0.8),
            _FakeMetric("Clinical Relevance", 0.7),
            _FakeMetric("Clarity", 0.6),
            _FakeMetric("AnswerRelevancyMetric", 0.5),
            _FakeMetric("FaithfulnessMetric", 0.4),
        ],
    )

    results, aggregate = await evaluate_answers_deepeval(
        [{"query_id": "q1", "query": "test query"}],
        top_k=3,
        cache_dir=tmp_path / "cache",
    )

    assert results[0]["metrics"]["completeness"]["status"] == "error"
    assert results[0]["metrics"]["completeness"]["score"] is None
    assert aggregate["completeness"]["count"] == 0
    assert aggregate["completeness"]["error_count"] == 1
    assert aggregate["metric_evaluations_failed"] == 1
    assert aggregate["metric_error_rate"] == pytest.approx(1 / 6)
    assert aggregate["status"] == "degraded"


@pytest.mark.asyncio
async def test_evaluate_answers_deepeval_marks_timeouts_as_metric_errors(monkeypatch, tmp_path):
    class _SlowMetric(_FakeMetric):
        async def a_measure(self, test_case, _show_indicator=False, _log_metric_to_confident=False):
            await asyncio.sleep(1.1)
            return self.score

    class _FakeClient:
        async def a_generate(self, prompt: str, context: str = "") -> str:
            return "generated answer"

    monkeypatch.setattr("src.infra.llm.get_client", lambda: _FakeClient())
    monkeypatch.setattr(
        "src.rag.runtime.retrieve_context_with_trace",
        lambda query, top_k, retrieval_options=None: ("retrieved context", ["doc"], _FakeTrace()),
    )
    monkeypatch.setattr(
        "src.evals.metrics.medical.create_medical_metrics",
        lambda: [
            _SlowMetric("Factual Accuracy", 0.9),
            _FakeMetric("Completeness", 0.8),
            _FakeMetric("Clinical Relevance", 0.7),
            _FakeMetric("Clarity", 0.6),
            _FakeMetric("AnswerRelevancyMetric", 0.5),
            _FakeMetric("FaithfulnessMetric", 0.4),
        ],
    )
    monkeypatch.setattr("src.evals.assessment.answer_eval.settings.deepeval_metric_timeout_seconds", 0)

    results, aggregate = await evaluate_answers_deepeval(
        [{"query_id": "q1", "query": "test query"}],
        top_k=3,
        cache_dir=tmp_path / "cache",
    )

    assert results[0]["metrics"]["factual_accuracy"]["status"] == "error"
    assert "metric_timeout" in str(results[0]["metrics"]["factual_accuracy"]["error"])
    assert aggregate["factual_accuracy"]["error_count"] == 1
