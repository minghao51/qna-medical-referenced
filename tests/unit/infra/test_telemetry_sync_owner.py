"""Synchronous evaluation owners share the bounded asynchronous lifecycle worker."""

import asyncio
import threading
import time

import pytest

from src.config.settings import TelemetryConfig
from src.infra.telemetry import Operation, Telemetry


@pytest.mark.parametrize(
    "identifier", ["12345678-1234-4234-8234-123456789012", "12345678123442348234123456789012"]
)
def test_numeric_uuid4_execution_ids_bind_and_reset_without_leaking_context(identifier):
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    with telemetry.span(Operation.RUN):
        with telemetry.run_id_context(identifier):
            with telemetry.span(Operation.RETRIEVAL):
                pass
    with telemetry.span(Operation.EVALUATION):
        pass
    by_name = {s.name: s for s in telemetry.finished_spans}
    assert by_name["run"].attributes["telemetry.run_id"] == identifier
    assert by_name["retrieval"].attributes["telemetry.run_id"] == identifier
    assert "telemetry.run_id" not in by_name["evaluation"].attributes
    assert telemetry.close()


@pytest.mark.asyncio
async def test_sync_close_works_inside_running_loop_without_creating_another_loop():
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    loop = asyncio.get_running_loop()
    assert telemetry.close()
    assert asyncio.get_running_loop() is loop
    assert await telemetry.aclose()


def test_sync_close_timeout_keeps_one_worker_until_entered_shutdown_finishes(monkeypatch):
    telemetry = Telemetry(TelemetryConfig(mode="local", shutdown_timeout_seconds=0.03))
    entered, release = threading.Event(), threading.Event()
    provider = telemetry._provider
    assert provider is not None
    shutdown = provider.shutdown

    def blocked():
        entered.set()
        release.wait()
        shutdown()

    monkeypatch.setattr(provider, "shutdown", blocked)
    try:
        start = time.monotonic()
        assert telemetry.close() is False
        assert time.monotonic() - start < 0.5
        assert entered.is_set()
        worker = telemetry._lifecycle_thread
        assert worker is not None
        assert worker.is_alive()
        assert telemetry.close() is False
        assert telemetry._lifecycle_thread is worker
        assert not telemetry._closed
    finally:
        release.set()
        worker = telemetry._lifecycle_thread
        if worker is not None:
            worker.join(2)
            assert not worker.is_alive()
    assert telemetry.close()


def test_thread_start_failure_is_non_throwing_and_can_retry(monkeypatch):
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    with monkeypatch.context() as patch:
        patch.setattr(
            threading.Thread,
            "start",
            lambda self: (_ for _ in ()).throw(RuntimeError("SYNTHETIC_SECRET_CANARY")),
        )
        assert telemetry.close() is False
        assert not telemetry._lifecycle_busy
    assert telemetry.close()
