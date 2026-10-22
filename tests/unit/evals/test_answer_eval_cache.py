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
async def test_evaluate_answer_quality_async_executes_fresh_attempts(monkeypatch, tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    legacy = cache_dir / "generation_cache.json"
    legacy_bytes = '{"schema_version":2,"entries":{"legacy":"do not reuse or rewrite"}}'
    legacy.write_text(legacy_bytes)
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

    dataset = [
        {"query": "cached query", "query_id": "q1"},
        {"query": "cached query", "query_id": "q2"},
    ]
    first_rows, first_metrics = await evaluate_answer_quality_async(
        dataset,
        top_k=3,
        cache_dir=cache_dir,
        retrieval_options={"search_mode": "rrf_hybrid"},
        cache_namespace={"index_hash": "abc"},
    )
    second_rows, second_metrics = await evaluate_answer_quality_async(
        dataset,
        top_k=3,
        cache_dir=cache_dir,
        retrieval_options={"search_mode": "rrf_hybrid"},
        cache_namespace={"index_hash": "abc"},
    )

    assert retrieval_calls == 4
    assert answer_calls == 4
    assert metric_calls == 24
    assert legacy.read_text() == legacy_bytes
    assert (
        first_metrics["cache_policy"]["attempt_id"] != second_metrics["cache_policy"]["attempt_id"]
    )
    assert len(first_rows) == len(second_rows) == 2
    assert not any(hit for row in first_rows + second_rows for hit in row["cache"].values())
    from pathlib import Path

    for metrics in (first_metrics, second_metrics):
        policy = metrics["cache_policy"]
        assert policy["mode"] == "fresh"
        assert policy["persistent_reuse"] is False
        attempt_dir = Path(policy["artifact_dir"])
        assert attempt_dir.parent == cache_dir
        for name in ("retrieval_cache.json", "generation_cache.json", "metric_cache.json"):
            payload = json.loads((attempt_dir / name).read_text())
            assert payload["schema_version"] == 3
            assert payload["cache_contract_version"] == 1
            assert payload["reusable"] is False
            assert len(payload["entries"]) == 1


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


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "failure", "cancellation"])
async def test_owned_judge_clients_close_on_the_evaluating_loop(monkeypatch, tmp_path, outcome):
    import asyncio

    from pydantic import SecretStr

    from src.config import settings
    from src.evals.assessment import answer_eval
    from src.evals.metrics import medical

    monkeypatch.setattr(settings.llm, "provider", "qwen")
    monkeypatch.setattr(settings.llm, "judge_provider", "qwen")
    monkeypatch.setattr(settings.llm, "dashscope_api_key", SecretStr("synthetic-only"))
    monkeypatch.setattr(answer_eval, "safe_a_measure", None)
    loop = asyncio.get_running_loop()
    closed_on: list[asyncio.AbstractEventLoop] = []

    class OwnedJudge:
        async def aclose(self):
            closed_on.append(asyncio.get_running_loop())

    class Metric:
        score = 1.0
        reason = None
        error = None

        def __init__(self):
            self.model = OwnedJudge()

        async def a_measure(self, *args, **kwargs):
            if outcome == "failure":
                raise RuntimeError("synthetic metric failure")
            if outcome == "cancellation":
                raise asyncio.CancelledError
            return self.score

    async def prepared(item, **kwargs):
        return answer_eval.AnswerQualityCase(
            query_id="synthetic",
            query="question",
            context="context",
            sources=[],
            trace={},
            answer="answer",
            timings={},
            cache={},
        )

    monkeypatch.setattr(answer_eval, "_prepare_answer_case", prepared)
    monkeypatch.setattr(
        medical, "create_medical_metrics", lambda: [Metric() for _ in medical.METRIC_SPECS]
    )

    if outcome == "cancellation":
        with pytest.raises(asyncio.CancelledError):
            await answer_eval.evaluate_answer_quality_async(
                [{"query_id": "synthetic", "query": "question"}], 3, cache_dir=tmp_path
            )
    else:
        rows, aggregate = await answer_eval.evaluate_answer_quality_async(
            [{"query_id": "synthetic", "query": "question"}], 3, cache_dir=tmp_path
        )
        assert len(rows) == 1
        assert aggregate["status"] == ("ok" if outcome == "success" else "degraded")

    assert len(closed_on) == len(medical.METRIC_SPECS)
    assert all(closed_loop is loop for closed_loop in closed_on)


@pytest.mark.asyncio
async def test_injected_judge_models_are_not_closed_by_metric_helper():
    from types import SimpleNamespace

    from src.evals.assessment.answer_eval import (
        AnswerQualityCase,
        _evaluate_case_metrics,
    )

    closed = []

    class InjectedJudge:
        async def aclose(self):
            closed.append(True)

    class Metric:
        score = 1.0
        reason = None
        error = None
        model = InjectedJudge()

        async def a_measure(self, case):
            return self.score

    result, scores, _ = await _evaluate_case_metrics(
        AnswerQualityCase("case", "question", "context", [], {}, "answer", {}, {}),
        metric_specs=[SimpleNamespace(key="metric")],
        metric_builder=lambda: [Metric()],
        runtime_signature={},
        metric_cache={},
        metric_cache_enabled=False,
        metric_concurrency=1,
    )

    assert result["metric"]["status"] == "ok"
    assert scores == {"metric": 1.0}
    assert closed == []


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), object()])
def test_cache_serialization_failure_preserves_existing_snapshot(tmp_path, invalid):
    from src.evals.assessment.answer_eval import _write_cache_entries

    target = tmp_path / "metric_cache.json"
    target.write_text('{"synthetic": "previous snapshot"}')
    with pytest.raises((ValueError, TypeError)):
        _write_cache_entries(target, {"invalid": invalid})
    assert target.read_text() == '{"synthetic": "previous snapshot"}'
    assert list(tmp_path.glob(".*.tmp")) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_type", [OSError, ValueError, TypeError])
@pytest.mark.parametrize("failure_stage", ["directory", "writer"])
async def test_optional_diagnostic_write_failure_keeps_completed_measurements(
    monkeypatch, tmp_path, caplog, failure_type, failure_stage
):
    from src.evals.assessment import answer_eval
    from src.evals.metrics import medical

    async def prepared(*args, **kwargs):
        return answer_eval.AnswerQualityCase(
            query_id="synthetic",
            query="question",
            context="context",
            sources=[],
            trace={},
            answer="answer",
            timings={},
            cache={},
        )

    def failed_write(*args, **kwargs):
        raise failure_type("synthetic-secret-and-path-canary")

    monkeypatch.setattr(answer_eval, "_prepare_answer_case", prepared)
    if failure_stage == "writer":
        monkeypatch.setattr(answer_eval, "_write_cache_entries", failed_write)
    else:
        monkeypatch.setattr(answer_eval.Path, "mkdir", failed_write)
    monkeypatch.setattr(
        medical,
        "create_medical_metrics",
        lambda: [_Metric(spec.display_name, 1.0) for spec in medical.METRIC_SPECS],
    )
    rows, metrics = await evaluate_answer_quality_async(
        [{"query": "question"}], 3, cache_dir=tmp_path
    )
    assert rows[0]["status"] == "ok"
    assert metrics["status"] == "ok"
    assert metrics["query_count_complete"] == 1
    assert metrics["cache_policy"]["write_status"] == "failed"
    assert "synthetic-secret-and-path-canary" not in caplog.text
