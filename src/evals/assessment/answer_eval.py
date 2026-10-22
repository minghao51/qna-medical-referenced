"""DeepEval-based answer quality evaluation helpers."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import anyio

from src.config import settings
from src.evals.artifacts import atomic_write_text, to_serializable
from src.evals.metrics import mean
from src.infra.telemetry import (
    ErrorCode,
    Operation,
    Stage,
    UsageCompleteness,
    telemetry_operation,
)
from src.ingestion.indexing.chroma_store import get_vector_store_runtime_config

logger = logging.getLogger(__name__)

# New envelopes are attempt-local diagnostics, not verified replay snapshots.
ANSWER_CACHE_SCHEMA_VERSION = 3
ANSWER_CACHE_CONTRACT_VERSION = 1

if TYPE_CHECKING:
    from deepeval.test_case import LLMTestCase

safe_a_measure: Callable[..., Awaitable[Any]] | None
try:
    from deepeval.metrics import indicator as _indicator_module
except ModuleNotFoundError:
    safe_a_measure = None
else:
    safe_a_measure = cast("Callable[..., Awaitable[Any]]", _indicator_module.safe_a_measure)


@dataclass(frozen=True)
class AnswerQualityCase:
    query_id: str | None
    query: str
    context: str
    sources: list[Any]
    trace: dict[str, Any]
    answer: str
    timings: dict[str, int]
    cache: dict[str, bool]
    _telemetry_case_id: str = field(default_factory=lambda: str(uuid4()), repr=False, compare=False)

    def to_test_case(self) -> LLMTestCase:
        try:
            from deepeval.test_case import LLMTestCase

            return LLMTestCase(
                input=self.query,
                actual_output=self.answer,
                retrieval_context=[self.context],
            )
        except ModuleNotFoundError:
            return cast(
                "LLMTestCase",
                SimpleNamespace(
                    input=self.query,
                    actual_output=self.answer,
                    retrieval_context=[self.context],
                ),
            )


def _runtime_signature(
    top_k: int,
    retrieval_options: dict[str, Any] | None = None,
    cache_namespace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": ANSWER_CACHE_SCHEMA_VERSION,
        "top_k": top_k,
        "generator_provider": settings.llm.provider,
        "model_name": settings.llm.model_name,
        "gemini_model_name": settings.llm.gemini_model_name,
        "openrouter_model": settings.llm.openrouter_model,
        "litellm_model": settings.llm.litellm_model,
        "judge_provider": settings.llm.judge_provider or settings.llm.provider,
        "judge_model_light": settings.llm.judge_model_light,
        "judge_model_heavy": settings.llm.judge_model_heavy,
        "judge_model_light_gemini": settings.llm.judge_model_light_gemini,
        "judge_model_heavy_gemini": settings.llm.judge_model_heavy_gemini,
        "judge_model_light_litellm": settings.llm.judge_model_light_litellm,
        "judge_model_heavy_litellm": settings.llm.judge_model_heavy_litellm,
        "judge_temperature": settings.llm.judge_temperature,
        "judge_max_tokens": settings.llm.judge_max_tokens,
        "collection_name": settings.storage.collection_name,
        "retrieval_options": retrieval_options or {},
        "cache_namespace": {
            **(cache_namespace or {}),
            "vector_store_runtime": get_vector_store_runtime_config(),
        },
        "faithfulness_truths_limit": settings.deepeval.deepeval_faithfulness_truths_limit,
    }


def _cache_key(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _write_cache_entries(cache_path: Path | None, cache_data: dict[str, Any]) -> None:
    if cache_path is None:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": ANSWER_CACHE_SCHEMA_VERSION,
        "cache_contract_version": ANSWER_CACHE_CONTRACT_VERSION,
        "mode": "fresh",
        "reusable": False,
        "entries": to_serializable(cache_data),
    }
    atomic_write_text(
        cache_path, json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False)
    )


def _resolve_cache_paths(
    cache_dir: Path | None,
) -> tuple[Path | None, Path | None, Path | None]:
    if cache_dir is None:
        return None, None, None
    return (
        cache_dir / "retrieval_cache.json",
        cache_dir / "generation_cache.json",
        cache_dir / "metric_cache.json",
    )


def _trace_to_dict(trace: Any) -> dict[str, Any]:
    if hasattr(trace, "model_dump"):
        payload = trace.model_dump()
        if isinstance(payload, dict):
            return cast(dict[str, Any], payload)
        return {}
    return trace if isinstance(trace, dict) else {}


async def _prepare_answer_case(
    item: dict[str, Any],
    *,
    top_k: int,
    retrieval_options: dict[str, Any] | None,
    runtime_signature: dict[str, Any],
    retrieval_cache: dict[str, Any],
    generation_cache: dict[str, Any],
    cache_enabled: bool,
    semaphore: asyncio.Semaphore,
    llm_client: Any,
) -> AnswerQualityCase:
    from src.rag.runtime import _run_owned_worker, retrieve_context_with_trace

    query = str(item.get("query") or "")
    if not query.strip():
        raise ValueError("Answer evaluation requires a non-empty query")
    client = llm_client
    telemetry_case_id = str(uuid4())
    query_start = time.time()
    retrieval_cached = False
    generation_cached = False

    async with semaphore:
        retrieval_key = _cache_key({"query": query, **runtime_signature})
        retrieval_start = time.time()
        with telemetry_operation(
            Operation.RETRIEVAL,
            case_id=telemetry_case_id,
            stage=Stage.SEARCH,
            error_code=ErrorCode.UPSTREAM,
        ):
            context, sources, trace_obj = await _run_owned_worker(
                retrieve_context_with_trace, query, top_k, retrieval_options
            )
        trace = _trace_to_dict(trace_obj)
        if cache_enabled:
            retrieval_cache[retrieval_key] = {
                "query": query,
                "context": context,
                "sources": to_serializable(sources),
                "trace": trace,
            }

        generation_key = _cache_key(
            {
                "query": query,
                "context": context,
                "generator_model": settings.llm.model_name,
                **runtime_signature,
            }
        )
        generation_start = time.time()
        with telemetry_operation(
            Operation.GENERATION,
            case_id=telemetry_case_id,
            stage=Stage.GENERATION,
            error_code=ErrorCode.UPSTREAM,
        ) as span:
            span.set_usage(completeness=UsageCompleteness.UNKNOWN)
            answer = await client.a_generate(prompt=query, context=context)
        if cache_enabled:
            generation_cache[generation_key] = {
                "query": query,
                "context_hash": hashlib.sha256(context.encode("utf-8")).hexdigest(),
                "answer": answer,
            }

    metrics_start = time.time()
    return AnswerQualityCase(
        query_id=item.get("query_id"),
        query=query,
        context=context,
        sources=sources,
        trace=trace,
        answer=answer,
        timings={
            "retrieval_ms": 0
            if retrieval_cached
            else int((generation_start - retrieval_start) * 1000),
            "generation_ms": 0
            if generation_cached
            else int((metrics_start - generation_start) * 1000),
            "metrics_ms": 0,
            "total_ms": int((metrics_start - query_start) * 1000),
        },
        cache={
            "retrieval": retrieval_cached,
            "generation": generation_cached,
            "metrics": False,
        },
        _telemetry_case_id=telemetry_case_id,
    )


async def _evaluate_metric(
    metric: Any,
    test_case: LLMTestCase,
    *,
    semaphore: asyncio.Semaphore,
    telemetry_case_id: str | None = None,
) -> dict[str, Any]:
    async with semaphore:
        started = time.time()
        telemetry_case_id = telemetry_case_id or str(uuid4())
        score: float | None = None
        reason = None
        error = None
        status = "ok"
        max_retries = 2
        timeout_seconds = max(1, int(settings.deepeval.deepeval_metric_timeout_seconds))
        for attempt in range(max_retries):
            attempt_id = str(uuid4())
            operation = Operation.RETRY if attempt > 0 else Operation.EVALUATION
            try:
                with telemetry_operation(
                    operation,
                    case_id=telemetry_case_id,
                    attempt_id=attempt_id,
                    stage=Stage.JUDGING,
                    retry_count=attempt if attempt > 0 else None,
                    error_code=ErrorCode.UPSTREAM,
                ) as span:
                    span.set_usage(completeness=UsageCompleteness.UNKNOWN)
                    if safe_a_measure is not None:
                        await asyncio.wait_for(
                            safe_a_measure(
                                metric,
                                test_case,
                                ignore_errors=False,
                                skip_on_missing_params=False,
                            ),
                            timeout=timeout_seconds,
                        )
                    else:
                        await asyncio.wait_for(metric.a_measure(test_case), timeout=timeout_seconds)
                    score = metric.score if metric.score is not None else None
                    reason = getattr(metric, "reason", None)
                    error = getattr(metric, "error", None)
                    if (
                        isinstance(score, bool)
                        or not isinstance(score, (int, float))
                        or not math.isfinite(score)
                    ):
                        score = None
                        error = "invalid_metric_score"
                        status = "error"
                        span.mark_error(ErrorCode.VALIDATION)
                        break
                    if error is not None:
                        span.mark_error(ErrorCode.UPSTREAM)
            except TimeoutError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                error = f"metric_timeout:{timeout_seconds}s (after {max_retries} retries)"
                reason = getattr(metric, "reason", None)
                status = "error"
                break
            except Exception:
                error = "metric_execution_failed"
                reason = None
                status = "error"
                break

            if error is not None:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                status = "error"
            break

        return {
            "status": status,
            "score": score,
            "reason": reason,
            "error": error,
            "elapsed_ms": int((time.time() - started) * 1000),
            "cached": False,
        }


def _metric_cache_key(case: AnswerQualityCase, runtime_signature: dict[str, Any]) -> str:
    return _cache_key(
        {
            "query": case.query,
            "context_hash": hashlib.sha256(case.context.encode("utf-8")).hexdigest(),
            "answer_hash": hashlib.sha256(case.answer.encode("utf-8")).hexdigest(),
            **runtime_signature,
        }
    )


async def _close_metric_models(
    metric_instances: list[Any], extra_clients: tuple[Any, ...] = ()
) -> list[BaseException]:
    models: list[Any] = []
    seen: set[int] = set()
    for metric in metric_instances:
        for attribute in ("model", "_model"):
            model = getattr(metric, attribute, None)
            if model is None or id(model) in seen or not callable(getattr(model, "aclose", None)):
                continue
            seen.add(id(model))
            models.append(model)

    for client in extra_clients:
        if id(client) not in seen and callable(getattr(client, "aclose", None)):
            seen.add(id(client))
            models.append(client)

    async def close(model: Any) -> BaseException | None:
        try:
            await model.aclose()
        except BaseException as exc:
            return exc
        return None

    results = await asyncio.gather(*(close(model) for model in models))
    return [result for result in results if result is not None]


async def _close_metric_models_preserving_primary(
    metric_instances: list[Any],
    primary_error: BaseException | None,
    *,
    extra_clients: tuple[Any, ...] = (),
) -> None:
    cleanup_task = asyncio.create_task(_close_metric_models(metric_instances, extra_clients))
    cancellation: asyncio.CancelledError | None = None
    try:
        await asyncio.shield(cleanup_task)
    except asyncio.CancelledError as exc:
        cancellation = exc
        with anyio.CancelScope(shield=True):
            while not cleanup_task.done():
                try:
                    await asyncio.shield(cleanup_task)
                except asyncio.CancelledError:
                    continue
                except BaseException:
                    break
    except BaseException:
        pass  # Retrieve the owned task's failure below without replacing the primary error.
    try:
        errors = cleanup_task.result()
    except BaseException as exc:
        errors = [exc]

    if primary_error is not None:
        for error in errors:
            primary_error.add_note(f"Judge cleanup failed: {type(error).__name__}")
        if cancellation is not None:
            primary_error.add_note("Cancellation was requested during judge cleanup")
        return
    if cancellation is not None:
        for error in errors:
            cancellation.add_note(f"Judge cleanup failed: {type(error).__name__}")
        raise cancellation
    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise BaseExceptionGroup("Judge cleanup failed", errors)


async def _evaluate_case_metrics(
    case: AnswerQualityCase,
    *,
    metric_specs: list[Any],
    metric_builder: Any,
    runtime_signature: dict[str, Any],
    metric_cache: dict[str, Any],
    metric_cache_enabled: bool,
    metric_concurrency: int,
    close_factory_owned_judges: bool = False,
) -> tuple[dict[str, dict[str, Any]], dict[str, float | None], bool]:
    cache_key = _metric_cache_key(case, runtime_signature)
    metric_instances: list[Any] = []
    owned_models: list[Any] = []
    primary_error: BaseException | None = None
    try:
        # No persistent or in-memory replay until complete semantic identity is verified.
        try:
            if (
                close_factory_owned_judges
                and "owned_models" in inspect.signature(metric_builder).parameters
            ):
                metric_instances = metric_builder(owned_models=owned_models)
            else:
                metric_instances = metric_builder()
        except ModuleNotFoundError:
            error_text = "missing_evaluation_dependency"
            metric_results: dict[str, dict[str, Any]] = {
                spec.key: {
                    "status": "error",
                    "score": None,
                    "reason": None,
                    "error": error_text,
                    "elapsed_ms": 0,
                    "cached": False,
                }
                for spec in metric_specs
            }
            score_updates: dict[str, float | None] = {spec.key: None for spec in metric_specs}
            return metric_results, score_updates, False
        metric_map = {
            spec.key: metric for spec, metric in zip(metric_specs, metric_instances, strict=True)
        }
        semaphore = asyncio.Semaphore(metric_concurrency)
        outcomes = await asyncio.gather(
            *[
                _evaluate_metric(
                    metric_map[spec.key],
                    case.to_test_case(),
                    semaphore=semaphore,
                    telemetry_case_id=case._telemetry_case_id,
                )
                for spec in metric_specs
            ],
            return_exceptions=True,
        )
        # An independently cancelled metric must not close models still in use
        # by siblings. Settle the whole group before propagating any failure.
        payloads: list[dict[str, Any]] = []
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                raise outcome
            payloads.append(outcome)
        metric_results = {
            spec.key: payload for spec, payload in zip(metric_specs, payloads, strict=True)
        }
        computed_scores: dict[str, float | None] = {}
        for key, payload in metric_results.items():
            raw_score = payload.get("score")
            computed_scores[key] = float(raw_score) if isinstance(raw_score, (int, float)) else None
        if metric_cache_enabled and all(
            payload.get("status") == "ok" and score is not None and math.isfinite(score)
            for payload, score in zip(
                metric_results.values(), computed_scores.values(), strict=True
            )
        ):
            metric_cache[cache_key] = {
                "metrics": metric_results,
                "score_updates": computed_scores,
            }
        return metric_results, computed_scores, False
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        if close_factory_owned_judges and (metric_instances or owned_models):
            await _close_metric_models_preserving_primary(
                metric_instances, primary_error, extra_clients=tuple(owned_models)
            )


def _aggregate_metric_results(
    metric_count: int,
    score_buckets: dict[str, list[float]],
    error_buckets: dict[str, int],
    total_queries: int,
    query_count_scored: int,
    query_count_complete: int,
) -> dict[str, Any]:
    metric_evaluations_total = total_queries * metric_count
    metric_evaluations_failed = sum(error_buckets.values())
    metric_evaluations_ok = metric_evaluations_total - metric_evaluations_failed
    return {
        "status": "incomplete"
        if not total_queries
        else "degraded"
        if metric_evaluations_failed
        else "ok",
        "query_count": total_queries,
        "query_count_scored": query_count_scored,
        "query_count_complete": query_count_complete,
        "query_count_failed": total_queries - query_count_complete,
        "metric_evaluations_total": metric_evaluations_total,
        "metric_evaluations_ok": metric_evaluations_ok,
        "metric_evaluations_failed": metric_evaluations_failed,
        "metric_error_rate": (
            metric_evaluations_failed / metric_evaluations_total
            if metric_evaluations_total
            else 0.0
        ),
        **{
            metric_key: {
                "mean": mean(values) if values else None,
                "count": len(values),
                "error_count": error_buckets.get(metric_key, 0),
                "error_rate": (
                    error_buckets.get(metric_key, 0) / total_queries if total_queries else 0.0
                ),
            }
            for metric_key, values in score_buckets.items()
        },
    }


async def evaluate_answer_quality_async(
    dataset: list[dict[str, Any]],
    top_k: int,
    cache_dir: Path | None = None,
    retrieval_options: dict[str, Any] | None = None,
    cache_namespace: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not dataset:
        return [], {
            "status": "incomplete",
            "reason": "empty_selected_dataset",
            "query_count": 0,
            "query_count_scored": 0,
            "query_count_complete": 0,
            "query_count_failed": 0,
        }
    from src.evals.deepeval_models import resolve_judge_provider

    credential_fields = {
        "qwen": ("dashscope_api_key", "APP__LLM__DASHSCOPE_API_KEY"),
        "gemini": ("gemini_api_key", "APP__LLM__GEMINI_API_KEY"),
        "litellm": ("openrouter_api_key", "APP__LLM__OPENROUTER_API_KEY"),
    }
    selected_roles = {"generator": settings.llm.provider, "judge": resolve_judge_provider()}
    missing = []
    for role, provider in selected_roles.items():
        if provider not in credential_fields:
            raise ValueError("Unsupported answer-evaluation provider")
        field, setting_name = credential_fields[provider]
        if not getattr(settings.llm, field).get_secret_value().strip():
            missing.append({"role": role, "setting": setting_name})
    if missing:
        return [], {
            "status": "error",
            "reason": "missing_role_credentials",
            "missing_credentials": missing,
            "query_count": len(dataset),
            "query_count_scored": 0,
            "query_count_complete": 0,
            "query_count_failed": len(dataset),
        }
    from src.evals.metrics import medical as medical_metrics

    top_k = max(0, int(top_k))

    query_concurrency = max(1, int(settings.deepeval.deepeval_query_concurrency))
    metric_concurrency = max(1, int(settings.deepeval.deepeval_metric_concurrency))
    cache_enabled = bool(settings.deepeval.deepeval_answer_cache_enabled)
    metric_cache_enabled = bool(settings.deepeval.deepeval_metric_cache_enabled)
    attempt_id = uuid4().hex
    resolved_cache_dir = (cache_dir or Path(settings.deepeval.deepeval_cache_dir)) / attempt_id
    retrieval_cache_path, generation_cache_path, _ = _resolve_cache_paths(
        resolved_cache_dir if cache_enabled else None
    )
    _, _, metric_cache_path = _resolve_cache_paths(
        resolved_cache_dir if metric_cache_enabled else None
    )
    retrieval_cache: dict[str, Any] = {}
    generation_cache: dict[str, Any] = {}
    metric_cache: dict[str, Any] = {}
    runtime_signature = _runtime_signature(
        top_k,
        retrieval_options=retrieval_options,
        cache_namespace=cache_namespace,
    )
    query_semaphore = asyncio.Semaphore(query_concurrency)
    metric_specs = list(medical_metrics.METRIC_SPECS)
    metric_builder = medical_metrics.create_medical_metrics
    score_buckets: dict[str, list[float]] = {spec.key: [] for spec in metric_specs}
    error_buckets = {spec.key: 0 for spec in metric_specs}
    query_count_scored = 0
    query_count_complete = 0

    async def _evaluate_item(item: dict[str, Any]) -> dict[str, Any]:
        started = time.time()
        case = await _prepare_answer_case(
            item,
            top_k=top_k,
            retrieval_options=retrieval_options,
            runtime_signature=runtime_signature,
            retrieval_cache=retrieval_cache,
            generation_cache=generation_cache,
            cache_enabled=cache_enabled,
            semaphore=query_semaphore,
            llm_client=client,
        )
        metrics_started = time.time()
        metric_results, score_updates, metrics_cached = await _evaluate_case_metrics(
            case,
            metric_specs=metric_specs,
            metric_builder=metric_builder,
            runtime_signature=runtime_signature,
            metric_cache=metric_cache,
            metric_cache_enabled=metric_cache_enabled,
            metric_concurrency=metric_concurrency,
            close_factory_owned_judges=True,
        )
        timings = dict(case.timings)
        timings["metrics_ms"] = 0 if metrics_cached else int((time.time() - metrics_started) * 1000)
        timings["total_ms"] = int((time.time() - started) * 1000)
        cache = {**case.cache, "metrics": metrics_cached}
        return {
            "query_id": case.query_id,
            "query": case.query,
            "answer": case.answer,
            "sources": case.sources,
            "trace": case.trace,
            "metrics": metric_results,
            "timings": timings,
            "cache": cache,
            "_score_updates": score_updates,
        }

    results: list[dict[str, Any]] = []
    from src.infra.llm import get_client

    client = get_client()
    primary_error: BaseException | None = None
    try:
        outcomes = await asyncio.gather(
            *[_evaluate_item(item) for item in dataset], return_exceptions=True
        )
        # gather returns child cancellations as values in this mode. Establish
        # cancellation as primary before closing shared clients, not afterward.
        for outcome in outcomes:
            if isinstance(outcome, BaseException) and not isinstance(outcome, Exception):
                raise outcome
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        await _close_metric_models_preserving_primary([], primary_error, extra_clients=(client,))
    for item, outcome in zip(dataset, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            if not isinstance(outcome, Exception):
                raise outcome
            result: dict[str, Any] = {
                "query_id": item.get("query_id"),
                "query": str(item.get("query") or ""),
                "status": "error",
                "error": "case_execution_failed",
                "answer": None,
                "metrics": {
                    spec.key: {"status": "error", "score": None, "error": "case_execution_failed"}
                    for spec in metric_specs
                },
                "_score_updates": {spec.key: None for spec in metric_specs},
            }
        else:
            result = outcome
        score_updates = result.pop("_score_updates", {})
        scored_this_query = False
        complete_this_query = bool(metric_specs)
        for metric_key, score in score_updates.items():
            metric_payload = result["metrics"].get(metric_key, {})
            if metric_payload.get("status") == "ok" and score is not None:
                score_buckets.setdefault(metric_key, []).append(score)
                scored_this_query = True
            else:
                error_buckets[metric_key] = error_buckets.get(metric_key, 0) + 1
                complete_this_query = False
        if scored_this_query:
            query_count_scored += 1
        if complete_this_query:
            query_count_complete += 1
        result["status"] = "ok" if complete_this_query else "error"
        results.append(result)

    cache_write_status = "disabled"
    if cache_enabled or metric_cache_enabled:
        try:
            resolved_cache_dir.mkdir(parents=True, exist_ok=False)
            if cache_enabled:
                _write_cache_entries(retrieval_cache_path, retrieval_cache)
                _write_cache_entries(generation_cache_path, generation_cache)
            if metric_cache_enabled:
                _write_cache_entries(metric_cache_path, metric_cache)
            cache_write_status = "written"
        except Exception:
            # Optional diagnostics must not discard completed measurements.
            logger.warning("Answer evaluation diagnostic cache write failed")
            cache_write_status = "failed"

    aggregate = _aggregate_metric_results(
        len(metric_specs),
        score_buckets,
        error_buckets,
        len(results),
        query_count_scored,
        query_count_complete,
    )
    aggregate["cache_policy"] = {
        "version": ANSWER_CACHE_CONTRACT_VERSION,
        "mode": "fresh",
        "persistent_reuse": False,
        "reason": "unverified_semantic_identity",
        "write_status": cache_write_status,
        "attempt_id": attempt_id,
        "artifact_dir": str(resolved_cache_dir) if cache_enabled or metric_cache_enabled else None,
    }
    return results, aggregate


def evaluate_answer_quality(
    dataset: list[dict[str, Any]],
    top_k: int,
    cache_dir: Path | None = None,
    retrieval_options: dict[str, Any] | None = None,
    cache_namespace: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("Use evaluate_answer_quality_async from an active event loop")
    return asyncio.run(
        evaluate_answer_quality_async(
            dataset,
            top_k,
            cache_dir=cache_dir,
            retrieval_options=retrieval_options,
            cache_namespace=cache_namespace,
        )
    )


__all__ = ["evaluate_answer_quality", "evaluate_answer_quality_async"]
