"""Exporter isolation and bounded lifecycle tests with synthetic-only exporters."""

import asyncio
import socket
import threading
import time

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from src.config.settings import TelemetryConfig
from src.infra.telemetry import Operation, Telemetry

_SYNTHETIC_TOKEN = "SYNTHETIC_WRITE_TOKEN_CANARY"
_SYNTHETIC_EXCEPTION = "SYNTHETIC_EXPORT_EXCEPTION_CANARY"


def _hosted_config(timeout: float = 0.1) -> TelemetryConfig:
    return TelemetryConfig(
        mode="hosted_metadata",
        export_enabled=True,
        endpoint="https://logfire-us.pydantic.dev",
        region="us",
        access_policy="private_project",
        access_approved=True,
        retention_days=30,
        retention_approved=True,
        token=_SYNTHETIC_TOKEN,
        shutdown_timeout_seconds=timeout,
    )


def _deny_network(monkeypatch):
    attempts = []

    def denied(*args, **kwargs):
        attempts.append("network")
        raise AssertionError("hosted exporter test attempted network access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket, "gethostbyname", denied)
    monkeypatch.setattr(socket, "gethostbyaddr", denied)
    return attempts


class _RecordingExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []
        self.shutdown_called = threading.Event()

    def export(self, spans) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self.shutdown_called.set()


class _FailingExporter(SpanExporter):
    def __init__(self) -> None:
        self.called = threading.Event()

    def export(self, spans) -> SpanExportResult:
        self.called.set()
        raise RuntimeError(_SYNTHETIC_EXCEPTION)


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


def test_explicit_hosted_mode_uses_only_injected_exporter(monkeypatch, caplog):
    attempts = _deny_network(monkeypatch)
    monkeypatch.setenv("LOGFIRE_TOKEN", _SYNTHETIC_EXCEPTION)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", f"authorization={_SYNTHETIC_EXCEPTION}")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    exporter = _RecordingExporter()
    telemetry = Telemetry(_hosted_config(), exporter=exporter)

    with telemetry.span(Operation.REQUEST, request_id="request-005"):
        pass

    assert asyncio.run(telemetry.force_flush())
    assert len(exporter.spans) == 1
    assert exporter.spans[0].name == "request"
    assert attempts == []
    assert _SYNTHETIC_EXCEPTION not in caplog.text
    assert asyncio.run(telemetry.aclose())
    assert exporter.shutdown_called.is_set()


def test_exporter_exception_does_not_escape_or_log_exception_text(caplog):
    exporter = _FailingExporter()
    telemetry = Telemetry(_hosted_config(), exporter=exporter)

    with telemetry.span(Operation.GENERATION):
        pass

    assert asyncio.run(telemetry.force_flush())
    assert exporter.called.wait(1)
    assert _SYNTHETIC_EXCEPTION not in caplog.text
    assert asyncio.run(telemetry.aclose())


@pytest.mark.asyncio
async def test_unresponsive_exporter_lifecycle_is_bounded_and_cleanup_is_observed():
    exporter = _BlockingExporter()
    telemetry = Telemetry(_hosted_config(timeout=0.1), exporter=exporter)
    with telemetry.span(Operation.REQUEST):
        pass

    try:
        await asyncio.wait_for(asyncio.to_thread(exporter.export_started.wait, 1), timeout=1.5)

        started = time.monotonic()
        flushed = await telemetry.force_flush()
        flush_elapsed = time.monotonic() - started
        assert flushed is False
        assert flush_elapsed < 1

        started = time.monotonic()
        closed = await telemetry.aclose()
        close_elapsed = time.monotonic() - started
        assert closed is False
        assert close_elapsed < 1

        exporter.release_export.set()
        worker = telemetry._lifecycle_thread
        assert worker is not None
        await asyncio.wait_for(asyncio.to_thread(worker.join, 1), timeout=1.5)
        assert not worker.is_alive()
        assert exporter.shutdown_called.is_set()
    finally:
        exporter.release_export.set()
        worker = telemetry._lifecycle_thread
        if worker is not None:
            await asyncio.wait_for(asyncio.to_thread(worker.join, 1), timeout=1.5)
