"""Privacy-policy and span-content tests; no application or provider clients are imported."""

import asyncio
import json
import socket

import pytest
from pydantic import ValidationError

from src.config.settings import Settings, TelemetryConfig
from src.infra.telemetry import (
    ContentClassification,
    ErrorCode,
    Operation,
    Route,
    Stage,
    Telemetry,
    UsageCompleteness,
)

_SECRET_CANARY = "SYNTHETIC_SECRET_CANARY"
_COOKIE_CANARY = "SYNTHETIC_COOKIE_CANARY"
_AUTH_CANARY = "SYNTHETIC_AUTH_CANARY"


def _serialize(telemetry: Telemetry) -> str:
    return json.dumps(
        [
            {
                "name": span.name,
                "attributes": dict(span.attributes or {}),
                "events": [
                    {"name": event.name, "attributes": dict(event.attributes or {})}
                    for event in span.events
                ],
                "status": span.status.status_code.name,
                "resource": dict(span.resource.attributes),
            }
            for span in telemetry.finished_spans
        ],
        sort_keys=True,
        default=str,
    )


def _deny_network(monkeypatch):
    attempts = []

    def denied(*args, **kwargs):
        attempts.append("network")
        raise AssertionError("telemetry attempted network access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket, "gethostbyname", denied)
    monkeypatch.setattr(socket, "gethostbyaddr", denied)
    return attempts


def test_settings_default_to_disabled_and_secret_is_masked(monkeypatch):
    monkeypatch.setenv("APP__TELEMETRY__TOKEN", _SECRET_CANARY)
    settings = Settings(_env_file=None, telemetry={"mode": "local"})
    config = TelemetryConfig(token=_SECRET_CANARY)

    assert settings.telemetry.mode == "local"
    assert TelemetryConfig().mode == "disabled"
    assert TelemetryConfig().export_enabled is False
    assert TelemetryConfig().content_approved is False
    assert "SYNTHETIC_SECRET_CANARY" not in repr(config)
    assert config.shutdown_timeout_seconds > 0
    assert config.shutdown_timeout_seconds <= 2


def test_hosted_export_requires_destination_access_retention_and_secret():
    with pytest.raises(ValidationError):
        TelemetryConfig(mode="hosted_metadata", export_enabled=True)

    with pytest.raises(ValidationError):
        TelemetryConfig(
            mode="hosted_metadata",
            export_enabled=True,
            token=_SECRET_CANARY,
            endpoint="https://collector.example.test",
            region="us",
            access_policy="private_project",
            access_approved=True,
            retention_days=30,
            retention_approved=True,
        )

    with pytest.raises(ValidationError):
        TelemetryConfig(
            mode="local",
            export_enabled=True,
            token=_SECRET_CANARY,
            endpoint="https://logfire-us.pydantic.dev",
            region="us",
            access_policy="private_project",
            access_approved=True,
            retention_days=30,
            retention_approved=True,
        )


def test_local_mode_ignores_logfire_and_otel_exporter_environment(monkeypatch, capsys):
    attempts = _deny_network(monkeypatch)
    monkeypatch.setenv("LOGFIRE_TOKEN", _SECRET_CANARY)
    monkeypatch.setenv("LOGFIRE_API_KEY", _AUTH_CANARY)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", f"authorization={_AUTH_CANARY}")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")

    telemetry = Telemetry(TelemetryConfig(mode="local"))
    with telemetry.span(Operation.REQUEST, request_id="request-001", route=Route.CHAT):
        pass

    serialized = _serialize(telemetry)
    output = capsys.readouterr()
    assert telemetry.available
    assert attempts == []
    assert output.out == ""
    assert output.err == ""
    assert _SECRET_CANARY not in serialized
    assert _AUTH_CANARY not in serialized
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in serialized


def test_manual_spans_correlate_and_record_only_allowlisted_usage():
    telemetry = Telemetry(TelemetryConfig(mode="local"))

    with telemetry.span(Operation.REQUEST, request_id="request-001", route=Route.CHAT):
        with telemetry.span(
            Operation.RETRIEVAL,
            stage=Stage.SEARCH,
            input_count=4,
            result_count=2,
            elapsed_ms=12.5,
        ) as retrieval:
            retrieval.set_usage(
                input_tokens=None,
                output_tokens=7,
                completeness=UsageCompleteness.PARTIAL,
            )

    by_name = {span.name: span for span in telemetry.finished_spans}
    request, retrieval = by_name["request"], by_name["retrieval"]
    assert request.name == "request"
    assert retrieval.name == "retrieval"
    assert retrieval.context.trace_id == request.context.trace_id
    assert retrieval.parent.span_id == request.context.span_id
    assert request.attributes["telemetry.request_id"] == "request-001"
    assert retrieval.attributes["telemetry.request_id"] == "request-001"
    assert retrieval.attributes["telemetry.stage"] == "search"
    assert retrieval.attributes["telemetry.result_count"] == 2
    assert "usage.input_tokens" not in retrieval.attributes
    assert retrieval.attributes["usage.output_tokens"] == 7
    assert retrieval.attributes["usage.completeness"] == "partial"


def test_errors_and_cancellation_never_capture_exception_details(caplog):
    telemetry = Telemetry(TelemetryConfig(mode="local"))

    with pytest.raises(RuntimeError):
        with telemetry.span(Operation.GENERATION, error_code=ErrorCode.UPSTREAM):
            raise RuntimeError(_SECRET_CANARY)

    with pytest.raises(asyncio.CancelledError):
        with telemetry.span(Operation.CANCELLATION, request_id="request-002"):
            raise asyncio.CancelledError(_COOKIE_CANARY)

    serialized = _serialize(telemetry)
    assert _SECRET_CANARY not in serialized
    assert _COOKIE_CANARY not in serialized
    assert _SECRET_CANARY not in caplog.text
    assert _COOKIE_CANARY not in caplog.text
    assert all(not span.events for span in telemetry.finished_spans)
    assert telemetry.finished_spans[0].attributes["telemetry.error_code"] == "upstream"
    assert telemetry.finished_spans[1].attributes["telemetry.outcome"] == "cancelled"
    assert telemetry.finished_spans[1].attributes["telemetry.error_code"] == "cancelled"


def test_unreviewed_or_unapproved_content_is_not_recorded(caplog):
    telemetry = Telemetry(TelemetryConfig(mode="hosted_metadata"))

    forbidden_canaries = (
        _SECRET_CANARY,
        _COOKIE_CANARY,
        _AUTH_CANARY,
        "patient_id=12345678",
    )
    for canary in forbidden_canaries:
        assert (
            telemetry.record_case_content(
                case_id="case-001",
                case_input=canary,
                case_output="synthetic answer",
                classification=ContentClassification.SYNTHETIC,
                consent=True,
                reviewed=True,
            )
            is False
        )
    assert telemetry.finished_spans == ()
    assert all(canary not in _serialize(telemetry) for canary in forbidden_canaries)
    assert all(canary not in caplog.text for canary in forbidden_canaries)

    approved = Telemetry(
        TelemetryConfig(
            mode="approved_public_synthetic_content",
            content_approved=True,
        )
    )
    for canary in forbidden_canaries:
        with pytest.raises(ValueError) as error:
            approved.record_case_content(
                case_id="case-002",
                case_input=canary,
                case_output="synthetic answer",
                classification="synthetic",
                consent=True,
                reviewed=True,
            )
        assert canary not in str(error.value)
    assert approved.finished_spans == ()
    assert all(canary not in _serialize(approved) for canary in forbidden_canaries)

    with pytest.raises(ValueError, match="case content is not approved"):
        approved.record_case_content(
            case_id="case-003",
            case_input="synthetic question",
            case_output="synthetic answer",
            classification="synthetic",
            consent=False,
            reviewed=True,
        )
    assert approved.finished_spans == ()


def test_approved_public_synthetic_content_records_only_explicit_fields():
    telemetry = Telemetry(
        TelemetryConfig(
            mode="approved_public_synthetic_content",
            content_approved=True,
        )
    )

    recorded = telemetry.record_case_content(
        case_id="case-004",
        case_input="Synthetic public question",
        case_output="Synthetic public answer",
        classification=ContentClassification.PUBLIC,
        consent=True,
        reviewed=True,
    )

    assert recorded
    span = telemetry.finished_spans[0]
    assert span.name == "case_content"
    assert span.attributes["content.classification"] == "public"
    assert span.attributes["content.consent"] is True
    assert span.attributes["content.reviewed"] is True
    assert span.attributes["content.input"] == "Synthetic public question"
    assert span.attributes["content.output"] == "Synthetic public answer"
    assert set(span.attributes).issubset(
        {
            "telemetry.operation",
            "telemetry.case_id",
            "telemetry.request_id",
            "telemetry.run_id",
            "telemetry.attempt_id",
            "content.classification",
            "content.consent",
            "content.reviewed",
            "content.input",
            "content.output",
            "telemetry.outcome",
        }
    )


def test_invalid_identifiers_and_arbitrary_fields_are_not_serialized():
    telemetry = Telemetry(TelemetryConfig(mode="local"))

    with telemetry.span(Operation.REQUEST, request_id="patient_id=12345678"):
        pass
    with pytest.raises(TypeError) as error:
        with telemetry.span(Operation.REQUEST, cookie=_COOKIE_CANARY):
            pass
    assert _COOKIE_CANARY not in str(error.value)
    serialized = _serialize(telemetry)
    assert "patient_id=12345678" not in serialized
    assert _COOKIE_CANARY not in serialized
    assert telemetry.finished_spans == ()


def test_generated_uuid_correlation_and_secret_model_canaries_are_safe():
    telemetry = Telemetry(TelemetryConfig(mode="local"))

    with telemetry.span(
        Operation.REQUEST,
        request_id="12345678-1234-4234-8234-123456789abc",
        model="SYNTHETIC_SECRET_CANARY",
    ):
        pass

    assert telemetry.finished_spans == ()
    with telemetry.span(
        Operation.REQUEST,
        request_id="12345678-1234-4234-8234-123456789abc",
        route=Route.CHAT,
    ):
        pass
    span = telemetry.finished_spans[0]
    assert span.attributes["telemetry.request_id"] == "12345678-1234-4234-8234-123456789abc"
    assert "telemetry.model" not in span.attributes
