"""DeepEval-based answer quality evaluation helpers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from deepeval.metrics.indicator import safe_a_measure
from deepeval.test_case import LLMTestCase

from src.config import settings
from src.evals.artifacts import to_serializable
from src.evals.metrics import mean
from src.evals.metrics import medical as medical_metrics
from src.ingestion.indexing.vector_store import get_vector_store_runtime_config

logger = logging.getLogger(__name__)


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

    def to_test_case(self) -> LLMTestCase:
        return LLMTestCase(
            input=self.query,
            actual_output=self.answer,
            retrieval_context=[self.context],
        )


def _runtime_signature(
    top_k: int,
    retrieval_options: dict[str, Any] | None = None,
    cache_namespace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": int(getattr(settings, "deepeval_cache_schema_version", 1)),
        "top_k": top_k,
        "model_name": settings.model_name,
        "judge_model_light": settings.judge_model_light,
        "judge_model_heavy": settings.judge_model_heavy,
        "collection_name": settings.collection_name,
        "retrieval_options": retrieval_options or {},
        "cache_namespace": {
            **(cache_namespace or {}),
            "vector_store_runtime": get_vector_store_runtime_config(),
        },
        "faithfulness_truths_limit": settings.deepeval_faithfulness_truths_limit,
    }


def _cache_key(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _load_cache_entries(cache_path: Path | None) -> dict[str, Any]:
    if cache_path is None or not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug("Failed to load cache entries from %s: %s", cache_path, e)
        return {}
    if not isinstance(payload, dict):
        return {}
    version = int(getattr(settings, "deepeval_cache_schema_version", 1))
    if int(payload.get("schema_version", version)) != version:
        return {}
    entries = payload.get("entries", {})
    return entries if isinstance(entries, dict) else {}


def _write_cache_entries(cache_path: Path | None, cache_data: dict[str, Any]) -> None:
    if cache_path is None:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": int(getattr(settings, "deepeval_cache_schema_version", 1)),
        "entries": to_serializable(cache_data),
    }
    cache_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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
) -> AnswerQualityCase:
    from src.infra.llm import get_client
    from src.rag.runtime import retrieve_context_with_trace

    client = get_client()
    query = str(item.get("query") or "")
    query_start = time.time()
    retrieval_cached = False
    generation_cached = False

    if not query.strip():
        _, _, trace_obj = await asyncio.to_thread(
            retrieve_context_with_trace, query, max(0, top_k), retrieval_options
        )
        return AnswerQualityCase(
            query_id=item.get("query_id"),
            query=query,
            context="",
            sources=[],
            trace=_trace_to_dict(trace_obj),
            answer="",
            timings={"retrieval_ms": 0, "generation_ms": 0, "metrics_ms": 0, "total_ms": 0},
            cache={"retrieval": False, "generation": False, "metrics": False},
        )

    async with semaphore:
        retrieval_key = _cache_key({"query": query, **runtime_signature})
        retrieval_entry = retrieval_cache.get(retrieval_key) if cache_enabled else None
        retrieval_start = time.time()
        if isinstance(retrieval_entry, dict) and retrieval_entry.get("query") == query:
            context = str(retrieval_entry.get("context", ""))
            sources = list(retrieval_entry.get("sources", []))
            trace = dict(retrieval_entry.get("trace", {}))
            retrieval_cached = True
        else:
            context, sources, trace_obj = await asyncio.to_thread(
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
                "generator_model": settings.model_name,
                **runtime_signature,
            }
        )
        generation_entry = generation_cache.get(generation_key) if cache_enabled else None
        generation_start = time.time()
        if isinstance(generation_entry, dict) and generation_entry.get("query") == query:
            answer = str(generation_entry.get("answer", ""))
            generation_cached = True
        else:
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
    )


async def _evaluate_metric(
    metric: Any,
    test_case: LLMTestCase,
    *,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    async with semaphore:
        started = time.time()
        score: float | None = None
        reason = None
        error = None
        status = "ok"
        max_retries = 2
        timeout_seconds = max(1, int(getattr(settings, "deepeval_metric_timeout_seconds", 90)))

        for attempt in range(max_retries):
            try:
                await asyncio.wait_for(
                    safe_a_measure(
                        metric,
                        test_case,
                        ignore_errors=False,
                        skip_on_missing_params=False,
                    ),
                    timeout=timeout_seconds,
                )
                score = metric.score if metric.score is not None else None
                reason = getattr(metric, "reason", None)
                error = getattr(metric, "error", None)
                if error is not None or score is None:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1 * (attempt + 1))
                        continue
                    status = "error"
                break
            except TimeoutError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                error = f"metric_timeout:{timeout_seconds}s (after {max_retries} retries)"
                reason = getattr(metric, "reason", None)
                status = "error"
                break
            except Exception as exc:
                error = str(exc)
                reason = getattr(metric, "reason", None)
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


async def _evaluate_case_metrics(
    case: AnswerQualityCase,
    *,
    runtime_signature: dict[str, Any],
    metric_cache: dict[str, Any],
    metric_cache_enabled: bool,
    metric_concurrency: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, float | None], bool]:
    cache_key = _metric_cache_key(case, runtime_signature)
    cached_payload = metric_cache.get(cache_key) if metric_cache_enabled else None
    if isinstance(cached_payload, dict):
        cached_metrics = cached_payload.get("metrics")
        cached_scores = cached_payload.get("score_updates")
        if isinstance(cached_metrics, dict) and isinstance(cached_scores, dict):
            cached_metric_results = {
                key: {**dict(value), "cached": True}
                for key, value in cached_metrics.items()
                if isinstance(value, dict)
            }
            score_updates = {
                str(key): (float(value) if value is not None else None)
                for key, value in cached_scores.items()
            }
            return cached_metric_results, score_updates, True

    metric_instances = medical_metrics.create_medical_metrics()
    metric_map = {
        spec.key: metric
        for spec, metric in zip(medical_metrics.METRIC_SPECS, metric_instances, strict=True)
    }
    semaphore = asyncio.Semaphore(metric_concurrency)
    payloads = await asyncio.gather(
        *[
            _evaluate_metric(metric_map[spec.key], case.to_test_case(), semaphore=semaphore)
            for spec in medical_metrics.METRIC_SPECS
        ]
    )
    metric_results = {
        spec.key: payload
        for spec, payload in zip(medical_metrics.METRIC_SPECS, payloads, strict=True)
    }
    score_updates = {key: payload["score"] for key, payload in metric_results.items()}
    if metric_cache_enabled:
        metric_cache[cache_key] = {
            "metrics": metric_results,
            "score_updates": score_updates,
        }
    return metric_results, score_updates, False


def _aggregate_metric_results(
    score_buckets: dict[str, list[float]],
    error_buckets: dict[str, int],
    total_queries: int,
    query_count_scored: int,
) -> dict[str, Any]:
    metric_count = len(medical_metrics.METRIC_SPECS)
    metric_evaluations_total = total_queries * metric_count
    metric_evaluations_failed = sum(error_buckets.values())
    metric_evaluations_ok = metric_evaluations_total - metric_evaluations_failed
    return {
        "status": "degraded" if metric_evaluations_failed else "ok",
        "query_count": total_queries,
        "query_count_scored": query_count_scored,
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
                "mean": mean(values),
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
    if not settings.dashscope_api_key or settings.dashscope_api_key == "test-api-key":
        return [], {"status": "skipped", "reason": "missing_dashscope_api_key"}

    top_k = max(0, int(top_k))

    query_concurrency = max(1, int(getattr(settings, "deepeval_query_concurrency", 2)))
    metric_concurrency = max(1, int(getattr(settings, "deepeval_metric_concurrency", 3)))
    cache_enabled = bool(getattr(settings, "deepeval_answer_cache_enabled", True))
    metric_cache_enabled = bool(getattr(settings, "deepeval_metric_cache_enabled", True))
    resolved_cache_dir = cache_dir or Path(
        getattr(settings, "deepeval_cache_dir", "data/evals/cache")
    )
    retrieval_cache_path, generation_cache_path, _ = _resolve_cache_paths(
        resolved_cache_dir if cache_enabled else None
    )
    _, _, metric_cache_path = _resolve_cache_paths(
        resolved_cache_dir if metric_cache_enabled else None
    )
    retrieval_cache = _load_cache_entries(retrieval_cache_path) if cache_enabled else {}
    generation_cache = _load_cache_entries(generation_cache_path) if cache_enabled else {}
    metric_cache = _load_cache_entries(metric_cache_path) if metric_cache_enabled else {}
    runtime_signature = _runtime_signature(
        top_k,
        retrieval_options=retrieval_options,
        cache_namespace=cache_namespace,
    )
    query_semaphore = asyncio.Semaphore(query_concurrency)
    score_buckets: dict[str, list[float]] = {spec.key: [] for spec in medical_metrics.METRIC_SPECS}
    error_buckets = {spec.key: 0 for spec in medical_metrics.METRIC_SPECS}
    query_count_scored = 0

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
        )
        metrics_started = time.time()
        metric_results, score_updates, metrics_cached = await _evaluate_case_metrics(
            case,
            runtime_signature=runtime_signature,
            metric_cache=metric_cache,
            metric_cache_enabled=metric_cache_enabled,
            metric_concurrency=metric_concurrency,
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
    for result in await asyncio.gather(*[_evaluate_item(item) for item in dataset]):
        score_updates = result.pop("_score_updates", {})
        scored_this_query = False
        for metric_key, score in score_updates.items():
            metric_payload = result["metrics"].get(metric_key, {})
            if metric_payload.get("status") == "ok" and score is not None:
                score_buckets.setdefault(metric_key, []).append(score)
                scored_this_query = True
            else:
                error_buckets[metric_key] = error_buckets.get(metric_key, 0) + 1
        if scored_this_query:
            query_count_scored += 1
        results.append(result)

    if cache_enabled:
        _write_cache_entries(retrieval_cache_path, retrieval_cache)
        _write_cache_entries(generation_cache_path, generation_cache)
    if metric_cache_enabled:
        _write_cache_entries(metric_cache_path, metric_cache)

    aggregate = _aggregate_metric_results(
        score_buckets, error_buckets, len(results), query_count_scored
    )
    return results, aggregate


def evaluate_answer_quality(
    dataset: list[dict[str, Any]],
    top_k: int,
    cache_dir: Path | None = None,
    retrieval_options: dict[str, Any] | None = None,
    cache_namespace: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
