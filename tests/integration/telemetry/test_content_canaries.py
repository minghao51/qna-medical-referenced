"""Offline content canaries: secrets, cookies, patient-like IDs and prompt text
never reach telemetry spans, application logs, or report/artifact strings except
through the single approved public/synthetic content path."""

import asyncio
import json
import socket
import threading
import uuid

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from pydantic import SecretStr

from src.cli import eval_pipeline
from src.config import settings
from src.config.settings import TelemetryConfig
from src.evals.schemas import AssessmentRunParams
from src.infra.telemetry import (
    ContentClassification,
    ErrorCode,
    Operation,
    Route,
    Stage,
    Telemetry,
    start_telemetry_operation,
    telemetry_operation,
    use_telemetry,
)
from tests.unit.evals.test_failed_usage_execution import _pipeline, _reported_usage

# Canary vocabulary: the guard markers recognized by _FORBIDDEN_CONTENT_CANARIES
# in src/infra/telemetry.py plus the additional shapes required by the P3-C
# brief (Bearer-style tokens, Set-Cookie headers, MRN-like identifiers, and
# full prompt/context text blocks). Every token matches at least one guard
# pattern, so every rejection below exercises the shipped guard, not a new one.
_SECRET_CANARY = "SYNTHETIC_SECRET_CANARY"
_COOKIE_CANARY = "SYNTHETIC_COOKIE_CANARY"
_AUTH_CANARY = "SYNTHETIC_AUTH_CANARY"
_BEARER_CANARY = "Authorization: Bearer SYNTHETIC_BEARER_TOKEN_CANARY"
# Standalone token marker with no "Authorization:" prefix; the shipped guard
# in src/infra/telemetry.py recognizes this marker by itself.
_STANDALONE_BEARER_CANARY = "SYNTHETIC_BEARER_TOKEN_CANARY"
_SET_COOKIE_CANARY = "Set-Cookie: session=synthetic-session-0123456"
_MRN_CANARY = "MRN-0045712"
_NUMERIC_ID_CANARY = "0043219"
_PROMPT_CANARY = (
    "system: synthetic clinical prompt\n"
    "user: synthetic question about case 1234567\n"
    "instructions: treat as synthetic; secret: synthetic-value"
)
_CONTEXT_CANARY = (
    "retrieved context: patient_id=0043219\n"
    "Set-Cookie: session=synthetic-0123456\n"
    "Authorization: Bearer SYNTHETIC_BEARER_TOKEN_CANARY"
)
_EXCEPTION_CANARY = "SYNTHETIC_GENERATION_EXCEPTION_CANARY secret: synthetic-value"
_IDENTIFIER_CANARIES = (
    {"request_id": _SECRET_CANARY},
    {"run_id": "run-patient-0043219"},
    {"case_id": "case-cookie-0123456"},
    {"attempt_id": "attempt-mrn-7734561"},
    {"model": "SYNTHETIC_COOKIE_CANARY"},
    {"model": "model-cookie:0123456"},
    {"request_id": _PROMPT_CANARY},
)
_CONTENT_CANARIES = (
    _SECRET_CANARY,
    _COOKIE_CANARY,
    _AUTH_CANARY,
    _BEARER_CANARY,
    _STANDALONE_BEARER_CANARY,
    _SET_COOKIE_CANARY,
    _MRN_CANARY,
    _NUMERIC_ID_CANARY,
    _PROMPT_CANARY,
    _CONTEXT_CANARY,
)
_ALL_CANARIES = (
    *_CONTENT_CANARIES,
    _EXCEPTION_CANARY,
    "run-patient-0043219",
    "case-cookie-0123456",
    "attempt-mrn-7734561",
    "model-cookie:0123456",
)

_APPROVED_INPUT = "synthetic question about the public corpus"
_APPROVED_OUTPUT = "synthetic answer citing synthetic sources"

_ALLOWLISTED_SPAN_ATTRIBUTES = frozenset(
    {
        "telemetry.operation",
        "telemetry.request_id",
        "telemetry.run_id",
        "telemetry.case_id",
        "telemetry.attempt_id",
        "telemetry.stage",
        "telemetry.route",
        "telemetry.model",
        "telemetry.input_count",
        "telemetry.result_count",
        "telemetry.retry_count",
        "telemetry.elapsed_ms",
        "telemetry.outcome",
        "telemetry.error_code",
        "usage.input_tokens",
        "usage.output_tokens",
        "usage.completeness",
    }
)
_CASE_CONTENT_ATTRIBUTES = _ALLOWLISTED_SPAN_ATTRIBUTES | {
    "content.classification",
    "content.consent",
    "content.reviewed",
    "content.input",
    "content.output",
}
_FAIL_CLOSED_REASONS = frozenset(
    {
        "external_overage_and_auto_top_up_not_confirmed_off",
        "monthly_usage_or_cash_is_incomplete",
        "monthly_run_usage_unavailable",
        "recorded_monthly_cash_ceiling_reached",
    }
)
_FIXED_LIMITATIONS = {
    "Does not include in-flight, delayed, or outside-repository charges",
    "Quota-value estimates and existing subscriptions are not incremental cash",
    "Recorded usage and estimates do not guarantee actual provider billing totals",
    "Local usage records do not enforce an operational hard spending cap",
    "Automatic provider overage and auto-top-up status are not verified by local records",
    "Existing subscription charges are excluded from the incremental cash ceiling",
    "Interactive chat serving is not budget-gated by these records",
}


def _hosted_metadata_config() -> TelemetryConfig:
    return TelemetryConfig(mode="hosted_metadata")


def _approved_content_config() -> TelemetryConfig:
    return TelemetryConfig(
        mode="approved_public_synthetic_content",
        content_approved=True,
    )


def _hosted_export_config() -> TelemetryConfig:
    return TelemetryConfig(
        mode="hosted_metadata",
        export_enabled=True,
        endpoint="https://logfire-us.pydantic.dev",
        region="us",
        access_policy="private_project",
        access_approved=True,
        retention_days=30,
        retention_approved=True,
        token=SecretStr("SYNTHETIC_TELEMETRY_TOKEN"),
        # These tests assert content sanitation, not the bounded-lifecycle
        # contract (covered in tests/unit/infra/test_telemetry_lifecycle.py and
        # test_explicit_export_destination.py). A 100 ms budget raced the
        # lifecycle thread hand-off under CPU contention and flipped aclose()
        # to False; 1 s keeps the same seam with scheduling headroom.
        shutdown_timeout_seconds=1.0,
    )


def _deny_network(monkeypatch):
    attempts = []

    def denied(*args, **kwargs):
        attempts.append("network")
        raise AssertionError("canary telemetry test attempted network access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket, "gethostbyname", denied)
    monkeypatch.setattr(socket, "gethostbyaddr", denied)
    return attempts


def _span_payload(spans) -> str:
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
            for span in spans
        ],
        sort_keys=True,
        default=str,
    )


def _serialize(telemetry: Telemetry) -> str:
    return _span_payload(telemetry.finished_spans)


def _assert_canary_free(payload: str, caplog=None) -> None:
    for canary in _ALL_CANARIES:
        assert canary not in payload
        if caplog is not None:
            assert canary not in caplog.text


def _application_log_text(caplog) -> str:
    """Application-log filter per tests/integration/app/test_log_privacy.py."""
    return "\n".join(
        record.getMessage() for record in caplog.records if record.name.startswith("src.")
    )


def _assert_allowlisted_attributes(spans, *, allow_content: bool = False) -> None:
    allowed = _CASE_CONTENT_ATTRIBUTES if allow_content else _ALLOWLISTED_SPAN_ATTRIBUTES
    for span in spans:
        assert set(span.attributes or {}).issubset(allowed)
        assert not span.events


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
        raise RuntimeError(_EXCEPTION_CANARY)


# --- Surface 1: span attributes via the public Telemetry surface -------------


def test_hosted_metadata_span_metadata_rejects_every_canary_shape(monkeypatch, caplog):
    attempts = _deny_network(monkeypatch)
    telemetry = Telemetry(_hosted_metadata_config())

    for metadata in _IDENTIFIER_CANARIES:
        with telemetry.span(Operation.REQUEST, **metadata):
            pass
    assert (
        telemetry.record_case_content(
            case_id="case-0001",
            case_input=_CONTEXT_CANARY,
            case_output=_PROMPT_CANARY,
            classification=ContentClassification.SYNTHETIC,
            consent=True,
            reviewed=True,
        )
        is False
    )
    assert telemetry.finished_spans == ()

    # Positive control: clean generated identifiers still produce spans.
    with telemetry.span(
        Operation.REQUEST,
        request_id=str(uuid.uuid4()),
        route=Route.CHAT,
        model="synthetic-eval-model",
    ):
        pass
    assert len(telemetry.finished_spans) == 1
    payload = _serialize(telemetry)
    _assert_allowlisted_attributes(telemetry.finished_spans)
    _assert_canary_free(payload, caplog)
    assert attempts == []


def test_hosted_metadata_exported_spans_carry_only_allowlisted_metadata(monkeypatch, caplog):
    attempts = _deny_network(monkeypatch)
    exporter = _RecordingExporter()
    telemetry = Telemetry(_hosted_export_config(), exporter=exporter)

    for metadata in _IDENTIFIER_CANARIES:
        with telemetry.span(Operation.REQUEST, **metadata):
            pass
    assert (
        telemetry.record_case_content(
            case_id="case-0001",
            case_input=_SET_COOKIE_CANARY,
            case_output="synthetic answer",
            classification=ContentClassification.SYNTHETIC,
            consent=True,
            reviewed=True,
        )
        is False
    )
    with pytest.raises(RuntimeError):
        with telemetry.span(Operation.GENERATION, error_code=ErrorCode.UPSTREAM):
            raise RuntimeError(_EXCEPTION_CANARY)
    with telemetry.span(Operation.REQUEST, request_id=str(uuid.uuid4()), route=Route.CHAT):
        pass

    assert asyncio.run(telemetry.force_flush())
    # Only the two clean spans reach the fake exporter; canary attempts record nothing.
    assert len(exporter.spans) == 2
    _assert_allowlisted_attributes(exporter.spans)
    _assert_canary_free(_span_payload(exporter.spans), caplog)
    assert attempts == []
    assert asyncio.run(telemetry.aclose())
    assert exporter.shutdown_called.is_set()


def test_module_level_operation_helpers_drop_canary_metadata(caplog):
    telemetry = Telemetry(_hosted_metadata_config())

    with use_telemetry(telemetry):
        with telemetry_operation(Operation.REQUEST, request_id=_SECRET_CANARY):
            pass
        handle = start_telemetry_operation(Operation.RETRIEVAL, model="model-cookie:0123456")
        handle.finish(outcome="retry", error_code=ErrorCode.TIMEOUT)
        assert telemetry.finished_spans == ()
        with telemetry_operation(
            Operation.REQUEST, request_id=str(uuid.uuid4()), route=Route.CHAT
        ) as span:
            span.set_result_count(1)

    assert len(telemetry.finished_spans) == 1
    _assert_allowlisted_attributes(telemetry.finished_spans)
    _assert_canary_free(_serialize(telemetry), caplog)


# --- Surface 2: record_case_content in both modes ----------------------------


def test_record_case_content_metadata_modes_return_false_and_record_nothing():
    for config in (
        _hosted_metadata_config(),
        TelemetryConfig(mode="approved_public_synthetic_content", content_approved=False),
    ):
        telemetry = Telemetry(config)
        assert (
            telemetry.record_case_content(
                case_id="case-0001",
                case_input=_APPROVED_INPUT,
                case_output=_APPROVED_OUTPUT,
                classification=ContentClassification.SYNTHETIC,
                consent=True,
                reviewed=True,
            )
            is False
        )
        assert (
            telemetry.record_case_content(
                case_id="case-0001",
                case_input=_SECRET_CANARY,
                case_output=_APPROVED_OUTPUT,
                classification=ContentClassification.SYNTHETIC,
                consent=True,
                reviewed=True,
            )
            is False
        )
        assert telemetry.finished_spans == ()


def test_approved_content_mode_records_synthetic_content_only_in_case_content_span():
    telemetry = Telemetry(_approved_content_config())

    recorded = telemetry.record_case_content(
        case_id="case-0001",
        case_input=_APPROVED_INPUT,
        case_output=_APPROVED_OUTPUT,
        classification=ContentClassification.SYNTHETIC,
        consent=True,
        reviewed=True,
    )
    assert recorded is True
    case_span = telemetry.finished_spans[0]
    assert case_span.name == "case_content"
    assert case_span.attributes["content.input"] == _APPROVED_INPUT
    assert case_span.attributes["content.output"] == _APPROVED_OUTPUT
    assert case_span.attributes["content.classification"] == "synthetic"
    assert case_span.attributes["content.consent"] is True
    assert case_span.attributes["content.reviewed"] is True
    assert case_span.attributes["telemetry.outcome"] == "success"
    assert set(case_span.attributes).issubset(_CASE_CONTENT_ATTRIBUTES)
    assert not case_span.events

    # Metadata spans in the same owner never carry content fields.
    with telemetry.span(Operation.REQUEST, request_id=str(uuid.uuid4()), route=Route.CHAT):
        pass
    request_span = telemetry.finished_spans[1]
    assert set(request_span.attributes).issubset(_ALLOWLISTED_SPAN_ATTRIBUTES)
    assert _APPROVED_INPUT not in _span_payload([request_span])
    assert _APPROVED_OUTPUT not in _span_payload([request_span])

    # The 2048-char content ceiling is inclusive for approved synthetic text.
    boundary_content = ("synthetic " * 205)[:2048]
    assert len(boundary_content) == 2048
    assert (
        telemetry.record_case_content(
            case_id="case-0002",
            case_input=boundary_content,
            case_output=_APPROVED_OUTPUT,
            classification=ContentClassification.PUBLIC,
            consent=True,
            reviewed=True,
        )
        is True
    )
    assert telemetry.finished_spans[2].attributes["content.input"] == boundary_content


@pytest.mark.parametrize("canary", _CONTENT_CANARIES)
def test_approved_content_mode_rejects_forbidden_canaries_in_input_and_output(caplog, canary):
    telemetry = Telemetry(_approved_content_config())

    for placement in ("case_input", "case_output"):
        kwargs = {
            "case_input": _APPROVED_INPUT,
            "case_output": _APPROVED_OUTPUT,
            placement: canary,
        }
        with pytest.raises(ValueError) as error:
            telemetry.record_case_content(
                case_id="case-0001",
                classification=ContentClassification.SYNTHETIC,
                consent=True,
                reviewed=True,
                **kwargs,
            )
        assert canary not in str(error.value)
    assert telemetry.finished_spans == ()
    _assert_canary_free(_serialize(telemetry), caplog)


@pytest.mark.parametrize("placement", ["case_input", "case_output"])
def test_standalone_bearer_token_canary_rejected_without_header_prefix(caplog, placement):
    """Review M2 regression: the token marker alone (no Authorization prefix)
    must trip the content guard in either field and record nothing."""
    telemetry = Telemetry(_approved_content_config())

    kwargs = {
        "case_input": _APPROVED_INPUT,
        "case_output": _APPROVED_OUTPUT,
        placement: _STANDALONE_BEARER_CANARY,
    }
    with pytest.raises(ValueError) as error:
        telemetry.record_case_content(
            case_id="case-0001",
            classification=ContentClassification.SYNTHETIC,
            consent=True,
            reviewed=True,
            **kwargs,
        )
    assert _STANDALONE_BEARER_CANARY not in str(error.value)
    assert telemetry.finished_spans == ()
    _assert_canary_free(_serialize(telemetry), caplog)


def test_case_content_validation_failures_raise_and_record_nothing(caplog):
    telemetry = Telemetry(_approved_content_config())
    failures = [
        # Missing consent.
        {
            "case_id": "case-0001",
            "case_input": _APPROVED_INPUT,
            "case_output": _APPROVED_OUTPUT,
            "classification": ContentClassification.SYNTHETIC,
            "consent": False,
            "reviewed": True,
        },
        # Missing review.
        {
            "case_id": "case-0001",
            "case_input": _APPROVED_INPUT,
            "case_output": _APPROVED_OUTPUT,
            "classification": ContentClassification.SYNTHETIC,
            "consent": True,
            "reviewed": False,
        },
        # Oversized content.
        {
            "case_id": "case-0001",
            "case_input": "s" * 2049,
            "case_output": _APPROVED_OUTPUT,
            "classification": ContentClassification.SYNTHETIC,
            "consent": True,
            "reviewed": True,
        },
        # Invalid/canary-bearing case ids.
        {
            "case_id": "patient_id=0043219",
            "case_input": _APPROVED_INPUT,
            "case_output": _APPROVED_OUTPUT,
            "classification": ContentClassification.SYNTHETIC,
            "consent": True,
            "reviewed": True,
        },
        {
            "case_id": "case with spaces",
            "case_input": _APPROVED_INPUT,
            "case_output": _APPROVED_OUTPUT,
            "classification": ContentClassification.SYNTHETIC,
            "consent": True,
            "reviewed": True,
        },
        # Invalid classification.
        {
            "case_id": "case-0001",
            "case_input": _APPROVED_INPUT,
            "case_output": _APPROVED_OUTPUT,
            "classification": "internal",
            "consent": True,
            "reviewed": True,
        },
    ]
    for kwargs in failures:
        with pytest.raises(ValueError) as error:
            telemetry.record_case_content(**kwargs)
        for canary in _ALL_CANARIES:
            assert canary not in str(error.value)
    assert telemetry.finished_spans == ()
    _assert_canary_free(_serialize(telemetry), caplog)


# --- Surface 3: error, mark_error and retry paths ----------------------------


def test_error_mark_error_and_retry_outcomes_carry_only_allowlisted_codes(caplog):
    telemetry = Telemetry(_hosted_metadata_config())
    error_codes = {code.value for code in ErrorCode}

    with pytest.raises(RuntimeError):
        with telemetry.span(Operation.GENERATION, error_code=ErrorCode.UPSTREAM):
            raise RuntimeError(_EXCEPTION_CANARY)
    with telemetry.span(Operation.SEARCH, stage=Stage.SEARCH) as span:
        span.mark_error(ErrorCode.TIMEOUT)
        span.finish()
    retry_span = telemetry.start_span(Operation.RETRY, attempt_id=str(uuid.uuid4()), retry_count=1)
    retry_span.finish(outcome="retry", error_code=ErrorCode.RETRY_EXHAUSTED)
    coerced = telemetry.start_span(Operation.REQUEST)
    coerced.finish(outcome="not-an-outcome")
    uncoded = telemetry.start_span(Operation.REQUEST)
    uncoded.finish(outcome="error", error_code="not-an-error-code")

    spans = telemetry.finished_spans
    assert [span.name for span in spans] == [
        "generation",
        "search",
        "retry",
        "request",
        "request",
    ]
    for span in spans:
        assert span.status.status_code.name == "ERROR"
        assert not span.events
        assert set(span.attributes).issubset(_ALLOWLISTED_SPAN_ATTRIBUTES)
        code = span.attributes.get("telemetry.error_code")
        if code is not None:
            assert code in error_codes
    assert spans[0].attributes["telemetry.outcome"] == "error"
    assert spans[0].attributes["telemetry.error_code"] == "upstream"
    assert spans[1].attributes["telemetry.outcome"] == "error"
    assert spans[1].attributes["telemetry.error_code"] == "timeout"
    assert spans[2].attributes["telemetry.outcome"] == "retry"
    assert spans[2].attributes["telemetry.error_code"] == "retry_exhausted"
    # Unrecognized outcomes coerce to the fixed "error" enum; unrecognized error
    # codes leave no error_code attribute at all.
    assert spans[3].attributes["telemetry.outcome"] == "error"
    assert "telemetry.error_code" not in spans[3].attributes
    assert spans[4].attributes["telemetry.outcome"] == "error"
    assert "telemetry.error_code" not in spans[4].attributes
    _assert_canary_free(_serialize(telemetry), caplog)


# --- Surface 4: application log output ---------------------------------------


def test_canaries_stay_out_of_application_logs_with_hosted_export_active(monkeypatch, caplog):
    attempts = _deny_network(monkeypatch)
    exporter = _FailingExporter()
    telemetry = Telemetry(_hosted_export_config(), exporter=exporter)

    with telemetry.span(Operation.REQUEST, request_id=_SECRET_CANARY):
        pass
    with pytest.raises(RuntimeError):
        with telemetry.span(Operation.GENERATION, error_code=ErrorCode.UPSTREAM):
            raise RuntimeError(_EXCEPTION_CANARY)
    assert (
        telemetry.record_case_content(
            case_id="case-0001",
            case_input=_CONTEXT_CANARY,
            case_output=_PROMPT_CANARY,
            classification=ContentClassification.SYNTHETIC,
            consent=True,
            reviewed=True,
        )
        is False
    )

    assert asyncio.run(telemetry.force_flush())
    assert exporter.called.wait(1)
    assert asyncio.run(telemetry.aclose())
    _assert_canary_free(_application_log_text(caplog))
    _assert_canary_free(caplog.text)
    assert attempts == []


def test_canaries_stay_out_of_application_logs_with_content_mode_active(caplog):
    telemetry = Telemetry(_approved_content_config())

    for canary in _CONTENT_CANARIES:
        with pytest.raises(ValueError):
            telemetry.record_case_content(
                case_id="case-0001",
                case_input=canary,
                case_output=_APPROVED_OUTPUT,
                classification=ContentClassification.SYNTHETIC,
                consent=True,
                reviewed=True,
            )
    with pytest.raises(RuntimeError):
        with telemetry.span(Operation.GENERATION):
            raise RuntimeError(_EXCEPTION_CANARY)
    telemetry.record_case_content(
        case_id="case-0002",
        case_input=_APPROVED_INPUT,
        case_output=_APPROVED_OUTPUT,
        classification=ContentClassification.SYNTHETIC,
        consent=True,
        reviewed=True,
    )

    assert [span.name for span in telemetry.finished_spans] == ["generation", "case_content"]
    generation = telemetry.finished_spans[0]
    assert generation.attributes["telemetry.outcome"] == "error"
    assert not generation.events
    _assert_canary_free(_application_log_text(caplog))
    _assert_canary_free(caplog.text)


# --- Surface 5: report and artifact paths ------------------------------------


def _params(tmp_path):
    return AssessmentRunParams(
        artifact_dir=tmp_path,
        skip_ingestion=True,
        disable_llm_generation=True,
        disable_llm_judging=True,
    )


def _canary_failed_attempt(tmp_path, monkeypatch):
    """Run the synthetic evaluation pipeline once with canaries in the failure."""
    monkeypatch.setattr(settings, "telemetry", TelemetryConfig(mode="local"))
    pipeline = _pipeline()

    def retrieval(*args, **kwargs):
        with telemetry_operation(Operation.RETRIEVAL, model="synthetic-eval-model"):
            with telemetry_operation(Operation.SEARCH, request_id=_SECRET_CANARY):
                pass
            _reported_usage()
            raise RuntimeError(_EXCEPTION_CANARY)

    pipeline.evaluate_retrieval_fn = retrieval
    with pytest.raises(RuntimeError):
        pipeline.run(_params(tmp_path))

    (trace_path,) = tmp_path.glob("*/telemetry_metadata.json")
    (manifest_path,) = tmp_path.glob("*/manifest.json")
    return (
        trace_path.read_text(encoding="utf-8"),
        json.loads(manifest_path.read_text(encoding="utf-8")),
    )


def test_failed_attempt_telemetry_artifact_and_manifests_stay_canary_free(
    tmp_path, monkeypatch, caplog
):
    trace_text, manifest = _canary_failed_attempt(tmp_path, monkeypatch)

    trace = json.loads(trace_text)
    assert trace["mode"] == "local"
    assert trace["shutdown_completed"] is True
    assert sorted(span["name"] for span in trace["spans"]) == ["retrieval", "run"]
    for span in trace["spans"]:
        assert set(span["attributes"]).issubset(_ALLOWLISTED_SPAN_ATTRIBUTES)
        assert span["attributes"].get("telemetry.error_code") in (
            {code.value for code in ErrorCode} | {None}
        )
    (retrieval_span,) = [s for s in trace["spans"] if s["name"] == "retrieval"]
    assert retrieval_span["attributes"]["telemetry.outcome"] == "error"

    for canary in _ALL_CANARIES:
        assert canary not in trace_text
        assert canary not in json.dumps(manifest)
        assert canary not in caplog.text
    assert manifest["execution_status"] == "failed"
    assert uuid.UUID(manifest["execution_id"]).version == 4


def test_failed_attempt_summary_json_artifact_stays_canary_free(tmp_path, monkeypatch, caplog):
    """The separately written summary.json must stay canary-free like the manifest."""
    _, manifest = _canary_failed_attempt(tmp_path, monkeypatch)

    (summary_path,) = tmp_path.glob("*/summary.json")
    summary_text = summary_path.read_text(encoding="utf-8")
    summary = json.loads(summary_text)

    assert summary["execution_id"] == manifest["execution_id"]
    assert uuid.UUID(summary["execution_id"]).version == 4
    assert summary["execution_status"] == "failed"
    assert summary["status"] == "failed"
    assert summary["quality_gate"] == "incomplete"
    assert summary["measurement"] == {
        "status": "incomplete",
        "reason": "assessment_attempt_failed",
    }
    assert summary["usage_summary"]["usage_status"] == "incomplete"
    for canary in _ALL_CANARIES:
        assert canary not in summary_text
        assert canary not in caplog.text


def test_offline_budget_diagnostics_report_stays_canary_free(tmp_path, monkeypatch, capsys):
    _, manifest = _canary_failed_attempt(tmp_path, monkeypatch)
    usage_summary = manifest["usage_summary"]
    summary_path = tmp_path / "usage-summary.json"
    summary_path.write_text(
        json.dumps({"execution_mode": "diagnostic", "usage_summary": usage_summary}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "eval_pipeline",
            "--usage-summary",
            str(summary_path),
            "--usage-month",
            usage_summary["utc_month"],
            "--confirm-overage-off",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        eval_pipeline.main()

    assert exc.value.code == 0
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)
    assert set(report["operation_admission"]) == {"benchmark", "diagnostic"}
    for admission in report["operation_admission"].values():
        assert admission["allowed"] is False
        assert set(admission["reasons"]).issubset(_FAIL_CLOSED_REASONS)
        assert set(admission["limitations"]).issubset(_FIXED_LIMITATIONS)
        assert admission["operation"] in {"benchmark", "diagnostic"}
    assert report["unknown_usage_count"] == 1
    # Only fresh generated run identifiers may be counted; never their content.
    assert report["known_cash_usd"] is None
    for canary in _ALL_CANARIES:
        assert canary not in serialized
