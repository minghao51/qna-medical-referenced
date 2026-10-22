"""Embedding helpers for the vector store using Qwen models."""

import logging
import time
from collections import OrderedDict
from collections.abc import Mapping
from threading import Lock
from time import perf_counter
from typing import Any
from uuid import uuid4

import openai
from openai import OpenAI

from src.config import settings
from src.infra.telemetry import (
    ErrorCode,
    Operation,
    Stage,
    UsageCompleteness,
    telemetry_operation,
)
from src.infra.usage import usage_call

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = settings.llm.embedding_model

_EMBEDDING_CACHE_MAX_ENTRIES = 512

# All embeddings are requested at this width (see `dimensions=` in the API call
# below) and the vector store assumes it. No settings knob exists for the
# embedding dimension yet; if the model or requested width changes, update it.
EXPECTED_EMBEDDING_DIM = 768

_EMBEDDING_TIMEOUT_SECONDS = 30.0
_RETRYABLE_EMBEDDING_ERRORS = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
)

_embedding_cache: OrderedDict[tuple[str, str], list[float]] = OrderedDict()
_embedding_cache_lock = Lock()

_MISSING = object()


def _public_field(value: Any, name: str) -> Any:
    try:
        if isinstance(value, Mapping):
            return value.get(name, _MISSING)
        return getattr(value, name, _MISSING)
    except Exception:
        return _MISSING


# Module-private origin marker: local invariant failures are tagged on the
# exception object at their raise sites so the outer classifier can tell them
# apart from provider-origin exceptions of the same built-in types.
_LOCAL_FAILURE_ATTR = "_embedding_local_failure"


def _mark_local_embedding_failure(exc: BaseException) -> None:
    """Tag a locally raised exception so the outer classifier sees its origin.

    Best effort: if the exception object rejects attributes, the tag is skipped
    and the outer classifier falls back to UPSTREAM, which is safe.
    """
    try:
        setattr(exc, _LOCAL_FAILURE_ATTR, True)
    except AttributeError:
        pass


def _is_local_embedding_failure(exc: BaseException) -> bool:
    return getattr(exc, _LOCAL_FAILURE_ATTR, False) is True


def _record_embedding_span(
    *,
    operation: Operation,
    model_name: str,
    input_count: int,
    elapsed_ms: float,
    result_count: int | None = None,
    response: Any | None = None,
    retry_count: int | None = None,
    error_code: ErrorCode | None = None,
) -> None:
    input_tokens: int | None = None
    output_tokens: int | None = None
    completeness = UsageCompleteness.UNKNOWN
    if response is not None:
        usage = _public_field(response, "usage")
        if usage is not _MISSING and usage is not None:
            raw_input = _public_field(usage, "prompt_tokens")
            if raw_input is _MISSING:
                raw_input = _public_field(usage, "input_tokens")
            raw_output = _public_field(usage, "completion_tokens")
            if raw_output is _MISSING:
                raw_output = _public_field(usage, "output_tokens")
            raw_total = _public_field(usage, "total_tokens")

            valid_input = (
                isinstance(raw_input, int) and not isinstance(raw_input, bool) and raw_input >= 0
            )
            valid_output = (
                isinstance(raw_output, int) and not isinstance(raw_output, bool) and raw_output >= 0
            )
            valid_total = (
                isinstance(raw_total, int) and not isinstance(raw_total, bool) and raw_total >= 0
            )
            input_tokens = raw_input if valid_input else None
            output_tokens = raw_output if valid_output else None
            completeness = (
                UsageCompleteness.COMPLETE
                if valid_input and valid_output and valid_total
                else UsageCompleteness.PARTIAL
            )

    with telemetry_operation(
        operation,
        stage=Stage.EMBEDDING,
        model=model_name,
        input_count=input_count,
        result_count=result_count,
        retry_count=retry_count,
        attempt_id=str(uuid4()),
        elapsed_ms=elapsed_ms,
    ) as span:
        span.set_usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            completeness=completeness,
        )
        if error_code is not None:
            span.mark_error(error_code)


def get_embedding_client() -> OpenAI:
    """Get a configured OpenAI client for Qwen embeddings.

    Returns:
        OpenAI client configured for Dashscope API
    """
    return OpenAI(
        api_key=settings.llm.dashscope_api_key.get_secret_value(),
        base_url=settings.llm.qwen_base_url,
    )


def _cache_get(model_name: str, text: str) -> list[float] | None:
    key = (model_name, text)
    with _embedding_cache_lock:
        value = _embedding_cache.get(key)
        if value is None:
            return None
        _embedding_cache.move_to_end(key)
        return list(value)


def _cache_put(model_name: str, text: str, embedding: list[float]) -> None:
    key = (model_name, text)
    with _embedding_cache_lock:
        _embedding_cache[key] = list(embedding)
        _embedding_cache.move_to_end(key)
        while len(_embedding_cache) > _EMBEDDING_CACHE_MAX_ENTRIES:
            _embedding_cache.popitem(last=False)


def _create_embeddings_with_retry(client: OpenAI, model_name: str, batch: list[str]) -> Any:
    """Call embeddings.create with a timeout and bounded retry on transient errors."""
    max_retries = max(1, int(settings.retry.max_retries))
    for attempt in range(max_retries):
        started = perf_counter()
        try:
            with usage_call(role="embedder", provider="openai") as usage:
                if usage is not None:
                    usage.mark_incomplete("provider_sdk_retry_usage_unavailable")
                response = client.embeddings.create(
                    model=model_name,
                    input=batch,
                    dimensions=EXPECTED_EMBEDDING_DIM,
                    timeout=_EMBEDDING_TIMEOUT_SECONDS,
                )
                if usage is not None:
                    usage.record_response(response)
        except _RETRYABLE_EMBEDDING_ERRORS as e:
            error_code = (
                ErrorCode.RETRY_EXHAUSTED if attempt >= max_retries - 1 else ErrorCode.UPSTREAM
            )
            _record_embedding_span(
                operation=Operation.EMBEDDING if attempt == 0 else Operation.RETRY,
                model_name=model_name,
                input_count=len(batch),
                result_count=None,
                elapsed_ms=(perf_counter() - started) * 1000,
                retry_count=attempt or None,
                error_code=error_code,
            )
            if attempt >= max_retries - 1:
                raise
            delay = settings.retry.retry_delay * (2**attempt)
            logger.warning(
                "Transient embedding error (attempt %d/%d) for model %s, retrying in %.1fs: %s",
                attempt + 1,
                max_retries,
                model_name,
                delay,
                e,
            )
            time.sleep(delay)
        except Exception:
            _record_embedding_span(
                operation=Operation.EMBEDDING if attempt == 0 else Operation.RETRY,
                model_name=model_name,
                input_count=len(batch),
                result_count=None,
                elapsed_ms=(perf_counter() - started) * 1000,
                retry_count=attempt or None,
                error_code=ErrorCode.UPSTREAM,
            )
            raise
        else:
            try:
                result_count = len(response.data)
            except Exception as exc:
                # An unparseable provider response is a local invariant failure,
                # not a provider fault.
                _mark_local_embedding_failure(exc)
                _record_embedding_span(
                    operation=Operation.EMBEDDING if attempt == 0 else Operation.RETRY,
                    model_name=model_name,
                    input_count=len(batch),
                    elapsed_ms=(perf_counter() - started) * 1000,
                    retry_count=attempt or None,
                    error_code=ErrorCode.INTERNAL,
                )
                raise
            _record_embedding_span(
                operation=Operation.EMBEDDING if attempt == 0 else Operation.RETRY,
                model_name=model_name,
                input_count=len(batch),
                result_count=result_count,
                response=response,
                retry_count=attempt or None,
                elapsed_ms=(perf_counter() - started) * 1000,
            )
            return response
    raise RuntimeError("Unexpected error in embedding retry logic")


def embed_texts_with_stats(
    texts: list[str], batch_size: int = 10, model: str | None = None
) -> tuple[list[list[float]], dict]:
    """Generate embeddings for a list of texts using Qwen.

    Args:
        texts: List of text strings to embed
        batch_size: Number of texts to process per API call

    Returns:
        List of embedding vectors (each is a list of floats)
    """
    telemetry_start = perf_counter()
    model_name = model or EMBEDDING_MODEL
    if not texts:
        _record_embedding_span(
            operation=Operation.EMBEDDING,
            model_name=model_name,
            input_count=0,
            result_count=0,
            elapsed_ms=(perf_counter() - telemetry_start) * 1000,
        )
        return [], {
            "text_count": 0,
            "batch_count": 0,
            "batch_size": batch_size,
            "embedding_model": model_name,
            "elapsed_ms": 0,
            "failure_count": 0,
        }

    start_time = time.time()
    try:
        all_embeddings: list[list[float] | None] = [None] * len(texts)
        uncached_items: list[tuple[int, str]] = []
        cache_hits = 0

        for idx, text in enumerate(texts):
            cached = _cache_get(model_name, text)
            if cached is not None:
                all_embeddings[idx] = cached
                cache_hits += 1
            else:
                uncached_items.append((idx, text))

        if uncached_items:
            client = get_embedding_client()
            for i in range(0, len(uncached_items), batch_size):
                batch_items = uncached_items[i : i + batch_size]
                batch = [text for _, text in batch_items]
                response = _create_embeddings_with_retry(client, model_name, batch)
                for (idx, text), item in zip(batch_items, response.data, strict=True):
                    embedding = item.embedding
                    if len(embedding) != EXPECTED_EMBEDDING_DIM:
                        mismatch = ValueError(
                            f"Embedding model {model_name!r} returned dimension "
                            f"{len(embedding)}, expected {EXPECTED_EMBEDDING_DIM}"
                        )
                        _mark_local_embedding_failure(mismatch)
                        raise mismatch
                    all_embeddings[idx] = embedding
                    _cache_put(model_name, text, embedding)

        resolved_embeddings = [embedding for embedding in all_embeddings if embedding is not None]
        if len(resolved_embeddings) != len(texts):
            incomplete = RuntimeError("Embedding generation returned incomplete results")
            _mark_local_embedding_failure(incomplete)
            raise incomplete

        stats = {
            "text_count": len(texts),
            "batch_count": (len(uncached_items) + batch_size - 1) // batch_size
            if uncached_items
            else 0,
            "batch_size": batch_size,
            "embedding_model": model_name,
            "elapsed_ms": int((time.time() - start_time) * 1000),
            "failure_count": 0,
            "cache_hit_count": cache_hits,
            "cache_miss_count": len(uncached_items),
        }
    except Exception as exc:
        # Terminal classification for the outer span, by origin: exceptions
        # tagged as local invariant failures at their raise sites are INTERNAL;
        # a re-raised transient error means the retry loop was exhausted
        # (RETRY_EXHAUSTED); anything else — including provider-origin
        # ValueError/RuntimeError — stays UPSTREAM. Per-attempt span codes are
        # unchanged.
        if _is_local_embedding_failure(exc):
            error_code = ErrorCode.INTERNAL
        elif isinstance(exc, _RETRYABLE_EMBEDDING_ERRORS):
            error_code = ErrorCode.RETRY_EXHAUSTED
        else:
            error_code = ErrorCode.UPSTREAM
        _record_embedding_span(
            operation=Operation.EMBEDDING,
            model_name=model_name,
            input_count=len(texts),
            elapsed_ms=(perf_counter() - telemetry_start) * 1000,
            error_code=error_code,
        )
        raise

    _record_embedding_span(
        operation=Operation.EMBEDDING,
        model_name=model_name,
        input_count=len(texts),
        result_count=len(resolved_embeddings),
        elapsed_ms=(perf_counter() - telemetry_start) * 1000,
    )
    return resolved_embeddings, stats


def embed_texts(
    texts: list[str], batch_size: int = 10, model: str | None = None
) -> list[list[float]]:
    embeddings, _ = embed_texts_with_stats(texts, batch_size=batch_size, model=model)
    return embeddings
