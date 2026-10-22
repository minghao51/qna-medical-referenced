"""Opt-in local evaluation tracing is bounded, content-free and attempt-owned."""

import asyncio
import json

import pytest

import src.evals.assessment.orchestrator as orchestrator
from src.config import settings
from src.config.settings import TelemetryConfig
from src.evals.schemas import AssessmentRunParams
from src.infra.telemetry import (
    Operation,
    Telemetry,
    current_telemetry,
    telemetry_operation,
    use_telemetry,
)
from tests.unit.evals.test_failed_usage_execution import _pipeline, _reported_usage


def _params(tmp_path):
    return AssessmentRunParams(
        artifact_dir=tmp_path,
        skip_ingestion=True,
        disable_llm_generation=True,
        disable_llm_judging=True,
    )


def _traced_pipeline(error=None):
    pipeline = _pipeline()
    evaluate = pipeline.evaluate_retrieval_fn

    def retrieval(*args, **kwargs):
        with telemetry_operation(Operation.RETRIEVAL):
            _reported_usage()
            if error is not None:
                raise error
            return evaluate(*args, **kwargs)

    pipeline.evaluate_retrieval_fn = retrieval
    return pipeline


def test_default_has_no_trace_artifact_or_new_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "telemetry", TelemetryConfig())
    monkeypatch.setattr(orchestrator, "Telemetry", lambda *a, **k: pytest.fail("unexpected owner"))
    result = _traced_pipeline().run(_params(tmp_path))
    assert not (result.run_dir / "telemetry_metadata.json").exists()
    assert current_telemetry() is None


def test_local_owned_run_matches_store_id_and_uses_only_reported_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "telemetry", TelemetryConfig(mode="local"))
    for _ in range(2):
        result = _traced_pipeline().run(_params(tmp_path))
        manifest = json.loads((result.run_dir / "manifest.json").read_text())
        trace = json.loads((result.run_dir / "telemetry_metadata.json").read_text())
        assert trace["mode"] == "local"
        assert trace["shutdown_completed"] is True
        (root,) = [s for s in trace["spans"] if s["name"] == "run"]
        (child,) = [s for s in trace["spans"] if s["name"] == "retrieval"]
        assert root["attributes"]["telemetry.run_id"] == manifest["execution_id"]
        assert child["attributes"]["telemetry.run_id"] == manifest["execution_id"]
        assert child["parent_span_id"] == root["span_id"]
        assert child["trace_id"] == root["trace_id"]
        assert root["attributes"]["usage.input_tokens"] == 8
        assert root["attributes"]["usage.output_tokens"] == 3
        assert root["attributes"]["usage.completeness"] == "complete"
        assert "synthetic question" not in json.dumps(trace)
        assert current_telemetry() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("cancelled", [False, True])
async def test_failed_and_cancelled_attempts_keep_safe_trace_and_primary(
    tmp_path, monkeypatch, cancelled
):
    monkeypatch.setattr(settings, "telemetry", TelemetryConfig(mode="local"))
    error = (
        asyncio.CancelledError("SYNTHETIC_SECRET_CANARY")
        if cancelled
        else RuntimeError("SYNTHETIC_SECRET_CANARY")
    )
    with pytest.raises(type(error)) as caught:
        _traced_pipeline(error).run(_params(tmp_path))
    assert caught.value is error
    (trace_path,) = tmp_path.glob("*/telemetry_metadata.json")
    text = trace_path.read_text()
    (root,) = [s for s in json.loads(text)["spans"] if s["name"] == "run"]
    assert root["attributes"]["telemetry.outcome"] == ("cancelled" if cancelled else "error")
    assert "SYNTHETIC_SECRET_CANARY" not in text
    assert current_telemetry() is None


def test_caller_owner_is_not_closed_or_persisted_and_run_ids_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "telemetry", TelemetryConfig(mode="local"))
    telemetry = Telemetry(TelemetryConfig(mode="local"))
    with use_telemetry(telemetry):
        results = [_traced_pipeline().run(_params(tmp_path)) for _ in range(2)]
        assert current_telemetry() is telemetry
        with telemetry_operation(Operation.EVALUATION):
            pass
    roots = [s for s in telemetry.finished_spans if s.name == "run"]
    assert len({s.attributes["telemetry.run_id"] for s in roots}) == 2
    unrelated = [s for s in telemetry.finished_spans if s.name == "evaluation"][-1]
    assert "telemetry.run_id" not in unrelated.attributes
    assert not telemetry._closed
    assert all(not (r.run_dir / "telemetry_metadata.json").exists() for r in results)
    assert telemetry.close()


def test_hosted_settings_do_not_construct_a_cli_exporter(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "telemetry",
        TelemetryConfig(
            mode="hosted_metadata",
            export_enabled=True,
            endpoint="https://logfire-us.pydantic.dev",
            region="us",
            access_policy="private_project",
            access_approved=True,
            retention_days=30,
            retention_approved=True,
            token="SYNTHETIC_SECRET_CANARY",
        ),
    )
    monkeypatch.setattr(orchestrator, "Telemetry", lambda *a, **k: pytest.fail("new CLI exporter"))
    result = _traced_pipeline().run(_params(tmp_path))
    assert not (result.run_dir / "telemetry_metadata.json").exists()


@pytest.mark.parametrize("fail_attempt", [False, True])
def test_trace_write_failure_never_replaces_result_or_primary(tmp_path, monkeypatch, fail_attempt):
    monkeypatch.setattr(settings, "telemetry", TelemetryConfig(mode="local"))
    write = orchestrator.ArtifactStore.write_json

    def fail_write(self, name, payload):
        if name == "telemetry_metadata.json":
            raise OSError("SYNTHETIC_SECRET_CANARY")
        return write(self, name, payload)

    monkeypatch.setattr(orchestrator.ArtifactStore, "write_json", fail_write)
    error = RuntimeError("original") if fail_attempt else None
    if fail_attempt:
        with pytest.raises(RuntimeError, match="original"):
            _traced_pipeline(error).run(_params(tmp_path))
    else:
        assert _traced_pipeline().run(_params(tmp_path)).run_dir.exists()


def test_local_metadata_is_an_explicit_bounded_tail_not_a_complete_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "telemetry", TelemetryConfig(mode="local", local_span_capacity=1))
    result = _traced_pipeline().run(_params(tmp_path))
    trace = json.loads((result.run_dir / "telemetry_metadata.json").read_text())
    assert trace["coverage"] == "bounded_tail_not_complete_trace"
    assert trace["span_capacity"] == 1
    assert len(trace["spans"]) == 1
    assert trace["spans"][0]["name"] == "run"


def test_replay_uses_its_execution_id_and_persists_local_trace(tmp_path, monkeypatch):
    from tests.unit.evals.test_replay_contract import _write_verified_benchmark

    monkeypatch.setattr(settings, "telemetry", TelemetryConfig(mode="local"))
    source = tmp_path / "source"
    _write_verified_benchmark(source)
    result = orchestrator.AssessmentPipeline().run(
        AssessmentRunParams(
            artifact_dir=tmp_path / "replays",
            execution_mode="replay",
            replay_snapshot=source,
        )
    )
    trace = json.loads((result.run_dir / "telemetry_metadata.json").read_text())
    (root,) = [s for s in trace["spans"] if s["name"] == "run"]
    assert root["attributes"]["telemetry.run_id"] == result.summary["execution_id"]
    assert root["attributes"]["usage.completeness"] == "unknown"
    assert result.summary["generation_sample"] is False
    assert result.summary["latency_sample"] is False
    assert current_telemetry() is None
