"""Tests for answer evaluation caching."""

import json

import pytest

from src.evals.assessment.answer_eval import evaluate_answer_quality_async


class _Trace:
    def model_dump(self):
        return {
            "retrieval": {"query": "cached query", "documents": [], "timing_ms": 1},
            "context": {"total_chunks": 1, "total_chars": 5, "sources": ["doc"]},
            "generation": {"model": "fake", "timing_ms": 1},
            "total_time_ms": 2,
        }


class _Metric:
    def __init__(self, name: str, score: float):
        self.name = name
        self.score = score
        self.reason = None
        self.error = None

    async def a_measure(self, *args, **kwargs):
        return self.score


@pytest.mark.asyncio
async def test_evaluate_answer_quality_async_reuses_cached_answer(monkeypatch, tmp_path):
    cache_dir = tmp_path / "cache"
    retrieval_calls = 0
    answer_calls = 0
    metric_calls = 0

    def fake_retrieve(query, top_k, retrieval_options=None):
        nonlocal retrieval_calls
        retrieval_calls += 1
        assert retrieval_options == {"search_mode": "rrf_hybrid"}
        return ("ctx", ["doc"], _Trace())

    class _Client:
        async def a_generate(self, prompt: str, context: str = "") -> str:
            nonlocal answer_calls
            answer_calls += 1
            return "cached answer"

    original_a_measure = _Metric.a_measure

    async def counted_a_measure(self, *args, **kwargs):
        nonlocal metric_calls
        metric_calls += 1
        return await original_a_measure(self, *args, **kwargs)

    monkeypatch.setattr("src.rag.runtime.retrieve_context_with_trace", fake_retrieve)
    monkeypatch.setattr("src.infra.llm.get_client", lambda: _Client())
    monkeypatch.setattr(_Metric, "a_measure", counted_a_measure)
    monkeypatch.setattr(
        "src.evals.metrics.medical.create_medical_metrics",
        lambda: [
            _Metric("Factual Accuracy", 1.0),
            _Metric("Completeness", 1.0),
            _Metric("Clinical Relevance", 1.0),
            _Metric("Clarity", 1.0),
            _Metric("AnswerRelevancyMetric", 1.0),
            _Metric("FaithfulnessMetric", 1.0),
        ],
    )

    dataset = [{"query": "cached query", "query_id": "q1"}]
    await evaluate_answer_quality_async(
        dataset,
        top_k=3,
        cache_dir=cache_dir,
        retrieval_options={"search_mode": "rrf_hybrid"},
        cache_namespace={"index_hash": "abc"},
    )
    await evaluate_answer_quality_async(
        dataset,
        top_k=3,
        cache_dir=cache_dir,
        retrieval_options={"search_mode": "rrf_hybrid"},
        cache_namespace={"index_hash": "abc"},
    )

    assert retrieval_calls == 1
    assert answer_calls == 1
    assert metric_calls == 6
    retrieval_cache = json.loads((cache_dir / "retrieval_cache.json").read_text(encoding="utf-8"))
    generation_cache = json.loads((cache_dir / "generation_cache.json").read_text(encoding="utf-8"))
    metric_cache = json.loads((cache_dir / "metric_cache.json").read_text(encoding="utf-8"))
    assert retrieval_cache["schema_version"] == 2
    assert generation_cache["schema_version"] == 2
    assert metric_cache["schema_version"] == 2
    assert len(retrieval_cache["entries"]) == 1
    assert len(generation_cache["entries"]) == 1
    assert len(metric_cache["entries"]) == 1


@pytest.mark.asyncio
async def test_evaluate_answer_quality_async_cache_key_changes_with_retrieval_options(
    monkeypatch, tmp_path
):
    cache_dir = tmp_path / "cache"
    retrieval_calls = 0

    def fake_retrieve(query, top_k, retrieval_options=None):
        nonlocal retrieval_calls
        retrieval_calls += 1
        return ("ctx", ["doc"], _Trace())

    class _Client:
        async def a_generate(self, prompt: str, context: str = "") -> str:
            return "answer"

    monkeypatch.setattr("src.rag.runtime.retrieve_context_with_trace", fake_retrieve)
    monkeypatch.setattr("src.infra.llm.get_client", lambda: _Client())
    monkeypatch.setattr(
        "src.evals.metrics.medical.create_medical_metrics",
        lambda: [
            _Metric("Factual Accuracy", 1.0),
            _Metric("Completeness", 1.0),
            _Metric("Clinical Relevance", 1.0),
            _Metric("Clarity", 1.0),
            _Metric("AnswerRelevancyMetric", 1.0),
            _Metric("FaithfulnessMetric", 1.0),
        ],
    )

    dataset = [{"query": "cached query", "query_id": "q1"}]
    await evaluate_answer_quality_async(
        dataset, top_k=3, cache_dir=cache_dir, retrieval_options={"search_mode": "rrf_hybrid"}
    )
    await evaluate_answer_quality_async(
        dataset, top_k=3, cache_dir=cache_dir, retrieval_options={"search_mode": "semantic_only"}
    )

    assert retrieval_calls == 2
