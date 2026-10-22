"""Explicit-export (Logfire destination) construction tests; never real network."""

import ast
import asyncio
import logging
import socket
import threading
import time
from pathlib import Path

import pytest
import requests
from opentelemetry.exporter.otlp.proto.http import Compression
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from pydantic import SecretStr

import src.infra.telemetry as telemetry_module
from src.config.settings import TelemetryConfig
from src.infra.telemetry import Operation, Telemetry

_SYNTHETIC_TOKEN = "SYNTHETIC_WRITE_TOKEN_CANARY"
_ENV_HEADER_CANARY = "SYNTHETIC_ENV_HEADER_CANARY"
_SYNTHETIC_EXCEPTION = "SYNTHETIC_EXPORT_EXCEPTION_CANARY"
_CANARY_EXPORT_REASON = "SYNTHETIC_EXPORT_REASON_CANARY"
_CANARY_TRANSPORT_EXCEPTION = "SYNTHETIC_EXPORT_TRANSPORT_EXCEPTION_CANARY"
_EXPECTED_ENDPOINT = "https://logfire-us.pydantic.dev/v1/traces"
# Explicit scheduler slack on top of the configured shutdown deadline; the
# lifecycle machinery must finish inside the budget, not a multiple of it.
_SCHEDULER_SLACK_SECONDS = 0.15


def _hosted_config(timeout: float = 0.25) -> TelemetryConfig:
    return TelemetryConfig(
        mode="hosted_metadata",
        export_enabled=True,
        endpoint="https://logfire-us.pydantic.dev",
        region="us",
        access_policy="private_project",
        access_approved=True,
        retention_days=30,
        retention_approved=True,
        token=SecretStr(_SYNTHETIC_TOKEN),
        shutdown_timeout_seconds=timeout,
    )


def _deny_network(monkeypatch):
    attempts = []

    def denied(*args, **kwargs):
        attempts.append("network")
        raise AssertionError("explicit-export test attempted network access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket, "gethostbyname", denied)
    monkeypatch.setattr(socket, "gethostbyaddr", denied)
    return attempts


def _capture_exporter_construction(monkeypatch) -> list[dict]:
    captured: list[dict] = []

    class _CapturingExporter(SpanExporter):
        def __init__(self, **kwargs):
            captured.append(kwargs)

        def export(self, spans) -> SpanExportResult:
            return SpanExportResult.SUCCESS

        def shutdown(self) -> None:
            return None

        def force_flush(self, timeout_millis: int = 30_000) -> bool:
            return True

    monkeypatch.setattr(telemetry_module, "OTLPSpanExporter", _CapturingExporter)
    return captured


def _sanitize_residual_otlp_environment(monkeypatch) -> None:
    for name in telemetry_module._RESIDUAL_OTLP_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


class _RecordingExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []
        self.shutdown_called = threading.Event()

    def export(self, spans) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self.shutdown_called.set()


class _BlockingExporter(_RecordingExporter):
    def __init__(self) -> None:
        super().__init__()
        self.export_started = threading.Event()
        self.release_export = threading.Event()

    def export(self, spans) -> SpanExportResult:
        self.export_started.set()
        self.release_export.wait()
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS


class _CanaryReasonSession:
    """Fake requests session returning a collector-controlled failure reason."""

    verify: bool | str = True

    def request(self, method, url, **kwargs):
        return _CanaryFailureResponse()


class _CanaryFailureResponse:
    """Minimal fake response: a non-retryable 500 whose reason carries a canary."""

    status_code = 500
    reason = _CANARY_EXPORT_REASON


class _RaisingSession:
    """Fake requests session whose transport exception text carries a canary."""

    verify: bool | str = True

    def request(self, method, url, **kwargs):
        raise RuntimeError(_CANARY_TRANSPORT_EXCEPTION)


def _real_pinned_exporter(session) -> OTLPSpanExporter:
    return OTLPSpanExporter(
        endpoint=_EXPECTED_ENDPOINT,
        headers={"Authorization": _SYNTHETIC_TOKEN},
        timeout=0.25,
        compression=Compression.NoCompression,
        session=session,
        meter_provider=NoOpMeterProvider(),
    )


def test_hosted_mode_constructs_official_exporter_from_config(monkeypatch):
    _deny_network(monkeypatch)
    _sanitize_residual_otlp_environment(monkeypatch)
    captured = _capture_exporter_construction(monkeypatch)

    telemetry = Telemetry(_hosted_config(timeout=0.25))

    assert len(captured) == 1
    kwargs = captured[0]
    assert set(kwargs) == {
        "endpoint",
        "headers",
        "timeout",
        "compression",
        "session",
        "meter_provider",
    }
    assert kwargs["endpoint"] == _EXPECTED_ENDPOINT
    assert kwargs["headers"] == {"Authorization": _SYNTHETIC_TOKEN}
    assert kwargs["timeout"] == 0.25
    assert kwargs["compression"] is Compression.NoCompression
    assert isinstance(kwargs["session"], requests.Session)
    assert kwargs["session"].trust_env is False
    assert asyncio.run(telemetry.aclose())


def test_otlp_environment_variables_do_not_alter_constructed_destination(monkeypatch):
    _deny_network(monkeypatch)
    # Header environment variables are not listed here: extra OTEL_EXPORTER_OTLP
    # HEADERS keys are merged by the pinned exporter regardless of explicit
    # arguments, so hosted construction fails closed on them instead (see the
    # residual-environment tests below; header neutralization itself is covered
    # by the direct-exporter hostile-env test).
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://127.0.0.1:9999/v1/traces")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "99")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_TIMEOUT", "99")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_COMPRESSION", "gzip")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_COMPRESSION", "gzip")
    _sanitize_residual_otlp_environment(monkeypatch)
    captured = _capture_exporter_construction(monkeypatch)

    telemetry = Telemetry(_hosted_config(timeout=0.25))

    assert len(captured) == 1
    kwargs = captured[0]
    assert kwargs["endpoint"] == _EXPECTED_ENDPOINT
    assert kwargs["headers"] == {"Authorization": _SYNTHETIC_TOKEN}
    assert kwargs["timeout"] == 0.25
    assert kwargs["compression"] is Compression.NoCompression
    assert kwargs["session"].trust_env is False
    assert asyncio.run(telemetry.aclose())


@pytest.mark.parametrize(
    "residual_var",
    [
        "OTEL_EXPORTER_OTLP_HEADERS",
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
        "OTEL_EXPORTER_OTLP_CERTIFICATE",
        "OTEL_EXPORTER_OTLP_TRACES_CERTIFICATE",
        "OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE",
        "OTEL_EXPORTER_OTLP_TRACES_CLIENT_CERTIFICATE",
        "OTEL_EXPORTER_OTLP_CLIENT_KEY",
        "OTEL_EXPORTER_OTLP_TRACES_CLIENT_KEY",
    ],
)
def test_hosted_construction_fails_closed_on_residual_otlp_environment(monkeypatch, residual_var):
    _deny_network(monkeypatch)
    # Isolate first so each parameter fails on its own variable, never on a
    # residual variable inherited from the ambient process environment.
    _sanitize_residual_otlp_environment(monkeypatch)
    captured = _capture_exporter_construction(monkeypatch)
    monkeypatch.setenv(residual_var, "SYNTHETIC_RESIDUAL_ENV_CANARY")

    telemetry = Telemetry(_hosted_config())

    assert telemetry.available is False
    assert captured == []


def test_hosted_construction_succeeds_with_sanitized_otlp_environment(monkeypatch):
    _deny_network(monkeypatch)
    _sanitize_residual_otlp_environment(monkeypatch)
    captured = _capture_exporter_construction(monkeypatch)

    telemetry = Telemetry(_hosted_config())

    assert telemetry.available is True
    assert len(captured) == 1
    assert asyncio.run(telemetry.aclose())


def test_pinned_official_exporter_keeps_config_destination_under_hostile_env(monkeypatch):
    _deny_network(monkeypatch)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://127.0.0.1:9999/v1/traces")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", f"authorization={_ENV_HEADER_CANARY}")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "99")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_COMPRESSION", "gzip")

    session = requests.Session()
    session.trust_env = False
    # Private attributes are read deliberately: the exact exporter build is
    # pinned (OTel 1.45.1), and these assertions lock its env-neutralization
    # behavior so any future pin bump must re-verify it.
    exporter = OTLPSpanExporter(
        endpoint=_EXPECTED_ENDPOINT,
        headers={"Authorization": _SYNTHETIC_TOKEN},
        timeout=0.25,
        compression=Compression.NoCompression,
        session=session,
    )

    assert exporter._endpoint == _EXPECTED_ENDPOINT
    assert exporter._client._timeout == 0.25
    assert exporter._client._headers["authorization"] == _SYNTHETIC_TOKEN
    assert _ENV_HEADER_CANARY not in exporter._client._headers.values()
    assert "content-encoding" not in exporter._client._headers


def test_hosted_spans_carry_no_exception_events_or_content(monkeypatch):
    _deny_network(monkeypatch)
    exporter = _RecordingExporter()
    telemetry = Telemetry(_hosted_config(), exporter=exporter)

    with pytest.raises(RuntimeError):
        with telemetry.span(Operation.GENERATION):
            raise RuntimeError(_SYNTHETIC_EXCEPTION)

    assert asyncio.run(telemetry.force_flush())
    assert len(exporter.spans) == 1
    span = exporter.spans[0]
    assert not span.events
    assert _SYNTHETIC_EXCEPTION not in repr(span.attributes)
    assert span.attributes["telemetry.outcome"] == "error"
    assert asyncio.run(telemetry.aclose())
    assert exporter.shutdown_called.is_set()


def _exporter_failure_records(caplog) -> list:
    return [
        record
        for record in caplog.records
        if record.name == telemetry_module._EXPORTER_LOG_NAMESPACE
    ]


def test_real_exporter_failure_reason_is_sanitized_from_logs(monkeypatch, caplog):
    _deny_network(monkeypatch)
    _sanitize_residual_otlp_environment(monkeypatch)
    # Hosted export owns the sanitizing filter for as long as it is active.
    telemetry = Telemetry(_hosted_config())
    assert telemetry.available is True
    exporter = _real_pinned_exporter(_CanaryReasonSession())

    with caplog.at_level(logging.DEBUG):
        assert exporter.export([]) is SpanExportResult.FAILURE

    records = _exporter_failure_records(caplog)
    assert len(records) == 1
    assert records[0].getMessage() == "OTLP export attempt failed"
    assert records[0].levelname == "ERROR"
    assert _CANARY_EXPORT_REASON not in caplog.text
    assert _SYNTHETIC_TOKEN not in caplog.text
    assert asyncio.run(telemetry.aclose())


def test_real_exporter_transport_exception_text_is_sanitized_from_logs(monkeypatch, caplog):
    _deny_network(monkeypatch)
    _sanitize_residual_otlp_environment(monkeypatch)
    telemetry = Telemetry(_hosted_config())
    assert telemetry.available is True
    exporter = _real_pinned_exporter(_RaisingSession())

    with caplog.at_level(logging.DEBUG):
        assert exporter.export([]) is SpanExportResult.FAILURE

    records = _exporter_failure_records(caplog)
    assert len(records) == 1
    assert records[0].getMessage() == "OTLP export attempt failed"
    assert records[0].levelname == "ERROR"
    assert _CANARY_TRANSPORT_EXCEPTION not in caplog.text
    assert asyncio.run(telemetry.aclose())


def test_export_log_filter_follows_hosted_exporter_lifecycle(monkeypatch):
    _deny_network(monkeypatch)
    _sanitize_residual_otlp_environment(monkeypatch)
    export_logger = logging.getLogger(telemetry_module._EXPORTER_LOG_NAMESPACE)

    def installed_filters() -> list:
        return [
            installed
            for installed in export_logger.filters
            if isinstance(installed, telemetry_module._ExportLogSanitizingFilter)
        ]

    telemetry = Telemetry(_hosted_config())
    assert len(installed_filters()) == 1

    assert asyncio.run(telemetry.aclose())

    assert installed_filters() == []


def test_hosted_construction_fails_closed_when_filter_installation_fails(monkeypatch):
    _deny_network(monkeypatch)
    _sanitize_residual_otlp_environment(monkeypatch)
    export_logger = logging.getLogger(telemetry_module._EXPORTER_LOG_NAMESPACE)
    captured = _capture_exporter_construction(monkeypatch)

    def installed_filters() -> list:
        return [
            installed
            for installed in export_logger.filters
            if isinstance(installed, telemetry_module._ExportLogSanitizingFilter)
        ]

    # Clean control: with a working addFilter, hosted construction succeeds
    # and the sanitizing filter is installed; closing removes it again.
    control = Telemetry(_hosted_config())
    assert control.available is True
    assert len(installed_filters()) == 1
    assert asyncio.run(control.aclose())
    assert installed_filters() == []

    def failing_add_filter(filter_: logging.Filter) -> None:
        raise RuntimeError(_SYNTHETIC_EXCEPTION)

    monkeypatch.setattr(export_logger, "addFilter", failing_add_filter)
    telemetry = Telemetry(_hosted_config())

    # Fail closed: no hosted telemetry, no exporter constructed, and the
    # global filter state stays consistent (nothing installed, depth zero).
    assert telemetry.available is False
    assert len(captured) == 1
    assert telemetry._export_log_filter_installed is False
    assert installed_filters() == []
    assert telemetry_module._EXPORT_LOG_FILTER is None
    assert telemetry_module._EXPORT_LOG_FILTER_DEPTH == 0


def _is_constant_logfire_module_argument(call: ast.Call) -> bool:
    """Match dynamic loader calls whose constant argument names Logfire."""
    arguments = [*call.args]
    arguments.extend(
        keyword.value
        for keyword in call.keywords
        if keyword.arg in {None, "name"} and keyword.value is not None
    )
    return any(
        isinstance(arg, ast.Constant)
        and isinstance(arg.value, str)
        and arg.value.startswith("logfire")
        for arg in arguments
    )


def test_constant_logfire_argument_matches_keyword_form():
    call = ast.parse("importlib.import_module(name='logfire')", mode="eval").body
    assert isinstance(call, ast.Call)
    assert _is_constant_logfire_module_argument(call)
    safe = ast.parse("importlib.import_module(name='otel_utils')", mode="eval").body
    assert isinstance(safe, ast.Call)
    assert not _is_constant_logfire_module_argument(safe)


def test_telemetry_module_has_no_logfire_import_or_configure_path():
    source_path = Path(__file__).resolve().parents[3] / "src" / "infra" / "telemetry.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] != "logfire", ast.dump(node)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "logfire", ast.dump(node)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "configure":
                root = func.value
                while isinstance(root, ast.Attribute):
                    root = root.value
                assert not (isinstance(root, ast.Name) and root.id == "logfire"), ast.dump(node)
            elif isinstance(func, ast.Name) and func.id == "__import__":
                assert not _is_constant_logfire_module_argument(node), ast.dump(node)
            elif isinstance(func, ast.Attribute) and func.attr == "import_module":
                assert not _is_constant_logfire_module_argument(node), ast.dump(node)
        elif isinstance(node, ast.ClassDef):
            assert node.name != "_ExplicitOTLPExporter", node.name
    assert "OTLPSpanExporter" in source_path.read_text(encoding="utf-8")


def test_hosted_flush_and_shutdown_succeed_within_configured_budget(monkeypatch):
    _deny_network(monkeypatch)
    timeout = 0.25
    deadline = timeout + _SCHEDULER_SLACK_SECONDS
    exporter = _RecordingExporter()
    telemetry = Telemetry(_hosted_config(timeout=timeout), exporter=exporter)
    with telemetry.span(Operation.REQUEST):
        pass

    started = time.monotonic()
    assert asyncio.run(telemetry.force_flush())
    assert time.monotonic() - started <= deadline
    started = time.monotonic()
    assert asyncio.run(telemetry.aclose())
    assert time.monotonic() - started <= deadline
    assert exporter.shutdown_called.is_set()


def test_unresponsive_hosted_exporter_flush_and_shutdown_stay_bounded(monkeypatch):
    _deny_network(monkeypatch)
    timeout = 0.1
    deadline = timeout + _SCHEDULER_SLACK_SECONDS
    exporter = _BlockingExporter()
    telemetry = Telemetry(_hosted_config(timeout=timeout), exporter=exporter)
    with telemetry.span(Operation.REQUEST):
        pass

    try:
        assert exporter.export_started.wait(1)
        started = time.monotonic()
        assert asyncio.run(telemetry.force_flush()) is False
        assert time.monotonic() - started <= deadline
        started = time.monotonic()
        assert asyncio.run(telemetry.aclose()) is False
        assert time.monotonic() - started <= deadline
    finally:
        exporter.release_export.set()
        worker = telemetry._lifecycle_thread
        if worker is not None:
            worker.join(1)
            assert not worker.is_alive()
    assert exporter.shutdown_called.is_set()
