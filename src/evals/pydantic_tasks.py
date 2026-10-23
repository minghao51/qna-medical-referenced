"""Offline Pydantic Evals tasks for both generation implementations (P4-C).

The layer stays deliberately thin and reuses the existing seams:

* :func:`build_dataset` wraps already-normalized case dicts (as produced by
  ``src.evals.dataset_builder._normalize_case_record``) in a Pydantic Evals
  ``Dataset``; no new dataset file format is introduced.
* :func:`baseline_answer_task` and :func:`adapter_answer_task` call the same
  ``generate_answer_case`` seam with identical inputs and normalize the outcome
  into one result model. Both take one caller-owned client created per run
  (:func:`existing_generation_client` for the baseline): a client per case would
  leak transports. The Pydantic AI adapter is imported lazily inside the adapter
  factory only, because ``src.infra.llm.__init__`` pulls the adapter in eagerly
  and the baseline must stay evaluable without it.
* :class:`MedicalMetricEvaluator` runs the existing DeepEval medical metric
  instances; no rubric text is restated in this module. The instances are
  stateful, so a fresh set is built and closed per case — the runner evaluates
  cases concurrently and must call ``Dataset.evaluate(..., max_concurrency=...)``
  to bound provider fan-out.
* :func:`report_completeness` applies R07 semantics instead of trusting the
  runner's default success.
* :func:`project_report` is the only supported export boundary: serialized
  ``EvaluationReport`` objects carry case ``inputs``/``output`` (P4-A probe), so
  case content is exported only for approved public/synthetic content and is
  otherwise omitted entirely.
* :func:`multi_turn_replay_task` replays ordered user turns inside a per-case
  ``conversation_scope`` bound to a fresh generated UUID.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import (
    EvaluationReason,
    Evaluator,
    EvaluatorContext,
    EvaluatorOutput,
)
from pydantic_evals.reporting import EvaluationReport

from src.evals.artifacts import ArtifactStore, to_serializable
from src.evals.assessment import answer_eval
from src.evals.assessment.answer_eval import AnswerQualityCase
from src.evals.metrics import medical
from src.evals.metrics.medical import MetricSpec
from src.infra.usage import capture_usage

if TYPE_CHECKING:
    from src.infra.llm.pydantic_ai_client import PydanticAIClient

__all__ = [
    "CONTENT_EXPORT_MODE",
    "MEDICAL_METRIC_EVALUATOR_VERSION",
    "MULTI_TURN_MAX_TURNS",
    "PROVENANCE_FIELDS",
    "REQUIRED_EVALUATORS",
    "AnswerTaskResult",
    "MedicalMetricEvaluator",
    "MultiTurnReplayResult",
    "ReportCompleteness",
    "adapter_answer_task",
    "baseline_answer_task",
    "build_dataset",
    "existing_generation_client",
    "medical_metric_evaluator",
    "multi_turn_replay_task",
    "project_report",
    "report_completeness",
    "run_dataset",
    "write_report",
]

# The only telemetry mode that may export case content; mirrors the
# ``TelemetryConfig.mode`` literal in ``src.config.settings``.
CONTENT_EXPORT_MODE = "approved_public_synthetic_content"

# Required evaluator coverage (R07). These keys are the metric keys from
# ``src.evals.metrics.medical.METRIC_SPECS``; the metric definitions themselves
# stay there and are never restated here.
REQUIRED_EVALUATORS: tuple[str, ...] = (
    "factual_accuracy",
    "completeness",
    "clinical_relevance",
    "clarity",
    "answer_relevancy",
    "faithfulness",
)

# Version tag for this bridge (not for the metric definitions). Bump it when the
# judge wiring below changes so differently produced scores are not merged blindly.
MEDICAL_METRIC_EVALUATOR_VERSION = "medical-metrics-v1"

# Provenance fields carried in case metadata, matching the normalized dataset
# record contract. Content fields never become metadata.
PROVENANCE_FIELDS: tuple[str, ...] = (
    "query_category",
    "answerability",
    "label_origin",
    "review_status",
    "source_family",
    "expected_chunk_id",
    "dataset_id",
    "dataset_version",
    "dataset_split",
)

# Hard bound on replayed user turns per case.
MULTI_TURN_MAX_TURNS = 8


class AnswerTaskResult(BaseModel):
    """Normalized generation result, identical for both implementations."""

    model_config = ConfigDict(frozen=True)

    implementation: Literal["existing", "pydantic-ai"]
    query_id: str | None
    query: str
    answer: str
    context: str
    sources: list[Any]
    timings: dict[str, int]
    usage: dict[str, Any] = Field(default_factory=dict)

    def to_test_case(self) -> Any:
        """Build the judge test case through the existing answer-case mapping."""
        return AnswerQualityCase(
            query_id=self.query_id,
            query=self.query,
            context=self.context,
            sources=list(self.sources),
            trace={},
            answer=self.answer,
            timings=dict(self.timings),
            cache={},
        ).to_test_case()


class MultiTurnReplayResult(BaseModel):
    """One replayed conversation: ordered user turns and their answers."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    session_id: str
    turns: list[str]
    answers: list[str]
    timings: dict[str, int]


class ReportCompleteness(BaseModel):
    """R07 denominators for one evaluation report.

    ``expected`` counts required metric slots across successful and failed cases,
    ``measured`` counts required metric results actually present, ``skipped``
    counts slots on successful cases with no measurement (including slots lost
    when a bridge raised), ``failed`` counts evaluator failures, and ``errored``
    counts cases whose task execution raised.
    """

    model_config = ConfigDict(frozen=True)

    expected: int
    measured: int
    failed: int
    skipped: int
    errored: int
    complete: bool


AnswerTask = Callable[[dict[str, Any]], Awaitable[AnswerTaskResult]]
MultiTurnTask = Callable[[dict[str, Any]], Awaitable[MultiTurnReplayResult]]


def build_dataset(
    case_records: Sequence[Mapping[str, Any]],
    *,
    name: str = "qna-medical-cases",
    evaluators: Sequence[Evaluator[Any, Any, Any]] = (),
) -> Dataset[dict[str, Any], AnswerTaskResult, dict[str, Any]]:
    """Build a dataset from normalized case dicts, one case per record.

    Inputs carry only the frozen identifiers and query; provenance goes to
    metadata so it never has to be re-derived from the inputs.
    """
    cases: list[Case[dict[str, Any], AnswerTaskResult, dict[str, Any]]] = []
    for record in case_records:
        case_id = str(record.get("case_id") or record.get("query_id") or "")
        query = str(record.get("query") or "")
        if not case_id or not query.strip():
            raise ValueError("Pydantic Evals cases require a case identifier and a query")
        metadata = {
            field_name: record[field_name]
            for field_name in PROVENANCE_FIELDS
            if record.get(field_name) is not None
        }
        cases.append(
            Case(
                name=case_id,
                inputs={
                    "case_id": case_id,
                    "query_id": str(record.get("query_id") or case_id),
                    "query": query,
                },
                metadata=metadata,
            )
        )
    return Dataset[dict[str, Any], AnswerTaskResult, dict[str, Any]](
        name=name,
        cases=cases,
        evaluators=evaluators,
    )


def _normalize_case(
    case: AnswerQualityCase,
    implementation: Literal["existing", "pydantic-ai"],
    usage: dict[str, Any],
) -> AnswerTaskResult:
    return AnswerTaskResult(
        implementation=implementation,
        query_id=case.query_id,
        query=case.query,
        answer=case.answer,
        context=case.context,
        sources=list(case.sources),
        timings=dict(case.timings),
        usage=usage,
    )


def existing_generation_client() -> Any:
    """Resolve the configured generation client once per run; the caller closes it."""
    from src.infra.llm import get_client

    return get_client()


def baseline_answer_task(
    *,
    llm_client: Any,
    top_k: int = 5,
    retrieval_options: dict[str, Any] | None = None,
) -> AnswerTask:
    """Task for the existing generation implementation on one caller-owned client.

    The client is created once per run (:func:`existing_generation_client`) and
    closed by the caller, mirroring the legacy runner's single-client lifetime.
    """

    async def task(inputs: dict[str, Any]) -> AnswerTaskResult:
        with capture_usage() as usage:
            case = await answer_eval.generate_answer_case(
                dict(inputs),
                llm_client=llm_client,
                top_k=top_k,
                retrieval_options=retrieval_options,
            )
        return _normalize_case(case, "existing", usage.snapshot())

    return task


def adapter_answer_task(
    *,
    client: PydanticAIClient,
    top_k: int = 5,
    retrieval_options: dict[str, Any] | None = None,
) -> AnswerTask:
    """Task for the opt-in Pydantic AI adapter, on identical inputs."""
    from src.infra.llm.pydantic_ai_client import PydanticAIClient as _AdapterClient

    if not isinstance(client, _AdapterClient):
        raise TypeError("adapter task requires a PydanticAIClient instance")

    async def task(inputs: dict[str, Any]) -> AnswerTaskResult:
        with capture_usage() as usage:
            case = await answer_eval.generate_answer_case(
                dict(inputs),
                llm_client=client,
                top_k=top_k,
                retrieval_options=retrieval_options,
            )
        return _normalize_case(case, "pydantic-ai", usage.snapshot())

    return task


@dataclass(repr=False)
class MedicalMetricEvaluator(Evaluator[dict[str, Any], AnswerTaskResult, dict[str, Any]]):
    """Bridge to the existing DeepEval medical metrics.

    DeepEval metrics are stateful (they store ``score``/``reason``/``error`` on
    the instance), so a fresh set is built for every case and closed afterwards;
    cases run concurrently under the runner and must never share an instance.
    Grading runs through the existing ``_evaluate_metric`` helper (bounded
    retries, fixed error codes) and each result is named after the metric key.
    """

    metric_factory: Callable[[list[Any]], list[Any]]
    metric_specs: tuple[MetricSpec, ...]

    def get_evaluator_version(self) -> str:
        return MEDICAL_METRIC_EVALUATOR_VERSION

    def build_serialization_arguments(self) -> dict[str, Any]:
        return {
            "metric_keys": [spec.key for spec in self.metric_specs],
            "judge_tiers": [spec.judge_tier for spec in self.metric_specs],
        }

    async def evaluate(
        self, ctx: EvaluatorContext[dict[str, Any], AnswerTaskResult, dict[str, Any]]
    ) -> EvaluatorOutput:
        if not isinstance(ctx.output, AnswerTaskResult):
            raise TypeError("medical metric bridge requires an AnswerTaskResult output")
        test_case = ctx.output.to_test_case()
        # Models are registered as they are built so a constructor that raises
        # mid-factory still leaves every already-built judge transport closable.
        owned_models: list[Any] = []
        metrics: list[Any] = []
        primary_error: BaseException | None = None
        semaphore = asyncio.Semaphore(1)
        results: dict[str, EvaluationReason] = {}
        try:
            metrics = list(self.metric_factory(owned_models))
            if len(metrics) != len(self.metric_specs):
                raise ValueError("medical metric factory must return one instance per metric spec")
            for spec, metric in zip(self.metric_specs, metrics, strict=True):
                payload = await answer_eval._evaluate_metric(metric, test_case, semaphore=semaphore)
                score = payload.get("score")
                if payload.get("status") != "ok" or score is None:
                    raise RuntimeError(f"required metric {spec.key} was not measured")
                reason = payload.get("reason")
                results[spec.key] = EvaluationReason(
                    value=float(score), reason=reason if isinstance(reason, str) else None
                )
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            await answer_eval._close_metric_models_preserving_primary(
                metrics, primary_error, extra_clients=tuple(owned_models)
            )
        return results


def _default_metric_factory(owned_models: list[Any]) -> list[Any]:
    return list(medical.create_medical_metrics(owned_models=owned_models))


def medical_metric_evaluator(
    *, metric_factory: Callable[[list[Any]], list[Any]] | None = None
) -> MedicalMetricEvaluator:
    """Create the bridge; each case gets a fresh metric set from the factory.

    The factory receives the owned-model registry so partially built judge
    transports are still closed if a later constructor raises.
    """
    specs = tuple(medical.METRIC_SPECS)
    resolved = metric_factory if metric_factory is not None else _default_metric_factory
    return MedicalMetricEvaluator(metric_factory=resolved, metric_specs=specs)


def report_completeness(report: EvaluationReport[Any, Any, Any]) -> ReportCompleteness:
    """Apply R07 completeness rules to a runner-produced report."""
    required = set(REQUIRED_EVALUATORS)
    successful_slots = len(required) * len(report.cases)
    expected = len(required) * (len(report.cases) + len(report.failures))
    measured = 0
    failed = len(report.report_evaluator_failures)
    for case in report.cases:
        present = set(case.scores) | set(case.labels) | set(case.assertions)
        measured += len(present & required)
        failed += len(case.evaluator_failures)
    skipped = successful_slots - measured
    errored = len(report.failures)
    complete = bool(report.cases) and errored == 0 and failed == 0 and skipped == 0
    return ReportCompleteness(
        expected=expected,
        measured=measured,
        failed=failed,
        skipped=skipped,
        errored=errored,
        complete=complete,
    )


def _project_evaluation(result: Any, include_content: bool) -> dict[str, Any]:
    projected: dict[str, Any] = {
        "value": result.value,
        "evaluator_version": result.evaluator_version,
    }
    if include_content:
        # Judge reasons are free-form model text, so they follow case content.
        projected["reason"] = result.reason
    elif isinstance(result.value, str):
        # A string label/assertion value can be model-generated text; it follows
        # the same gate as case content instead of being exported unconditionally.
        projected.pop("value")
        projected["value_redacted"] = True
    return projected


def _project_output_summary(output: Any) -> dict[str, Any]:
    """Non-content per-case outcome: timings, usage, and shape only."""
    if isinstance(output, AnswerTaskResult):
        return {
            "implementation": output.implementation,
            "timings": dict(output.timings),
            "usage": dict(output.usage),
        }
    if isinstance(output, MultiTurnReplayResult):
        return {"turn_count": len(output.answers), "timings": dict(output.timings)}
    return {"output_type": type(output).__name__}


def _project_case(case: Any, include_content: bool) -> dict[str, Any]:
    projected: dict[str, Any] = {
        "name": case.name,
        "scores": {
            name: _project_evaluation(result, include_content)
            for name, result in case.scores.items()
        },
        "labels": {
            name: _project_evaluation(result, include_content)
            for name, result in case.labels.items()
        },
        "assertions": {
            name: _project_evaluation(result, include_content)
            for name, result in case.assertions.items()
        },
        "metrics": dict(case.metrics),
        "task_duration": case.task_duration,
        "total_duration": case.total_duration,
        "evaluator_failures": [
            {
                "name": failure.name,
                "error_type": failure.error_type,
                "evaluator_version": failure.evaluator_version,
            }
            for failure in case.evaluator_failures
        ],
    }
    if include_content:
        projected["inputs"] = to_serializable(case.inputs)
        projected["output"] = to_serializable(case.output)
        projected["expected_output"] = to_serializable(case.expected_output)
    else:
        projected["output_summary"] = _project_output_summary(case.output)
    return projected


def _project_failure(failure: Any, include_content: bool) -> dict[str, Any]:
    projected: dict[str, Any] = {"name": failure.name}
    if include_content:
        projected["inputs"] = to_serializable(failure.inputs)
        projected["expected_output"] = to_serializable(failure.expected_output)
        projected["error_message"] = failure.error_message
        projected["error_stacktrace"] = failure.error_stacktrace
    return projected


def project_report(
    report: EvaluationReport[Any, Any, Any], *, mode: str, content_approved: bool
) -> dict[str, Any]:
    """Project a report for export, dropping case content unless approved.

    Scores, labels, assertions, durations, evaluator-failure type names, metric
    identity, and aggregates are always kept. Case ``inputs``, ``output``,
    ``expected_output``, judge reasons, and failure ``error_message``/
    ``error_stacktrace`` appear only for approved public/synthetic content.
    """
    include_content = mode == CONTENT_EXPORT_MODE and bool(content_approved)
    averages = report.averages()
    averages_payload = None
    if averages is not None:
        averages_payload = averages.model_dump()
        if not include_content:
            # Aggregate label keys ARE the label values (model/evaluator text), so
            # they follow the same gate as case content.
            averages_payload.pop("labels", None)
    return {
        "report_name": report.name,
        "content_redacted": not include_content,
        "required_evaluators": list(REQUIRED_EVALUATORS),
        "metric_identity": {
            spec.key: {"display_name": spec.display_name, "judge_tier": spec.judge_tier}
            for spec in medical.METRIC_SPECS
        },
        "completeness": report_completeness(report).model_dump(),
        "cases": [_project_case(case, include_content) for case in report.cases],
        "failures": [_project_failure(failure, include_content) for failure in report.failures],
        "averages": averages_payload,
    }


async def run_dataset(
    dataset: Dataset[dict[str, Any], AnswerTaskResult, dict[str, Any]],
    task: AnswerTask,
    *,
    name: str = "pydantic-evals-run",
    max_concurrency: int | None = None,
) -> EvaluationReport[dict[str, Any], AnswerTaskResult, dict[str, Any]]:
    """Evaluate a dataset with a bounded per-case fan-out.

    The runner defaults to no limit, which would fan out every case's retrieval,
    generation, and judge calls at once; this entry applies the configured judge
    concurrency unless the caller passes an explicit bound.
    """
    from src.config.settings import settings

    limit = (
        max_concurrency
        if max_concurrency is not None
        else max(1, int(settings.deepeval.deepeval_query_concurrency))
    )
    return await dataset.evaluate(task, name=name, max_concurrency=limit, progress=False)


def write_report(
    store: ArtifactStore,
    report: EvaluationReport[Any, Any, Any],
    *,
    mode: str,
    content_approved: bool,
    relative_name: str = "pydantic_evals/report.json",
) -> Path:
    """Write the projected report through the existing artifact store."""
    return store.write_json(
        relative_name,
        project_report(report, mode=mode, content_approved=content_approved),
    )


def multi_turn_replay_task(
    *,
    llm_client: Any,
    top_k: int = 5,
    max_turns: int = MULTI_TURN_MAX_TURNS,
) -> MultiTurnTask:
    """Replay ordered user turns for one case inside an isolated conversation.

    Each task call binds a fresh generated UUID as the conversation id for the
    whole case, verifies the binding on every turn, and leaves no scope behind,
    so two cases can never share session identity or history.
    """
    from src.infra.llm.conversation_context import conversation_scope, get_conversation_id

    async def task(inputs: dict[str, Any]) -> MultiTurnReplayResult:
        case_id = str(inputs.get("case_id") or "")
        turns = [
            str(turn.get("content") or "")
            for turn in inputs.get("turns") or []
            if str(turn.get("role") or "user") == "user"
        ]
        if not case_id or not turns or any(not turn.strip() for turn in turns):
            raise ValueError("multi-turn replay requires a case identifier and non-empty turns")
        if len(turns) > max_turns:
            raise ValueError(f"multi-turn replay is bounded to {max_turns} turns per case")

        started = time.time()
        session_id = str(uuid4())
        answers: list[str] = []
        with conversation_scope(session_id):
            for turn in turns:
                if get_conversation_id() != session_id:
                    raise RuntimeError("multi-turn replay lost its per-case conversation scope")
                case = await answer_eval.generate_answer_case(
                    {"case_id": case_id, "query": turn},
                    llm_client=llm_client,
                    top_k=top_k,
                )
                answers.append(case.answer)
        if get_conversation_id() is not None:
            raise RuntimeError("multi-turn replay leaked its conversation scope")
        return MultiTurnReplayResult(
            case_id=case_id,
            session_id=session_id,
            turns=turns,
            answers=answers,
            timings={"total_ms": int((time.time() - started) * 1000)},
        )

    return task
