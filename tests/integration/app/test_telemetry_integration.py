"""HTTP/lifespan telemetry integration with synthetic retrieval and generation leaves."""

import asyncio
import json
import threading
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from tests.integration.app import test_lifespan

lifecycle = test_lifespan.lifecycle


def _events(response):
    return [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]


def _span_attributes(owner):
    return [(span.name, dict(span.attributes or {}), span) for span in owner.finished_spans]


def _hosted_config(timeout=0.1):
    from src.config.settings import TelemetryConfig

    return TelemetryConfig(
        mode="hosted_metadata",
        export_enabled=True,
        endpoint="https://logfire-us.pydantic.dev",
        region="us",
        access_policy="private_project",
        access_approved=True,
        retention_days=30,
        retention_approved=True,
        token="SYNTHETIC_TELEMETRY_TOKEN",
        shutdown_timeout_seconds=timeout,
    )


def test_local_telemetry_wraps_real_http_sse_and_closes_owned_instance(lifecycle, monkeypatch):
    from src.config.settings import TelemetryConfig

    control = lifecycle
    monkeypatch.setattr(control.factory.settings, "telemetry", TelemetryConfig(mode="local"))
    app = control.factory.create_app()

    with TestClient(app) as http:
        owner = app.state.telemetry
        response = http.post(
            "/chat?include_pipeline=true",
            json={"message": "SYNTHETIC_REQUEST_CONTENT"},
            headers={"X-Request-ID": "SYNTHETIC_INCOMING_REQUEST_ID"},
        )
        assert response.status_code == 200
        events = _events(response)
        assert [event["content"] for event in events if not event["done"]] == [
            "synthetic ",
            "answer",
        ]
        assert events[-1]["request_id"] == response.headers["x-request-id"]
        assert uuid.UUID(response.headers["x-request-id"]).version == 4
        assert response.headers["x-request-id"] != "SYNTHETIC_INCOMING_REQUEST_ID"

        spans = _span_attributes(owner)
        names = [name for name, _, _ in spans]
        assert {"request", "retrieval", "expansion", "search", "reranking", "generation"}.issubset(
            names
        )
        request_span = next(attrs for name, attrs, _ in spans if name == "request")
        assert request_span["telemetry.request_id"] == response.headers["x-request-id"]
        assert request_span["telemetry.route"] == "chat"
        serialized = json.dumps([attrs for _, attrs, _ in spans], sort_keys=True, default=str)
        assert "SYNTHETIC_REQUEST_CONTENT" not in serialized
        assert "synthetic answer" not in serialized
        assert "SYNTHETIC_INCOMING_REQUEST_ID" not in serialized
        assert control.searches

    assert app.state.telemetry is None
    assert owner.finished_spans


def test_http_generation_error_is_metadata_only_and_does_not_capture_exception(
    lifecycle, monkeypatch, caplog
):
    from src.config.settings import TelemetryConfig

    control = lifecycle
    monkeypatch.setattr(control.factory.settings, "telemetry", TelemetryConfig(mode="local"))
    app = control.factory.create_app()

    async def failed_generation(**kwargs):
        if False:
            yield ""
        raise RuntimeError("SYNTHETIC_GENERATION_EXCEPTION_CANARY")

    with TestClient(app) as http:
        owner = app.state.telemetry
        monkeypatch.setattr(app.state.llm_client, "a_generate_stream", failed_generation)
        response = http.post("/chat", json={"message": "synthetic question"})
        assert response.status_code == 200
        events = _events(response)
        assert events[-1]["error_code"] == "chat_stream_failed"
        assert "SYNTHETIC_GENERATION_EXCEPTION_CANARY" not in response.text
        generation = next(span for span in owner.finished_spans if span.name == "generation")
        assert generation.attributes["telemetry.outcome"] == "error"
        assert generation.events == ()

    assert "SYNTHETIC_GENERATION_EXCEPTION_CANARY" not in caplog.text


def test_export_failure_does_not_break_http_chat_or_leak_export_exception(
    lifecycle, monkeypatch, caplog
):
    from src.infra.telemetry import Telemetry

    control = lifecycle

    class FailingExporter(SpanExporter):
        def export(self, spans):
            raise RuntimeError("SYNTHETIC_EXPORT_EXCEPTION_CANARY")

        def shutdown(self):
            return None

    exporter = FailingExporter()

    class ExportTelemetry(Telemetry):
        def __init__(self, config):
            super().__init__(config, exporter=exporter)

    monkeypatch.setattr(control.factory.settings, "telemetry", _hosted_config())
    monkeypatch.setattr(control.factory, "Telemetry", ExportTelemetry)
    app = control.factory.create_app()

    with TestClient(app) as http:
        response = http.post("/chat", json={"message": "synthetic question"})
        assert response.status_code == 200
        assert _events(response)[-1]["error"] is None

    assert "SYNTHETIC_EXPORT_EXCEPTION_CANARY" not in caplog.text
    assert app.state.telemetry is None


@pytest.mark.asyncio
async def test_real_asgi_disconnect_records_cancelled_generation_without_terminal_event(
    lifecycle, monkeypatch
):
    from src.config.settings import TelemetryConfig

    control = lifecycle
    monkeypatch.setattr(control.factory.settings, "telemetry", TelemetryConfig(mode="local"))
    app = control.factory.create_app()
    disconnected = asyncio.Event()
    generation_closed = asyncio.Event()
    sent = []
    first_receive = True

    async def generation(**kwargs):
        try:
            yield "synthetic-prefix"
            await asyncio.Event().wait()
        finally:
            generation_closed.set()

    async with app.router.lifespan_context(app):
        owner = app.state.telemetry
        monkeypatch.setattr(app.state.llm_client, "a_generate_stream", generation)

        async def receive():
            nonlocal first_receive
            if first_receive:
                first_receive = False
                return {
                    "type": "http.request",
                    "body": b'{"message":"synthetic question"}',
                    "more_body": False,
                }
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)
            if message.get("type") == "http.response.body" and b"synthetic-prefix" in message.get(
                "body", b""
            ):
                disconnected.set()

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/chat",
            "raw_path": b"/chat",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        await asyncio.wait_for(app(scope, receive, send), timeout=3)
        assert generation_closed.is_set()
        body = b"".join(
            message.get("body", b"")
            for message in sent
            if message.get("type") == "http.response.body"
        )
        assert b"synthetic-prefix" in body
        assert b'"done":true' not in body
        spans = _span_attributes(owner)
        generation_span = next(span for name, _, span in spans if name == "generation")
        assert generation_span.attributes["telemetry.outcome"] == "cancelled"
        assert any(name == "cancellation" for name, _, _ in spans)
        request_id = next(
            value
            for message in sent
            if message.get("type") == "http.response.start"
            for key, value in message["headers"]
            if key.lower() == b"x-request-id"
        ).decode()
        assert uuid.UUID(request_id).version == 4
        assert all(attrs.get("telemetry.request_id") == request_id for _, attrs, _ in spans)

    assert app.state.telemetry is None


@pytest.mark.asyncio
async def test_lifespan_closes_only_owned_telemetry_and_clears_state(lifecycle, monkeypatch):
    from src.config.settings import TelemetryConfig

    control = lifecycle
    monkeypatch.setattr(control.factory.settings, "telemetry", TelemetryConfig(mode="local"))
    app = control.factory.create_app()
    injected = SimpleNamespace(aclose=AsyncMock())

    async with app.router.lifespan_context(app):
        owner = app.state.telemetry
        app.state.telemetry = injected

    assert owner._closed
    injected.aclose.assert_not_awaited()
    assert app.state.telemetry is None


@pytest.mark.asyncio
async def test_owner_cleanup_is_bounded_with_blocked_exporter(lifecycle, monkeypatch):
    from src.infra.telemetry import Operation, Telemetry

    control = lifecycle

    class BlockingExporter(SpanExporter):
        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()
            self.shutdown_called = False

        def export(self, spans):
            self.started.set()
            self.release.wait()
            return SpanExportResult.SUCCESS

        def shutdown(self):
            self.shutdown_called = True

    exporter = BlockingExporter()
    loop = asyncio.get_running_loop()
    started_at = loop.time()

    class BlockingTelemetry(Telemetry):
        def __init__(self, config):
            super().__init__(config, exporter=exporter)

    monkeypatch.setattr(control.factory.settings, "telemetry", _hosted_config(timeout=0.05))
    monkeypatch.setattr(control.factory, "Telemetry", BlockingTelemetry)
    app = control.factory.create_app()

    async with app.router.lifespan_context(app):
        owner = app.state.telemetry
        with owner.span(Operation.REQUEST):
            pass

    assert app.state.telemetry is None
    assert loop.time() - started_at < 1
    assert await asyncio.wait_for(asyncio.to_thread(exporter.started.wait, 1), timeout=1.5)
    worker = owner._lifecycle_thread
    assert worker is not None
    exporter.release.set()
    await asyncio.wait_for(asyncio.to_thread(worker.join, 1), timeout=1.5)
    assert not worker.is_alive()
    assert exporter.shutdown_called
