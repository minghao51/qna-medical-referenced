"""Offline regressions for the Pydantic Evals task layer (P4-C).

Fakes only: no providers, no judges, no network, no live calls. Content fixtures
are synthetic canaries that must never reach a non-approved projection.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from pydantic_evals.evaluators import Evaluator, EvaluatorContext
from pydantic_evals.reporting import EvaluationReportAdapter

from src.evals import pydantic_tasks
from src.evals.artifacts import ArtifactStore
from src.evals.metrics import medical

RETRIEVAL_CONTEXT = "synthetic evidence"
CANARY_SECRET = "CANARY-SECRET-DO-NOT-EXPORT"
CANARY_PATIENT = "PATIENT-JANE-DOE"


@pytest.fixture(autouse=True)
def synthetic_retrieval(monkeypatch):
    """Replace the retrieval leaf so generation runs fully offline."""
    import src.rag.runtime as runtime

    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda *args, **kwargs: (RETRIEVAL_CONTEXT, [], {}),
    )
    return RETRIEVAL_CONTEXT


class _FakeClient:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.prompts: list[str] = []
        self.contexts: list[str] = []

    async def a_generate(self, prompt: str, context: str = "") -> str:
        self.prompts.append(prompt)
        self.contexts.append(context)
        return self.answer


class _RecordingClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.session_ids: list[str | None] = []

    async def a_generate(self, prompt: str, context: str = "") -> str:
        from src.infra.llm.conversation_context import get_conversation_id

        self.prompts.append(prompt)
        self.session_ids.append(get_conversation_id())
        return f"answer to {prompt}"


class _RecordingModelSettingsAgent:
    """Stand-in for the adapter's text agent that records per-call model settings."""

    def __init__(self) -> None:
        self.model_settings: list[Any] = []

    async def run(self, user_prompt: str, *, model_settings: Any = None) -> Any:
        self.model_settings.append(model_settings)
        return SimpleNamespace(
            output="synthetic answer",
            usage=SimpleNamespace(input_tokens=1, output_tokens=1, total_tokens=2),
        )


class _MetricsLedger:
    """Counts metric construction, judging calls, and model closes across a run."""

    def __init__(self, *, score: float = 0.9, raising_index: int | None = None) -> None:
        self.score = score
        self.raising_index = raising_index
        self.created = 0
        self.calls = 0
        self.closes = 0

    def factory(self, owned_models: list[Any] | None = None) -> list[Any]:
        metrics: list[Any] = []
        for index in range(len(medical.METRIC_SPECS)):
            if index == self.raising_index:
                metrics.append(_RaisingMetric())
            else:
                metrics.append(_FakeMetric(score=self.score, ledger=self))
        self.created += len(metrics)
        if owned_models is not None:
            owned_models.extend(
                model for model in (getattr(metric, "model", None) for metric in metrics) if model
            )
        return metrics


class _ClosableModel:
    def __init__(self, ledger: _MetricsLedger) -> None:
        self.ledger = ledger

    async def aclose(self) -> None:
        self.ledger.closes += 1


class _FakeMetric:
    def __init__(
        self,
        score: float = 0.9,
        reason: str | None = None,
        ledger: _MetricsLedger | None = None,
    ) -> None:
        self.score = score
        self.reason = reason
        self.error = None
        self.ledger = ledger or _MetricsLedger()
        self.model = _ClosableModel(self.ledger)

    async def a_measure(self, *args: Any, **kwargs: Any) -> float:
        self.ledger.calls += 1
        return self.score


class _RaisingMetric:
    score: float | None = None
    reason: str | None = None
    error: str | None = None

    async def a_measure(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("synthetic judge failure")


@dataclass(repr=False)
class _PartialEvaluator(Evaluator[dict[str, Any], Any, dict[str, Any]]):
    """Returns only one of the required metrics, leaving the rest unmeasured."""

    def evaluate(
        self, ctx: EvaluatorContext[dict[str, Any], Any, dict[str, Any]]
    ) -> dict[str, float]:
        return {pydantic_tasks.REQUIRED_EVALUATORS[0]: 0.5}


def _records(*, count: int = 1) -> list[dict[str, Any]]:
    return [
        {
            "query_id": f"q{index}",
            "case_id": f"c{index}",
            "query": "synthetic question",
            "query_category": "anchor",
            "answerability": "answerable",
            "label_origin": "synthetic",
            "review_status": "unreviewed",
            "source_family": "lipid",
            "expected_chunk_id": f"chunk-{index}",
        }
        for index in range(count)
    ]


def _bridge(*, score: float = 0.9, raising_index: int | None = None):
    ledger = _MetricsLedger(score=score, raising_index=raising_index)
    return pydantic_tasks.medical_metric_evaluator(metric_factory=ledger.factory), ledger


async def _evaluate(
    *,
    evaluators: Sequence[Any] = (),
    records: Sequence[Mapping[str, Any]] | None = None,
    answer: str = "synthetic answer",
    task: Any = None,
):
    dataset = pydantic_tasks.build_dataset(
        _records() if records is None else records, evaluators=list(evaluators)
    )
    resolved_task = task or pydantic_tasks.baseline_answer_task(llm_client=_FakeClient(answer))
    return await dataset.evaluate(resolved_task, name="synthetic-run", progress=False)


async def _canary_report():
    records = _records(count=2)
    records[0]["query"] = f"{CANARY_SECRET} synthetic question"
    bridge, _ = _bridge()
    baseline = pydantic_tasks.baseline_answer_task(
        llm_client=_FakeClient(f"{CANARY_PATIENT} synthetic answer")
    )

    async def task(inputs: dict[str, Any]):
        if inputs["case_id"] == "c1":
            raise RuntimeError("synthetic task failure")
        return await baseline(inputs)

    return await _evaluate(evaluators=[bridge], records=records, task=task)


def _case_inputs(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": record["case_id"],
        "query_id": record["query_id"],
        "query": record["query"],
    }


def test_build_dataset_keeps_inputs_frozen_and_provenance_in_metadata():
    record = _records()[0]
    dataset = pydantic_tasks.build_dataset([record])
    case = dataset.cases[0]

    assert case.name == record["case_id"]
    assert case.inputs == _case_inputs(record)
    assert case.metadata == {
        "query_category": "anchor",
        "answerability": "answerable",
        "label_origin": "synthetic",
        "review_status": "unreviewed",
        "source_family": "lipid",
        "expected_chunk_id": "chunk-0",
    }


@pytest.mark.asyncio
async def test_baseline_and_adapter_tasks_emit_same_normalized_fields():
    from src.infra.llm.pydantic_ai_client import PydanticAIClient

    class _FakeAdapterClient(PydanticAIClient):
        def __init__(self) -> None:
            self.prompts: list[str] = []
            self.contexts: list[str] = []

        async def a_generate(self, prompt: str, context: str = "") -> str:
            self.prompts.append(prompt)
            self.contexts.append(context)
            return "shared answer"

    record = _records()[0]
    baseline_client = _FakeClient("shared answer")
    adapter_client = _FakeAdapterClient()

    baseline = await pydantic_tasks.baseline_answer_task(llm_client=baseline_client)(
        _case_inputs(record)
    )
    adapter = await pydantic_tasks.adapter_answer_task(client=adapter_client)(_case_inputs(record))

    assert set(baseline.model_dump()) == set(adapter.model_dump())
    assert baseline.query_id == adapter.query_id == record["query_id"]
    assert baseline.query == adapter.query == record["query"]
    assert baseline.answer == adapter.answer == "shared answer"
    assert baseline.context == adapter.context == RETRIEVAL_CONTEXT
    assert baseline.implementation == "existing"
    assert adapter.implementation == "pydantic-ai"
    assert baseline.timings.keys() == adapter.timings.keys()
    assert set(baseline.usage) == {"usage_by_role", "unknowns"}
    assert set(adapter.usage) == {"usage_by_role", "unknowns"}
    assert baseline_client.prompts == adapter_client.prompts == [record["query"]]
    assert baseline_client.contexts == adapter_client.contexts == [RETRIEVAL_CONTEXT]


def test_adapter_task_factory_rejects_non_adapter_clients():
    with pytest.raises(TypeError):
        pydantic_tasks.adapter_answer_task(client=_FakeClient("answer"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"temperature": 0.0, "timeout_seconds": 0.5},
        {"temperature": 2.0, "timeout_seconds": 600.0},
    ],
)
async def test_adapter_task_passes_temperature_and_timeout_overrides_to_the_model_call(
    monkeypatch, overrides
):
    from src.infra.llm import pydantic_ai_client
    from src.infra.llm.pydantic_ai_client import PydanticAIClient

    monkeypatch.setattr(
        pydantic_ai_client,
        "settings",
        SimpleNamespace(
            llm=SimpleNamespace(
                pydantic_ai_model="synthetic-model",
                pydantic_ai_base_url="https://synthetic.invalid/v1",
                pydantic_ai_api_key=SecretStr("synthetic-not-a-key"),
                pydantic_ai_temperature=0.7,
                pydantic_ai_max_tokens=2048,
                pydantic_ai_timeout_seconds=30.0,
                pydantic_ai_structured_output_mode="tool",
            ),
            retry=SimpleNamespace(max_retries=1, retry_delay=0.0),
        ),
    )
    client = PydanticAIClient(model="synthetic-model", **overrides)
    agent = _RecordingModelSettingsAgent()
    client._text_agent = agent
    try:
        task = pydantic_tasks.adapter_answer_task(client=client)
        result = await task(_case_inputs(_records()[0]))
    finally:
        await client.aclose()

    assert result.answer == "synthetic answer"
    assert result.implementation == "pydantic-ai"
    assert result.usage["usage_by_role"]["generation"]["total_tokens"] == 2
    # The overrides reached the adapter's call settings, not just the constructor.
    assert client._temperature == overrides["temperature"]
    assert client._timeout == overrides["timeout_seconds"]
    assert client._http_client.timeout == httpx.Timeout(overrides["timeout_seconds"])
    assert len(agent.model_settings) == 1
    assert agent.model_settings[0]["temperature"] == overrides["temperature"]
    assert agent.model_settings[0]["max_tokens"] == 2048


@pytest.mark.asyncio
async def test_baseline_path_does_not_import_pydantic_ai_adapter():
    adapter_module = "src.infra.llm.pydantic_ai_client"
    saved = sys.modules.pop(adapter_module, None)
    try:
        module = importlib.reload(pydantic_tasks)
        assert adapter_module not in sys.modules
        result = await module.baseline_answer_task(llm_client=_FakeClient("answer"))(
            _case_inputs(_records()[0])
        )
        assert result.answer == "answer"
        assert adapter_module not in sys.modules
    finally:
        if saved is not None:
            sys.modules[adapter_module] = saved


@pytest.mark.asyncio
async def test_evaluator_bridge_runs_each_metric_once_per_case():
    bridge, ledger = _bridge(score=0.75)
    report = await _evaluate(evaluators=[bridge], records=_records(count=2))

    # A fresh metric set per case: two cases x one instance per metric spec,
    # each judged once and each closed exactly once.
    assert ledger.created == 2 * len(medical.METRIC_SPECS)
    assert ledger.calls == 2 * len(medical.METRIC_SPECS)
    assert ledger.closes == 2 * len(medical.METRIC_SPECS)
    assert len(report.cases) == 2
    expected_keys = list(pydantic_tasks.REQUIRED_EVALUATORS)
    for case in report.cases:
        assert list(case.scores) == expected_keys
        for result in case.scores.values():
            assert result.value == pytest.approx(0.75)
            assert result.evaluator_version == pydantic_tasks.MEDICAL_METRIC_EVALUATOR_VERSION
            assert result.source.name == "MedicalMetricEvaluator"
            assert result.source.arguments == {
                "metric_keys": expected_keys,
                "judge_tiers": [spec.judge_tier for spec in medical.METRIC_SPECS],
            }


def test_required_evaluators_match_medical_metric_specs():
    assert pydantic_tasks.REQUIRED_EVALUATORS == tuple(spec.key for spec in medical.METRIC_SPECS)


def test_task_module_does_not_restate_metric_rubrics():
    text = Path(pydantic_tasks.__file__).read_text(encoding="utf-8")
    for marker in (
        "Rate from 1-5",
        "You are a medical information evaluator",
        "Evaluation criteria:",
        "threshold=",
    ):
        assert marker not in text


@pytest.mark.asyncio
async def test_completeness_incomplete_when_required_evaluator_missing():
    report = await _evaluate()
    completeness = pydantic_tasks.report_completeness(report)

    assert (completeness.expected, completeness.measured, completeness.skipped) == (6, 0, 6)
    assert completeness.complete is False


@pytest.mark.asyncio
async def test_completeness_incomplete_when_metric_skipped():
    report = await _evaluate(evaluators=[_PartialEvaluator()])
    completeness = pydantic_tasks.report_completeness(report)

    assert (completeness.expected, completeness.measured, completeness.skipped) == (6, 1, 5)
    assert completeness.complete is False


@pytest.mark.asyncio
async def test_completeness_incomplete_on_evaluator_failure():
    bridge, _ = _bridge(raising_index=0)
    report = await _evaluate(evaluators=[bridge])
    completeness = pydantic_tasks.report_completeness(report)

    assert completeness.failed == 1
    assert completeness.measured == 0
    assert completeness.complete is False
    assert report.cases[0].evaluator_failures[0].error_type == "RuntimeError"


@pytest.mark.asyncio
async def test_completeness_incomplete_on_errored_case():
    async def failing_task(inputs: dict[str, Any]):
        raise RuntimeError("synthetic task failure")

    report = await _evaluate(task=failing_task)
    completeness = pydantic_tasks.report_completeness(report)

    assert (completeness.expected, completeness.errored) == (6, 1)
    assert completeness.complete is False


@pytest.mark.asyncio
async def test_completeness_complete_when_all_required_measured():
    bridge, _ = _bridge()
    report = await _evaluate(evaluators=[bridge])

    completeness = pydantic_tasks.report_completeness(report)

    assert completeness.model_dump() == {
        "expected": 6,
        "measured": 6,
        "failed": 0,
        "skipped": 0,
        "errored": 0,
        "complete": True,
    }


@pytest.mark.asyncio
async def test_raw_evaluation_report_dump_includes_case_content():
    report = await _canary_report()

    dumped = EvaluationReportAdapter.dump_json(report).decode("utf-8")

    assert CANARY_SECRET in dumped
    assert CANARY_PATIENT in dumped


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["disabled", "local", "hosted_metadata"])
async def test_projection_omits_case_content_outside_approved_mode(mode):
    report = await _canary_report()

    projected = pydantic_tasks.project_report(report, mode=mode, content_approved=False)

    assert projected["content_redacted"] is True
    case = projected["cases"][0]
    for field in ("inputs", "output", "expected_output", "error_message", "error_stacktrace"):
        assert field not in case
    for result in case["scores"].values():
        assert "reason" not in result
    failure = projected["failures"][0]
    for field in ("inputs", "expected_output", "error_message", "error_stacktrace"):
        assert field not in failure
    assert failure["name"] == "c1"
    assert case["name"] == "c0"
    assert set(case["output_summary"]) == {"implementation", "timings", "usage"}
    assert case["scores"]["factual_accuracy"]["value"] == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_projection_includes_case_content_only_when_approved():
    report = await _canary_report()

    still_redacted = pydantic_tasks.project_report(
        report, mode=pydantic_tasks.CONTENT_EXPORT_MODE, content_approved=False
    )
    assert still_redacted["content_redacted"] is True
    assert "inputs" not in still_redacted["cases"][0]

    approved = pydantic_tasks.project_report(
        report, mode=pydantic_tasks.CONTENT_EXPORT_MODE, content_approved=True
    )

    assert approved["content_redacted"] is False
    case = approved["cases"][0]
    assert case["inputs"]["query"] == f"{CANARY_SECRET} synthetic question"
    assert case["output"]["answer"] == f"{CANARY_PATIENT} synthetic answer"
    assert case["expected_output"] is None
    assert "reason" in case["scores"]["factual_accuracy"]
    failure = approved["failures"][0]
    assert failure["inputs"]["query"] == "synthetic question"
    assert failure["error_message"] == "RuntimeError: synthetic task failure"
    assert "synthetic task failure" in failure["error_stacktrace"]


@pytest.mark.asyncio
async def test_projection_never_exports_canary_content_without_approval():
    report = await _canary_report()

    for mode in ("disabled", "local", "hosted_metadata", pydantic_tasks.CONTENT_EXPORT_MODE):
        serialized = json.dumps(
            pydantic_tasks.project_report(report, mode=mode, content_approved=False)
        )
        assert CANARY_SECRET not in serialized
        assert CANARY_PATIENT not in serialized


@pytest.mark.asyncio
async def test_write_report_persists_redacted_projection(tmp_path):
    report = await _canary_report()
    store = ArtifactStore(tmp_path, "pydantic-evals")

    path = pydantic_tasks.write_report(store, report, mode="local", content_approved=False)

    content = path.read_text(encoding="utf-8")
    payload = json.loads(content)
    assert payload["content_redacted"] is True
    # One case errored on purpose, so the stored report is honestly incomplete.
    assert payload["completeness"]["complete"] is False
    assert payload["completeness"]["errored"] == 1
    assert "output" not in payload["cases"][0]
    assert CANARY_SECRET not in content
    assert CANARY_PATIENT not in content


@pytest.mark.asyncio
async def test_multi_turn_replay_keeps_per_case_sessions_isolated():
    from src.infra.llm.conversation_context import get_conversation_id

    client = _RecordingClient()
    task = pydantic_tasks.multi_turn_replay_task(llm_client=client)
    turns = [{"role": "user", "content": f"question {index}"} for index in range(3)]

    first = await task({"case_id": "case-a", "turns": turns})
    second = await task({"case_id": "case-b", "turns": turns})

    assert first.turns == ["question 0", "question 1", "question 2"]
    assert first.answers == [f"answer to question {index}" for index in range(3)]
    assert second.answers == first.answers
    assert first.session_id != second.session_id
    assert {first.session_id, second.session_id}.isdisjoint({"case-a", "case-b"})
    assert client.session_ids[:3] == [first.session_id] * 3
    assert client.session_ids[3:] == [second.session_id] * 3
    assert client.prompts[:3] == first.turns
    assert get_conversation_id() is None


@pytest.mark.asyncio
async def test_multi_turn_replay_is_bounded():
    client = _RecordingClient()
    task = pydantic_tasks.multi_turn_replay_task(llm_client=client, max_turns=2)
    turns = [{"role": "user", "content": f"question {index}"} for index in range(3)]

    with pytest.raises(ValueError):
        await task({"case_id": "case-a", "turns": turns})

    assert client.prompts == []


class _RequestScopedMetric:
    """Stateful judge metric whose score depends on the case being judged.

    Mirrors DeepEval's instance-state mutation; sharing one instance across
    concurrently evaluated cases would let the last writer win.
    """

    score: float | None = None
    reason: str | None = None
    error: str | None = None

    async def a_measure(self, test_case: Any, *args: Any, **kwargs: Any) -> float:
        self.score = 1.0 if "first" in test_case.input else 0.0
        await asyncio.sleep(0.01)
        return self.score


@dataclass(repr=False)
class _LabelEvaluator(Evaluator[dict[str, Any], Any, dict[str, Any]]):
    """Emits model-generated text as a label, which the export gate must treat as content."""

    def evaluate(
        self, ctx: EvaluatorContext[dict[str, Any], Any, dict[str, Any]]
    ) -> dict[str, str]:
        return {"generated_label": f"{CANARY_SECRET} generated label"}


@pytest.mark.asyncio
async def test_evaluator_bridge_keeps_per_case_scores_under_concurrency():
    bridge = pydantic_tasks.medical_metric_evaluator(
        metric_factory=lambda _owned=None: [_RequestScopedMetric() for _ in medical.METRIC_SPECS]
    )
    records = _records(count=2)
    records[0]["query"] = "first synthetic question"
    records[1]["query"] = "second synthetic question"

    report = await _evaluate(evaluators=[bridge], records=records)

    scores = {case.name: case.scores["factual_accuracy"].value for case in report.cases}
    assert scores == {"c0": 1.0, "c1": 0.0}
    assert pydantic_tasks.report_completeness(report).complete is True


@pytest.mark.asyncio
async def test_evaluator_bridge_closes_metric_models_when_a_required_metric_fails():
    bridge, ledger = _bridge(raising_index=0)
    report = await _evaluate(evaluators=[bridge], records=_records(count=1))

    assert report.cases[0].evaluator_failures
    # Every built metric is closed, including the ones a failing metric prevented
    # from running; the raising stand-in owns no transport.
    assert ledger.closes == len(medical.METRIC_SPECS) - 1


@pytest.mark.asyncio
async def test_projection_redacts_string_label_values_without_approval():
    report = await _evaluate(evaluators=[_LabelEvaluator()], records=_records(count=1))

    redacted = pydantic_tasks.project_report(report, mode="local", content_approved=False)
    label = redacted["cases"][0]["labels"]["generated_label"]
    assert label["value_redacted"] is True
    assert "value" not in label
    assert CANARY_SECRET not in json.dumps(redacted)

    approved = pydantic_tasks.project_report(
        report, mode=pydantic_tasks.CONTENT_EXPORT_MODE, content_approved=True
    )
    assert approved["cases"][0]["labels"]["generated_label"]["value"] == (
        f"{CANARY_SECRET} generated label"
    )


def test_baseline_answer_task_requires_a_caller_owned_client():
    with pytest.raises(TypeError):
        pydantic_tasks.baseline_answer_task()


@pytest.mark.asyncio
async def test_projection_drops_aggregate_label_values_without_approval():
    report = await _evaluate(evaluators=[_LabelEvaluator()], records=_records(count=1))

    redacted = pydantic_tasks.project_report(report, mode="local", content_approved=False)
    assert "labels" not in redacted["averages"]


@pytest.mark.asyncio
async def test_evaluator_bridge_closes_partially_built_models_when_the_factory_raises():
    ledger = _MetricsLedger()
    first_model = _ClosableModel(ledger)

    def factory(owned_models: list[Any]) -> list[Any]:
        owned_models.append(first_model)
        raise RuntimeError("synthetic metric constructor failure")

    bridge = pydantic_tasks.medical_metric_evaluator(metric_factory=factory)
    report = await _evaluate(evaluators=[bridge], records=_records(count=1))

    assert report.cases[0].evaluator_failures
    assert ledger.closes == 1


@pytest.mark.asyncio
async def test_run_dataset_applies_the_configured_concurrency_bound(monkeypatch):
    from pydantic_evals import Dataset

    from src.config.settings import settings

    monkeypatch.setattr(settings.deepeval, "deepeval_query_concurrency", 2)
    captured: dict[str, Any] = {}

    async def fake_evaluate(self, task, **kwargs):
        captured.update(kwargs)
        captured["task"] = task
        return "synthetic-report"

    monkeypatch.setattr(Dataset, "evaluate", fake_evaluate)
    dataset = pydantic_tasks.build_dataset(_records())
    task = pydantic_tasks.baseline_answer_task(llm_client=_FakeClient("synthetic answer"))

    result = await pydantic_tasks.run_dataset(dataset, task)

    assert result == "synthetic-report"
    assert captured["max_concurrency"] == 2
    assert captured["name"] == "pydantic-evals-run"
    assert captured["task"] is task


@pytest.mark.asyncio
async def test_run_dataset_honours_an_explicit_concurrency_bound(monkeypatch):
    from pydantic_evals import Dataset

    from src.config.settings import settings

    monkeypatch.setattr(settings.deepeval, "deepeval_query_concurrency", 5)
    captured: dict[str, Any] = {}

    async def fake_evaluate(self, task, **kwargs):
        captured.update(kwargs)
        return "synthetic-report"

    monkeypatch.setattr(Dataset, "evaluate", fake_evaluate)
    dataset = pydantic_tasks.build_dataset(_records())
    task = pydantic_tasks.baseline_answer_task(llm_client=_FakeClient("synthetic answer"))

    await pydantic_tasks.run_dataset(dataset, task, max_concurrency=1, name="explicit")

    assert captured["max_concurrency"] == 1
    assert captured["name"] == "explicit"
