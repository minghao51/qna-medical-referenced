"""Offline checks for privacy-safe assessment operation spans."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.config.settings import TelemetryConfig
from src.evals.assessment import answer_eval
from src.evals.assessment.retrieval_eval import evaluate_retrieval
from src.infra.telemetry import (
    Operation,
    Stage,
    Telemetry,
    UsageCompleteness,
    telemetry_operation,
    use_telemetry,
)

_SOURCE_ID_CANARY = "12345678-1234-4234-8234-123456789abc"
_QUERY_CANARY = "SYNTHETIC_PROMPT_CANARY"
_SOURCE_CANARY = "SYNTHETIC_SOURCE_CANARY"
_ANSWER_CANARY = "SYNTHETIC_ANSWER_CANARY"
_EXCEPTION_CANARY = "SYNTHETIC_EXCEPTION_TEXT_CANARY"


def _serialize_spans(telemetry: Telemetry) -> str:
    return json.dumps(
        [
            {
                "name": span.name,
                "attributes": dict(span.attributes or {}),
                "events": [
                    {"name": event.name, "attributes": dict(event.attributes or {})}
                    for event in span.events
                ],
            }
            for span in telemetry.finished_spans
        ],
        sort_keys=True,
        default=str,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("score", "error"),
    [(False, None), (None, None), (float("nan"), None), (0.75, _EXCEPTION_CANARY)],
)
async def test_handled_metric_failure_marks_attempt_error_without_exception_text(
    monkeypatch, score, error
):
    class Metric:
        async def a_measure(self, test_case):
            pass

    metric = Metric()
    metric.score, metric.error, metric.reason = score, error, None
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    monkeypatch.setattr(answer_eval, "safe_a_measure", None)
    with use_telemetry(telemetry):
        payload = await answer_eval._evaluate_metric(
            metric, SimpleNamespace(), semaphore=asyncio.Semaphore(1)
        )
    attempts = [s for s in telemetry.finished_spans if s.name in {"evaluation", "retry"}]
    assert len(attempts) == (2 if error else 1)
    assert payload["status"] == "error"
    assert all(s.attributes["telemetry.outcome"] == "error" for s in attempts)
    assert all(s.status.status_code.name == "ERROR" for s in attempts)
    assert _EXCEPTION_CANARY not in _serialize_spans(telemetry)
    assert telemetry.close()


def _prepare_kwargs(client) -> dict:
    return {
        "top_k": 2,
        "retrieval_options": None,
        "runtime_signature": {},
        "retrieval_cache": {},
        "generation_cache": {},
        "cache_enabled": False,
        "semaphore": asyncio.Semaphore(2),
        "llm_client": client,
    }


@pytest.mark.asyncio
async def test_answer_spans_correlate_opaque_cases_across_worker_and_judging(monkeypatch):
    import src.rag.runtime as runtime

    telemetry = Telemetry(TelemetryConfig(mode="local"))

    def retrieve(query, top_k, retrieval_options=None):
        with telemetry_operation(Operation.SEARCH, stage=Stage.SEARCH):
            return _SOURCE_CANARY, [_SOURCE_CANARY], {}

    class Client:
        async def a_generate(self, prompt, context):
            await asyncio.sleep(0)
            return _ANSWER_CANARY

    class Metric:
        score = 0.75
        reason = None
        error = None

        async def a_measure(self, test_case):
            await asyncio.sleep(0)

    monkeypatch.setattr(runtime, "retrieve_context_with_trace", retrieve)
    monkeypatch.setattr(answer_eval, "safe_a_measure", None)
    run_id = str(uuid4())

    with use_telemetry(telemetry):
        with telemetry.span(Operation.RUN, run_id=run_id):
            cases = await asyncio.gather(
                *[
                    answer_eval._prepare_answer_case(
                        {"query_id": _SOURCE_ID_CANARY, "query": f"{_QUERY_CANARY}-{index}"},
                        **_prepare_kwargs(Client()),
                    )
                    for index in range(2)
                ]
            )
            await asyncio.gather(
                *[
                    answer_eval._evaluate_metric(
                        Metric(),
                        SimpleNamespace(),
                        semaphore=asyncio.Semaphore(2),
                        telemetry_case_id=case._telemetry_case_id,
                    )
                    for case in cases
                ]
            )

    spans = telemetry.finished_spans
    run_span = next(span for span in spans if span.name == "run")
    phase_spans = [span for span in spans if span.name in {"retrieval", "generation", "evaluation"}]
    case_ids = {
        span.attributes["telemetry.case_id"]
        for span in phase_spans
        if "telemetry.case_id" in span.attributes
    }
    assert len(case_ids) == 2
    assert _SOURCE_ID_CANARY not in case_ids
    for case_id in case_ids:
        assert {
            span.name for span in phase_spans if span.attributes.get("telemetry.case_id") == case_id
        } == {"retrieval", "generation", "evaluation"}
    assert all(span.attributes["telemetry.run_id"] == run_id for span in spans)
    assert all(span.parent.span_id == run_span.context.span_id for span in phase_spans)
    worker_spans = [span for span in spans if span.name == "search"]
    assert len(worker_spans) == 2
    assert all(span.attributes["telemetry.case_id"] in case_ids for span in worker_spans)
    assert all(
        span.parent.span_id
        == next(
            phase.context.span_id
            for phase in phase_spans
            if phase.name == "retrieval"
            and phase.attributes["telemetry.case_id"] == span.attributes["telemetry.case_id"]
        )
        for span in worker_spans
    )
    generation_spans = [span for span in phase_spans if span.name == "generation"]
    assert all(
        span.attributes["usage.completeness"] == UsageCompleteness.UNKNOWN.value
        and "usage.input_tokens" not in span.attributes
        and "usage.output_tokens" not in span.attributes
        for span in generation_spans
    )
    serialized = _serialize_spans(telemetry)
    for canary in (_SOURCE_ID_CANARY, _QUERY_CANARY, _SOURCE_CANARY, _ANSWER_CANARY):
        assert canary not in serialized


@pytest.mark.asyncio
async def test_metric_retries_get_fresh_attempt_ids_and_only_real_retry_metadata(monkeypatch):
    monkeypatch.setattr(answer_eval, "safe_a_measure", None)

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(answer_eval.asyncio, "sleep", no_wait)
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    case_id = str(uuid4())

    class Metric:
        score = 0.8
        reason = None
        error = None
        calls = 0

        async def a_measure(self, test_case):
            self.calls += 1
            self.error = "synthetic judge diagnostic" if self.calls == 1 else None

    with use_telemetry(telemetry):
        with telemetry.span(Operation.RUN, run_id=str(uuid4())):
            result = await answer_eval._evaluate_metric(
                Metric(),
                SimpleNamespace(),
                semaphore=asyncio.Semaphore(1),
                telemetry_case_id=case_id,
            )

    attempts = [span for span in telemetry.finished_spans if span.name in {"evaluation", "retry"}]
    assert result["status"] == "ok"
    assert [span.name for span in attempts] == ["evaluation", "retry"]
    assert len({span.attributes["telemetry.attempt_id"] for span in attempts}) == 2
    assert all(span.attributes["telemetry.case_id"] == case_id for span in attempts)
    assert "telemetry.retry_count" not in attempts[0].attributes
    assert attempts[1].attributes["telemetry.retry_count"] == 1
    assert all(span.attributes["telemetry.stage"] == Stage.JUDGING.value for span in attempts)
    assert all(
        span.attributes["usage.completeness"] == UsageCompleteness.UNKNOWN.value
        and "usage.input_tokens" not in span.attributes
        and "usage.output_tokens" not in span.attributes
        for span in attempts
    )
    assert "synthetic judge diagnostic" not in _serialize_spans(telemetry)


def test_caught_retrieval_failure_finishes_error_span_without_exception_text(monkeypatch):
    import src.rag.runtime as runtime

    telemetry = Telemetry(TelemetryConfig(mode="local"))

    def failed_retrieval(query, top_k, retrieval_options=None):
        raise RuntimeError(f"{_EXCEPTION_CANARY} {_QUERY_CANARY} {_SOURCE_CANARY}")

    monkeypatch.setattr(runtime, "retrieve_context_with_trace", failed_retrieval)
    with use_telemetry(telemetry):
        with telemetry.span(Operation.RUN, run_id=str(uuid4())):
            rows, _ = evaluate_retrieval(
                [{"query_id": _SOURCE_ID_CANARY, "query": _QUERY_CANARY}], top_k=2
            )

    retrieval_span = next(span for span in telemetry.finished_spans if span.name == "retrieval")
    assert rows[0]["case_status"] == "failed"
    assert retrieval_span.attributes["telemetry.outcome"] == "error"
    serialized = _serialize_spans(telemetry)
    for canary in (_SOURCE_ID_CANARY, _QUERY_CANARY, _SOURCE_CANARY, _EXCEPTION_CANARY):
        assert canary not in serialized


def test_retrieval_eval_uses_generated_case_ids_not_source_ids_or_content(monkeypatch):
    import src.rag.runtime as runtime

    telemetry = Telemetry(TelemetryConfig(mode="local"))

    class Trace:
        retrieval = SimpleNamespace(documents=[], score_weights={})
        total_time_ms = 1

        def model_dump(self):
            return {"query": _QUERY_CANARY, "source": _SOURCE_CANARY}

    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda query, top_k, retrieval_options=None: (
            _SOURCE_CANARY,
            [_SOURCE_CANARY],
            Trace(),
        ),
    )
    with use_telemetry(telemetry):
        with telemetry.span(Operation.RUN, run_id=str(uuid4())):
            evaluate_retrieval([{"query_id": _SOURCE_ID_CANARY, "query": _QUERY_CANARY}], top_k=2)

    retrieval_span = next(span for span in telemetry.finished_spans if span.name == "retrieval")
    assert retrieval_span.attributes["telemetry.case_id"] != _SOURCE_ID_CANARY
    serialized = _serialize_spans(telemetry)
    for canary in (_SOURCE_ID_CANARY, _QUERY_CANARY, _SOURCE_CANARY):
        assert canary not in serialized


@pytest.mark.asyncio
async def test_failed_and_cancelled_answer_stages_end_without_exception_text(monkeypatch):
    import src.rag.runtime as runtime

    telemetry = Telemetry(TelemetryConfig(mode="local"))

    def failed_retrieval(query, top_k, retrieval_options=None):
        raise RuntimeError(f"{_EXCEPTION_CANARY} {_QUERY_CANARY} {_SOURCE_CANARY}")

    class SuccessfulClient:
        async def a_generate(self, prompt, context):
            return _ANSWER_CANARY

    class CancelledClient:
        async def a_generate(self, prompt, context):
            raise asyncio.CancelledError(_EXCEPTION_CANARY)

    monkeypatch.setattr(runtime, "retrieve_context_with_trace", failed_retrieval)
    with use_telemetry(telemetry):
        with telemetry.span(Operation.RUN, run_id=str(uuid4())):
            with pytest.raises(RuntimeError):
                await answer_eval._prepare_answer_case(
                    {"query_id": _SOURCE_ID_CANARY, "query": _QUERY_CANARY},
                    **_prepare_kwargs(SuccessfulClient()),
                )

            monkeypatch.setattr(
                runtime,
                "retrieve_context_with_trace",
                lambda query, top_k, retrieval_options=None: (_SOURCE_CANARY, [], {}),
            )
            with pytest.raises(asyncio.CancelledError):
                await answer_eval._prepare_answer_case(
                    {"query_id": _SOURCE_ID_CANARY, "query": _QUERY_CANARY},
                    **_prepare_kwargs(CancelledClient()),
                )

    retrieval_spans = [span for span in telemetry.finished_spans if span.name == "retrieval"]
    generation_span = next(span for span in telemetry.finished_spans if span.name == "generation")
    assert retrieval_spans[0].attributes["telemetry.outcome"] == "error"
    assert generation_span.attributes["telemetry.outcome"] == "cancelled"
    assert generation_span.attributes["telemetry.error_code"] == "cancelled"
    serialized = _serialize_spans(telemetry)
    for canary in (
        _SOURCE_ID_CANARY,
        _QUERY_CANARY,
        _SOURCE_CANARY,
        _ANSWER_CANARY,
        _EXCEPTION_CANARY,
    ):
        assert canary not in serialized
