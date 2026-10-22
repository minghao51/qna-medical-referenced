"""Manual, allowlisted OpenTelemetry tracing with opt-in OTLP export.

This module deliberately avoids Logfire's automatic instrumentation and
high-level span context manager: those paths can capture exception details or
application arguments. It does not register a global provider and never
invokes Logfire's global ``configure()`` entry point. The hosted destination
is exported through the official
pinned ``OTLPSpanExporter``, constructed only from explicit config-derived
arguments so OTLP environment discovery cannot redirect it.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import threading
import uuid
from collections import deque
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar, Token
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import requests
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http import Compression
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanLimits, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ReadableSpan,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace import Span, Status, StatusCode

if TYPE_CHECKING:
    from src.config.settings import TelemetryConfig


class Operation(StrEnum):
    REQUEST = "request"
    RUN = "run"
    CASE = "case"
    RETRIEVAL = "retrieval"
    EXPANSION = "expansion"
    EMBEDDING = "embedding"
    SEARCH = "search"
    RERANKING = "reranking"
    GENERATION = "generation"
    RETRY = "retry"
    ERROR = "error"
    CANCELLATION = "cancellation"
    EVALUATION = "evaluation"
    CASE_CONTENT = "case_content"


class Stage(StrEnum):
    QUERY_EXPANSION = "query_expansion"
    EMBEDDING = "embedding"
    SEARCH = "search"
    RERANKING = "reranking"
    GENERATION = "generation"
    JUDGING = "judging"
    PERSISTENCE = "persistence"


class Route(StrEnum):
    CHAT = "chat"
    EVALUATION = "evaluation"
    INGESTION = "ingestion"
    CLI = "cli"


class ErrorCode(StrEnum):
    VALIDATION = "validation"
    UPSTREAM = "upstream"
    INTERNAL = "internal"
    RETRY_EXHAUSTED = "retry_exhausted"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    SHUTDOWN = "shutdown"


class UsageCompleteness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class ContentClassification(StrEnum):
    PUBLIC = "public"
    SYNTHETIC = "synthetic"


_MAX_COUNT = 1_000_000_000
_MAX_ELAPSED_MS = 86_400_000
_MAX_CONTENT_CHARS = 2_048
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")
_FORBIDDEN_IDENTIFIER = re.compile(
    r"(?:patient|mrn|cookie|authorization|auth[_-]?token|api[_-]?key|secret)", re.IGNORECASE
)
_FORBIDDEN_NUMERIC_ID = re.compile(r"\d{7,}")
# These narrow canary checks are defense-in-depth for known test markers, not
# a general secret detector or a PHI-classification mechanism.
_FORBIDDEN_CONTENT_CANARIES = (
    re.compile(r"SYNTHETIC_(?:SECRET|COOKIE|AUTH|BEARER(?:_TOKEN)?)_CANARY", re.IGNORECASE),
    re.compile(
        r"\b(?:secret|api[_ -]?key|authorization|cookie|session[_ -]?id)\s*[:=]", re.IGNORECASE
    ),
    re.compile(r"\b(?:patient|mrn)[_ -]?(?:id)?\s*[:=]", re.IGNORECASE),
    _FORBIDDEN_NUMERIC_ID,
)
# OTel 1.45.1 merges these variables into every OTLP/HTTP export regardless of
# explicit constructor arguments (extra header keys in _resolve_headers; CA
# and client-certificate material in _build_transport), so hosted construction
# fails closed instead of exporting under an unsanitized environment.
_RESIDUAL_OTLP_ENV_VARS = (
    "OTEL_EXPORTER_OTLP_HEADERS",
    "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
    "OTEL_EXPORTER_OTLP_CERTIFICATE",
    "OTEL_EXPORTER_OTLP_TRACES_CERTIFICATE",
    "OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE",
    "OTEL_EXPORTER_OTLP_TRACES_CLIENT_CERTIFICATE",
    "OTEL_EXPORTER_OTLP_CLIENT_KEY",
    "OTEL_EXPORTER_OTLP_TRACES_CLIENT_KEY",
)

_REQUEST_ID: ContextVar[str | None] = ContextVar("telemetry_request_id", default=None)
_RUN_ID: ContextVar[str | None] = ContextVar("telemetry_run_id", default=None)
_CASE_ID: ContextVar[str | None] = ContextVar("telemetry_case_id", default=None)
_ATTEMPT_ID: ContextVar[str | None] = ContextVar("telemetry_attempt_id", default=None)
_CONTEXT_IDS: tuple[tuple[str, ContextVar[str | None]], ...] = (
    ("request_id", _REQUEST_ID),
    ("run_id", _RUN_ID),
    ("case_id", _CASE_ID),
    ("attempt_id", _ATTEMPT_ID),
)


def _enum_value(enum_type: type[StrEnum], value: StrEnum | str | None, field: str) -> str | None:
    if value is None:
        return None
    try:
        return enum_type(value).value
    except (TypeError, ValueError):
        raise ValueError(f"invalid telemetry {field}") from None


def _validate_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid telemetry correlation identifier")
    try:
        parsed_uuid = uuid.UUID(value)
    except (ValueError, AttributeError):
        parsed_uuid = None
    is_generated_uuid = (
        parsed_uuid is not None
        and parsed_uuid.version == 4
        and value.lower() in {str(parsed_uuid), parsed_uuid.hex}
    )
    if (
        not _IDENTIFIER_PATTERN.fullmatch(value)
        or _FORBIDDEN_IDENTIFIER.search(value)
        or (_FORBIDDEN_NUMERIC_ID.search(value) and not is_generated_uuid)
    ):
        raise ValueError("invalid telemetry correlation identifier")
    return value


def _validate_count(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _MAX_COUNT:
        raise ValueError("invalid telemetry count")
    return value


def _validate_elapsed(value: float | None) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("invalid telemetry timing")
    try:
        elapsed = float(value)
    except (OverflowError, ValueError):
        raise ValueError("invalid telemetry timing") from None
    if not math.isfinite(elapsed) or not 0 <= elapsed <= _MAX_ELAPSED_MS:
        raise ValueError("invalid telemetry timing")
    return elapsed


def _validate_model(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not _MODEL_PATTERN.fullmatch(value)
        or "://" in value
        or _has_forbidden_canary(value)
    ):
        raise ValueError("invalid telemetry model metadata")
    return value


def _has_forbidden_canary(value: str) -> bool:
    return any(pattern.search(value) for pattern in _FORBIDDEN_CONTENT_CANARIES)


# The pinned traces exporter logs collector-controlled failure text (response
# reason, transport exception text) through this logger; while hosted export
# is active, its records are rewritten to a fixed message.
_EXPORTER_LOG_NAMESPACE = "opentelemetry.exporter.otlp.proto.http.trace_exporter"
_EXPORT_FAILURE_LOG_MESSAGE = "OTLP export attempt failed"


class _ExportLogSanitizingFilter(logging.Filter):
    """Rewrite each exporter log record to a fixed message, preserving the
    level and dropping the message content and its arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _EXPORT_FAILURE_LOG_MESSAGE
        record.args = None
        return True


_EXPORT_LOG_FILTER_LOCK = threading.Lock()
_EXPORT_LOG_FILTER: _ExportLogSanitizingFilter | None = None
_EXPORT_LOG_FILTER_DEPTH = 0


def _install_export_log_filter() -> None:
    # Raises on installation failure; hosted construction must fail closed
    # rather than keep exporting unsanitized exporter failure logs. The filter
    # is recorded only after addFilter succeeded, so a failed install never
    # leaves an untracked filter or an inflated depth behind.
    global _EXPORT_LOG_FILTER, _EXPORT_LOG_FILTER_DEPTH
    with _EXPORT_LOG_FILTER_LOCK:
        if _EXPORT_LOG_FILTER is None:
            log_filter = _ExportLogSanitizingFilter()
            logging.getLogger(_EXPORTER_LOG_NAMESPACE).addFilter(log_filter)
            _EXPORT_LOG_FILTER = log_filter
        _EXPORT_LOG_FILTER_DEPTH += 1


def _remove_export_log_filter() -> None:
    global _EXPORT_LOG_FILTER, _EXPORT_LOG_FILTER_DEPTH
    try:
        with _EXPORT_LOG_FILTER_LOCK:
            if _EXPORT_LOG_FILTER_DEPTH > 0:
                _EXPORT_LOG_FILTER_DEPTH -= 1
                if _EXPORT_LOG_FILTER_DEPTH == 0 and _EXPORT_LOG_FILTER is not None:
                    logging.getLogger(_EXPORTER_LOG_NAMESPACE).removeFilter(_EXPORT_LOG_FILTER)
                    _EXPORT_LOG_FILTER = None
    except BaseException:
        pass


class _BoundedMemoryExporter(SpanExporter):
    """Small local-only sink; it never prints, persists, or opens a connection."""

    def __init__(self, capacity: int) -> None:
        self._spans: deque[ReadableSpan] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        with self._lock:
            self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True

    def finished_spans(self) -> tuple[ReadableSpan, ...]:
        with self._lock:
            return tuple(self._spans)


class _NonThrowingExporter(SpanExporter):
    """Keep exporter exceptions and their text away from request/control flow."""

    def __init__(self, exporter: SpanExporter) -> None:
        self._exporter = exporter

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            return self._exporter.export(spans)
        except BaseException:
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        try:
            self._exporter.shutdown()
        except BaseException:
            pass

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        try:
            return self._exporter.force_flush(timeout_millis)
        except BaseException:
            return False


class TelemetrySpan:
    """Restricted metadata handle; never exposes the underlying OTel span."""

    __slots__ = ("__ended", "__finish_lock", "__outcome", "__span")

    def __init__(self, span: Span | None) -> None:
        self.__span = span
        self.__finish_lock = threading.Lock()
        self.__ended = False
        self.__outcome: str | None = None

    def set_usage(
        self,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        completeness: UsageCompleteness | str = UsageCompleteness.UNKNOWN,
    ) -> None:
        try:
            input_tokens = _validate_count(input_tokens)
            output_tokens = _validate_count(output_tokens)
            completeness_value = _enum_value(UsageCompleteness, completeness, "usage completeness")
        except (TypeError, ValueError):
            return
        if self.__span is None:
            return
        try:
            if input_tokens is not None:
                self.__span.set_attribute("usage.input_tokens", input_tokens)
            if output_tokens is not None:
                self.__span.set_attribute("usage.output_tokens", output_tokens)
            if completeness_value is not None:
                self.__span.set_attribute("usage.completeness", completeness_value)
        except BaseException:
            pass

    def set_result_count(self, count: int) -> None:
        try:
            value = _validate_count(count)
        except (TypeError, ValueError):
            return
        if self.__span is not None and value is not None:
            try:
                self.__span.set_attribute("telemetry.result_count", value)
            except BaseException:
                pass

    def mark_error(self, error_code: ErrorCode = ErrorCode.INTERNAL) -> None:
        """Mark a handled failure without ending the active span or recording its text."""
        try:
            safe_code = _enum_value(ErrorCode, error_code, "error code")
        except (TypeError, ValueError):
            return
        self._finish("error", safe_code)

    def _finish(self, outcome: str, error_code: str | None = None) -> None:
        if outcome == "success" and self.__outcome in {"error", "cancelled"}:
            return
        self.__outcome = outcome
        if self.__span is None:
            return
        try:
            self.__span.set_attribute("telemetry.outcome", outcome)
            if error_code is not None:
                self.__span.set_attribute("telemetry.error_code", error_code)
            if outcome != "success":
                self.__span.set_status(Status(StatusCode.ERROR))
        except BaseException:
            pass

    def finish(
        self,
        *,
        outcome: str = "success",
        error_code: ErrorCode | str | None = None,
    ) -> None:
        """End a manually managed span without depending on task-local context.

        The ``retry`` outcome marks a transient retry transition, not a terminal
        failure; the span status still records the failed attempt as an error.
        """
        if outcome not in {"success", "error", "cancelled", "retry"}:
            outcome = "error"
        try:
            safe_error_code = _enum_value(ErrorCode, error_code, "error code")
        except (TypeError, ValueError):
            safe_error_code = None
        if self.__span is None:
            return
        with self.__finish_lock:
            if self.__ended:
                return
            self._finish(outcome, safe_error_code)
            try:
                self.__span.end()
            except BaseException:
                pass
            self.__ended = True


class Telemetry:
    """Owner-scoped, manually instrumented telemetry lifecycle."""

    def __init__(self, config: TelemetryConfig, *, exporter: SpanExporter | None = None) -> None:
        self._config = config
        self._exporter: _BoundedMemoryExporter | SpanExporter | None = None
        self._provider: TracerProvider | None = None
        self._tracer: trace.Tracer | None = None
        self._lifecycle_lock = threading.Lock()
        self._lifecycle_thread: threading.Thread | None = None
        self._lifecycle_done = threading.Event()
        self._lifecycle_done.set()
        self._lifecycle_busy = False
        self._shutdown_requested = False
        self._closed = False
        self._lifecycle_result = True
        self._export_log_filter_installed = False

        if config.mode == "disabled":
            return
        try:
            sink: SpanExporter
            processor: SpanProcessor
            if config.export_enabled:
                if exporter is None:
                    sink = self._make_hosted_exporter()
                else:
                    sink = exporter
                processor = BatchSpanProcessor(
                    _NonThrowingExporter(sink),
                    max_queue_size=256,
                    schedule_delay_millis=500,
                    max_export_batch_size=32,
                    export_timeout_millis=max(1, int(config.shutdown_timeout_seconds * 1000)),
                    meter_provider=NoOpMeterProvider(),
                )
            else:
                sink = _BoundedMemoryExporter(config.local_span_capacity)
                processor = SimpleSpanProcessor(sink)
            self._exporter = sink
            resource_attributes: dict[str, str | int] = {
                "service.name": "qna-medical-referenced",
                "telemetry.mode": config.mode,
            }
            if config.export_enabled:
                if config.region is not None:
                    resource_attributes["telemetry.region"] = config.region
                if config.access_policy is not None:
                    resource_attributes["telemetry.access_policy"] = config.access_policy
                if config.retention_days is not None:
                    resource_attributes["telemetry.retention_days"] = config.retention_days
            self._provider = TracerProvider(
                sampler=ALWAYS_ON,
                resource=Resource(attributes=resource_attributes),
                shutdown_on_exit=False,
                span_limits=SpanLimits(
                    max_attributes=32,
                    max_events=0,
                    max_links=0,
                    max_span_attributes=32,
                    max_event_attributes=0,
                    max_link_attributes=0,
                    max_attribute_length=2_048,
                    max_span_attribute_length=2_048,
                ),
            )
            self._provider.add_span_processor(processor)
            self._tracer = self._provider.get_tracer("src.infra.telemetry", "1")
        except Exception:
            if self._export_log_filter_installed:
                _remove_export_log_filter()
                self._export_log_filter_installed = False
            self._provider = None
            self._tracer = None
            self._exporter = None

    @property
    def available(self) -> bool:
        return self._provider is not None

    @property
    def finished_spans(self) -> tuple[ReadableSpan, ...]:
        if isinstance(self._exporter, _BoundedMemoryExporter):
            return self._exporter.finished_spans()
        return ()

    def _make_hosted_exporter(self) -> SpanExporter:
        if not self._config.export_enabled or self._config.endpoint is None:
            raise ValueError("hosted telemetry is not approved")
        residual = [name for name in _RESIDUAL_OTLP_ENV_VARS if name in os.environ]
        if residual:
            raise ValueError("hosted telemetry requires a sanitized OTLP export environment")
        session = requests.Session()
        session.trust_env = False
        # Explicit arguments pin the endpoint, timeout, compression, and the
        # proxy/trust_env-off session, and explicit headers override matching
        # keys per key. OTel 1.45.1 is NOT fully neutralized by them: it still
        # merges additional OTEL_EXPORTER_OTLP_HEADERS/_TRACES_HEADERS keys
        # into every request and always reads
        # OTEL_EXPORTER_OTLP_CERTIFICATE/_TRACES_CERTIFICATE,
        # _CLIENT_CERTIFICATE/_TRACES_CLIENT_CERTIFICATE and
        # _CLIENT_KEY/_TRACES_CLIENT_KEY independently of explicit arguments,
        # so any of those residual variables fails closed above.
        # The sanitizing filter must be installed before any exporter exists:
        # an installation failure aborts hosted construction with no
        # exporter/session left behind, and if construction itself fails after
        # a successful install, the install is undone so the global filter
        # state stays consistent with the degrade path below.
        _install_export_log_filter()
        self._export_log_filter_installed = True
        try:
            return OTLPSpanExporter(
                endpoint=f"{self._config.endpoint.rstrip('/')}/v1/traces",
                headers={"Authorization": self._config.token.get_secret_value()},
                timeout=self._config.shutdown_timeout_seconds,
                compression=Compression.NoCompression,
                session=session,
                meter_provider=NoOpMeterProvider(),
            )
        except BaseException:
            _remove_export_log_filter()
            self._export_log_filter_installed = False
            raise

    def _span_attributes(
        self,
        operation: Operation | str,
        *,
        request_id: str | None = None,
        run_id: str | None = None,
        case_id: str | None = None,
        attempt_id: str | None = None,
        stage: Stage | str | None = None,
        route: Route | str | None = None,
        model: str | None = None,
        input_count: int | None = None,
        result_count: int | None = None,
        retry_count: int | None = None,
        elapsed_ms: float | None = None,
        error_code: ErrorCode | str | None = None,
    ) -> tuple[
        str | None,
        dict[str, str | int | float],
        list[tuple[ContextVar[str | None], Token[str | None]]],
    ]:
        operation_value = _enum_value(Operation, operation, "operation")
        stage_value = _enum_value(Stage, stage, "stage")
        route_value = _enum_value(Route, route, "route")
        _enum_value(ErrorCode, error_code, "error code")
        input_count = _validate_count(input_count)
        result_count = _validate_count(result_count)
        retry_count = _validate_count(retry_count)
        elapsed_ms = _validate_elapsed(elapsed_ms)
        model_value = _validate_model(model)
        supplied_ids = {
            "request_id": _validate_identifier(request_id),
            "run_id": _validate_identifier(run_id),
            "case_id": _validate_identifier(case_id),
            "attempt_id": _validate_identifier(attempt_id),
        }

        attrs: dict[str, str | int | float] = {"telemetry.operation": operation_value or ""}
        context_tokens: list[tuple[ContextVar[str | None], Token[str | None]]] = []
        for name, var in _CONTEXT_IDS:
            supplied = supplied_ids[name]
            current = supplied if supplied is not None else var.get()
            if supplied is not None:
                context_tokens.append((var, var.set(supplied)))
            if current is not None:
                attrs[f"telemetry.{name}"] = current
        if stage_value is not None:
            attrs["telemetry.stage"] = stage_value
        if route_value is not None:
            attrs["telemetry.route"] = route_value
        if model_value is not None:
            attrs["telemetry.model"] = model_value
        if input_count is not None:
            attrs["telemetry.input_count"] = input_count
        if result_count is not None:
            attrs["telemetry.result_count"] = result_count
        if retry_count is not None:
            attrs["telemetry.retry_count"] = retry_count
        if elapsed_ms is not None:
            attrs["telemetry.elapsed_ms"] = elapsed_ms
        return operation_value, attrs, context_tokens

    @contextmanager
    def span(
        self,
        operation: Operation | str,
        *,
        request_id: str | None = None,
        run_id: str | None = None,
        case_id: str | None = None,
        attempt_id: str | None = None,
        stage: Stage | str | None = None,
        route: Route | str | None = None,
        model: str | None = None,
        input_count: int | None = None,
        result_count: int | None = None,
        retry_count: int | None = None,
        elapsed_ms: float | None = None,
        error_code: ErrorCode | str | None = None,
    ) -> Iterator[TelemetrySpan]:
        try:
            operation_value, attrs, context_tokens = self._span_attributes(
                operation,
                request_id=request_id,
                run_id=run_id,
                case_id=case_id,
                attempt_id=attempt_id,
                stage=stage,
                route=route,
                model=model,
                input_count=input_count,
                result_count=result_count,
                retry_count=retry_count,
                elapsed_ms=elapsed_ms,
                error_code=error_code,
            )
        except (TypeError, ValueError):
            yield TelemetrySpan(None)
            return

        try:
            if self._tracer is None or operation_value is None:
                yield TelemetrySpan(None)
                return
            manager = self._tracer.start_as_current_span(
                operation_value,
                attributes=attrs,
                record_exception=False,
                set_status_on_exception=False,
            )
            try:
                otel_span = manager.__enter__()
            except BaseException:
                self._tracer = None
                yield TelemetrySpan(None)
                return

            handle = TelemetrySpan(otel_span)
            error: BaseException | None = None
            try:
                yield handle
            except (asyncio.CancelledError, GeneratorExit) as exc:
                error = exc
                handle._finish("cancelled", ErrorCode.CANCELLED.value)
                raise
            except BaseException as exc:
                error = exc
                try:
                    safe_error_code = _enum_value(ErrorCode, error_code, "error code")
                except (TypeError, ValueError):
                    safe_error_code = None
                handle._finish("error", safe_error_code)
                raise
            else:
                handle._finish("success")
            finally:
                try:
                    manager.__exit__(
                        type(error) if error is not None else None,
                        error,
                        error.__traceback__ if error is not None else None,
                    )
                except BaseException:
                    self._tracer = None
        finally:
            for var, token in reversed(context_tokens):
                try:
                    var.reset(token)
                except BaseException:
                    pass

    def start_span(
        self,
        operation: Operation | str,
        *,
        request_id: str | None = None,
        run_id: str | None = None,
        case_id: str | None = None,
        attempt_id: str | None = None,
        stage: Stage | str | None = None,
        route: Route | str | None = None,
        model: str | None = None,
        input_count: int | None = None,
        result_count: int | None = None,
        retry_count: int | None = None,
        elapsed_ms: float | None = None,
        error_code: ErrorCode | str | None = None,
    ) -> TelemetrySpan:
        """Start a span that may be ended from a different async-generator task."""
        try:
            operation_value, attrs, context_tokens = self._span_attributes(
                operation,
                request_id=request_id,
                run_id=run_id,
                case_id=case_id,
                attempt_id=attempt_id,
                stage=stage,
                route=route,
                model=model,
                input_count=input_count,
                result_count=result_count,
                retry_count=retry_count,
                elapsed_ms=elapsed_ms,
                error_code=error_code,
            )
        except (TypeError, ValueError):
            return TelemetrySpan(None)

        try:
            if self._tracer is None or operation_value is None:
                return TelemetrySpan(None)
            try:
                return TelemetrySpan(self._tracer.start_span(operation_value, attributes=attrs))
            except BaseException:
                self._tracer = None
                return TelemetrySpan(None)
        finally:
            for var, token in reversed(context_tokens):
                try:
                    var.reset(token)
                except BaseException:
                    pass

    @contextmanager
    def request_id_context(self, request_id: str) -> Iterator[None]:
        """Correlate only a generated opaque request id with current work."""
        try:
            safe_request_id = _validate_identifier(request_id)
        except (TypeError, ValueError):
            safe_request_id = None
        if safe_request_id is None:
            yield
            return
        token = _REQUEST_ID.set(safe_request_id)
        try:
            try:
                active_span = trace.get_current_span()
                if active_span.is_recording():
                    active_span.set_attribute("telemetry.request_id", safe_request_id)
            except BaseException:
                pass
            yield
        finally:
            try:
                _REQUEST_ID.reset(token)
            except BaseException:
                pass

    @contextmanager
    def run_id_context(self, run_id: str) -> Iterator[None]:
        """Bind an actual opaque execution id after the run store is created."""
        try:
            safe_run_id = _validate_identifier(run_id)
        except (TypeError, ValueError):
            safe_run_id = None
        if safe_run_id is None:
            yield
            return
        token = _RUN_ID.set(safe_run_id)
        try:
            try:
                if self._tracer is not None:
                    active_span = trace.get_current_span()
                    if active_span.is_recording():
                        active_span.set_attribute("telemetry.run_id", safe_run_id)
            except BaseException:
                pass
            yield
        finally:
            try:
                _RUN_ID.reset(token)
            except BaseException:
                pass

    def record_case_content(
        self,
        *,
        case_id: str,
        case_input: str,
        case_output: str,
        classification: ContentClassification | str,
        consent: bool,
        reviewed: bool,
    ) -> bool:
        """Record only explicitly approved, reviewed public/synthetic case fields."""
        if (
            self._config.mode != "approved_public_synthetic_content"
            or not self._config.content_approved
        ):
            return False
        safe_case_id = _validate_identifier(case_id)
        classification_value = _enum_value(
            ContentClassification, classification, "content classification"
        )
        if (
            safe_case_id is None
            or classification_value is None
            or consent is not True
            or reviewed is not True
            or not isinstance(case_input, str)
            or not isinstance(case_output, str)
            or len(case_input) > _MAX_CONTENT_CHARS
            or len(case_output) > _MAX_CONTENT_CHARS
            or _has_forbidden_canary(case_input)
            or _has_forbidden_canary(case_output)
        ):
            raise ValueError("case content is not approved for telemetry")

        attrs: dict[str, str | bool] = {
            "telemetry.operation": Operation.CASE_CONTENT.value,
            "telemetry.case_id": safe_case_id,
            "content.classification": classification_value,
            "content.consent": True,
            "content.reviewed": True,
            "content.input": case_input,
            "content.output": case_output,
        }
        for name, var in _CONTEXT_IDS:
            if name != "case_id" and (identifier := var.get()) is not None:
                attrs[f"telemetry.{name}"] = identifier
        if self._tracer is None:
            return False
        try:
            with self._tracer.start_as_current_span(
                Operation.CASE_CONTENT.value,
                attributes=attrs,
                record_exception=False,
                set_status_on_exception=False,
            ) as span:
                span.set_attribute("telemetry.outcome", "success")
        except Exception:
            return False
        return True

    async def force_flush(self) -> bool:
        """Flush without blocking the event loop; exporter timeouts are cooperative."""
        return await self._run_lifecycle_async("flush")

    async def aclose(self) -> bool:
        """Close within the configured wait budget, without claiming worker termination."""
        return await self._run_lifecycle_async("shutdown")

    def close(self) -> bool:
        """Bound synchronous-owner cleanup without terminating an exporter worker."""
        immediate = self._begin_lifecycle("shutdown")
        if immediate is not None:
            return immediate
        if not self._lifecycle_done.wait(self._config.shutdown_timeout_seconds):
            return False
        with self._lifecycle_lock:
            return self._lifecycle_result

    def _begin_lifecycle(self, action: str) -> bool | None:
        if self._provider is None:
            return True
        with self._lifecycle_lock:
            if self._closed:
                return action == "shutdown"
            if self._lifecycle_busy:
                if action == "shutdown":
                    self._shutdown_requested = True
            else:
                self._lifecycle_busy = True
                self._lifecycle_done.clear()
                self._shutdown_requested = action == "shutdown"
                worker = threading.Thread(
                    target=self._lifecycle_worker,
                    args=(action,),
                    name="telemetry-lifecycle",
                    daemon=True,
                )
                self._lifecycle_thread = worker
                try:
                    worker.start()
                except BaseException:
                    self._lifecycle_busy = False
                    self._lifecycle_result = False
                    self._lifecycle_done.set()
                    return False
        return None

    async def _run_lifecycle_async(self, action: str) -> bool:
        immediate = self._begin_lifecycle(action)
        if immediate is not None:
            return immediate
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._config.shutdown_timeout_seconds
        while not self._lifecycle_done.is_set():
            remaining = deadline - loop.time()
            if remaining <= 0:
                return False
            await asyncio.sleep(min(0.01, remaining))
        with self._lifecycle_lock:
            return self._lifecycle_result

    def _lifecycle_worker(self, action: str) -> None:
        provider = self._provider
        result = provider is not None
        try:
            if action == "flush" and provider is not None:
                result = provider.force_flush(
                    timeout_millis=max(1, int(self._config.shutdown_timeout_seconds * 1000))
                )
        except BaseException:
            result = False

        with self._lifecycle_lock:
            should_shutdown = action == "shutdown" or self._shutdown_requested
            if not should_shutdown:
                self._lifecycle_result = result
                self._lifecycle_busy = False
                self._lifecycle_done.set()
                return

        try:
            if provider is not None:
                provider.shutdown()
        except BaseException:
            result = False
        if self._export_log_filter_installed:
            _remove_export_log_filter()
            self._export_log_filter_installed = False
        with self._lifecycle_lock:
            self._closed = True
            self._lifecycle_result = result
            self._lifecycle_busy = False
            self._lifecycle_done.set()


_CURRENT_TELEMETRY: ContextVar[Telemetry | None] = ContextVar("current_telemetry", default=None)


def current_telemetry() -> Telemetry | None:
    """Return the app-local telemetry owner active in this execution context."""
    return _CURRENT_TELEMETRY.get()


@contextmanager
def use_telemetry(telemetry: Telemetry | None) -> Iterator[None]:
    """Activate one app's telemetry for an ASGI request and its child tasks."""
    token = _CURRENT_TELEMETRY.set(telemetry)
    try:
        yield
    finally:
        _CURRENT_TELEMETRY.reset(token)


@contextmanager
def telemetry_operation(operation: Operation | str, **metadata: Any) -> Iterator[TelemetrySpan]:
    """Record an operation if an app-local owner is active; otherwise stay no-op."""
    telemetry = current_telemetry()
    if telemetry is None:
        yield TelemetrySpan(None)
        return
    with telemetry.span(operation, **metadata) as span:
        yield span


def start_telemetry_operation(operation: Operation | str, **metadata: Any) -> TelemetrySpan:
    """Start a context-independent operation span for async-generator work."""
    telemetry = current_telemetry()
    if telemetry is None:
        return TelemetrySpan(None)
    return telemetry.start_span(operation, **metadata)
