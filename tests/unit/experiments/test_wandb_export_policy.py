import json
import sys
from pathlib import Path

import pytest

from src.experiments.config import _normalize_experiment_dict
from src.experiments.wandb_tracking import log_assessment_to_wandb

CANARY = "synthetic-secret-canary-92f7"


class _FakeArtifact:
    def __init__(self, name: str, type: str, metadata: dict | None = None):
        self.name = name
        self.type = type
        self.metadata = metadata or {}
        self.added_dirs: list[str] = []

    def add_dir(self, path: str) -> None:
        self.added_dirs.append(path)


class _FakeRun:
    def __init__(self):
        self.name = CANARY
        self.id = CANARY
        self.url = f"https://example.invalid/{CANARY}"
        self.logged: list[dict] = []
        self.logged_artifacts: list[_FakeArtifact] = []
        self.finished = False
        self.defined_metrics: list[str] = []
        self.fail_log = False

    def log(self, payload: dict) -> None:
        if self.fail_log:
            raise RuntimeError(CANARY)
        self.logged.append(payload)

    def log_artifact(self, artifact: _FakeArtifact) -> None:
        self.logged_artifacts.append(artifact)

    def define_metric(self, name: str, **kwargs) -> None:
        self.defined_metrics.append(name)
        if name == "retrieval/mrr":
            raise RuntimeError(CANARY)

    def finish(self) -> None:
        self.finished = True


class _FakeWandb:
    def __init__(self):
        self.run = _FakeRun()
        self.inits: list[dict] = []
        self.artifacts: list[_FakeArtifact] = []

    def init(self, **kwargs):
        self.inits.append(kwargs)
        return self.run

    def Artifact(self, name: str, type: str, metadata: dict | None = None):
        artifact = _FakeArtifact(name=name, type=type, metadata=metadata)
        self.artifacts.append(artifact)
        return artifact


def _track(
    monkeypatch,
    *,
    experiment,
    run_dir,
    summary=None,
    manifest=None,
    step_metrics=None,
    retrieval_metrics=None,
    l6_metrics=None,
    failed_thresholds=None,
):
    fake_wandb = _FakeWandb()
    monkeypatch.setitem(sys.modules, "wandb", fake_wandb)
    result = log_assessment_to_wandb(
        experiment=experiment,
        summary=summary or {"status": "ok", "duration_s": 1.5, "failed_thresholds_count": 0},
        manifest=manifest or {},
        step_metrics=step_metrics or {},
        retrieval_metrics=retrieval_metrics or {},
        l6_answer_quality_metrics=l6_metrics or {},
        run_dir=run_dir,
        failed_thresholds=failed_thresholds or [],
    )
    return fake_wandb, result


def test_metadata_only_tracking_filters_canaries_and_defaults_artifact_export_off(
    monkeypatch, tmp_path: Path, caplog
):
    normalized = _normalize_experiment_dict({}, file_path=Path("canary.yaml"))
    assert normalized["tracking"]["wandb"]["log_artifacts"] is False

    experiment = {
        "schema_version": 1,
        "metadata": {"name": CANARY, "description": CANARY, "tags": [CANARY]},
        "variant_name": CANARY,
        "ingestion": {"page_classification_enabled": True, "unknown": CANARY},
        "retrieval": {
            "top_k": 5,
            "search_mode": "rrf_hybrid",
            "by_query_category": {CANARY: {"hit_rate_at_k": 1.0}},
        },
        "secret": CANARY,
        "tracking": {
            "wandb": {
                "enabled": True,
                "mode": "offline",
                "metrics_verbosity": "debug",
                "group": CANARY,
                "tags": [CANARY],
                "notes": CANARY,
            }
        },
    }
    run_dir = tmp_path / CANARY
    fake_wandb, result = _track(
        monkeypatch,
        experiment=experiment,
        run_dir=run_dir,
        summary={"status": CANARY, "duration_s": 1.5, "freeform": CANARY},
        manifest={"patient": CANARY, "prompt": CANARY, "nested": {"body": CANARY}},
        retrieval_metrics={
            "hit_rate_at_k": 0.9,
            "mrr": float("nan"),
            "by_query_category": {CANARY: {"hit_rate_at_k": 1.0}},
            "contribution_analysis": {CANARY: 1.0},
        },
        l6_metrics={"factual_accuracy": {"mean": 0.8, CANARY: CANARY}},
        step_metrics={CANARY: {"aggregate": {CANARY: CANARY}}},
        failed_thresholds=[{"message": CANARY}],
    )

    serialized = json.dumps({"init": fake_wandb.inits, "logged": fake_wandb.run.logged})
    serialized += json.dumps(result) + caplog.text
    assert CANARY not in serialized

    init = fake_wandb.inits[0]
    assert init["project"] is None
    assert init["mode"] == "offline"
    assert init["job_type"] == "pipeline_eval"
    assert "group" not in init
    assert "tags" not in init
    assert "notes" not in init
    assert "name" not in init
    assert init["config"] == {
        "structural_metadata": {
            "schema_version": 1,
            "ingestion": {"page_classification_enabled": True},
            "retrieval": {"top_k": 5, "search_mode": "rrf_hybrid"},
        }
    }
    assert fake_wandb.run.logged == [
        {
            "retrieval/hit_rate": 0.9,
            "l6_answer_quality/factual_accuracy_mean": 0.8,
            "l6_answer_quality/factual_accuracy_error_rate": 0.0,
            "summary/duration_s": 1.5,
            "summary/failed_thresholds": 0,
            "thresholds/failed_count": 1,
        }
    ]
    assert not fake_wandb.artifacts
    assert result["artifact_export_enabled"] is False
    assert not {"run_name", "run_id", "run_url"} & result.keys()


def test_sdk_exception_details_are_not_logged_or_returned(monkeypatch, tmp_path: Path, caplog):
    experiment = {"tracking": {"wandb": {"enabled": True, "mode": "offline"}}}
    fake_wandb = _FakeWandb()
    fake_wandb.run.fail_log = True
    monkeypatch.setitem(sys.modules, "wandb", fake_wandb)

    result = log_assessment_to_wandb(
        experiment=experiment,
        summary={"duration_s": 1.0},
        manifest={},
        step_metrics={},
        retrieval_metrics={"hit_rate_at_k": 0.5},
        l6_answer_quality_metrics={},
        run_dir=tmp_path,
        failed_thresholds=[],
    )

    assert result == {
        "enabled": True,
        "status": "error",
        "error": "tracking failed",
        "artifact_export_enabled": False,
    }
    assert CANARY not in caplog.text
    assert fake_wandb.run.finished is True


@pytest.mark.parametrize("field", ["enabled", "log_artifacts"])
def test_tracking_boolean_strings_fail_validation(field):
    with pytest.raises(ValueError, match="must be a boolean"):
        _normalize_experiment_dict(
            {"tracking": {"wandb": {field: "false"}}},
            file_path=Path("synthetic.yaml"),
        )


def test_unknown_tracking_mode_never_falls_back_to_online(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="tracking mode"):
        _normalize_experiment_dict(
            {"tracking": {"wandb": {"mode": "synthetic-typo"}}},
            file_path=Path("synthetic.yaml"),
        )
    fake, result = _track(
        monkeypatch,
        experiment={"tracking": {"wandb": {"enabled": True, "mode": "synthetic-typo"}}},
        run_dir=tmp_path,
    )
    assert fake.inits == []
    assert result["status"] == "error"


@pytest.mark.parametrize("boundary", ["init", "finish"])
def test_export_lifecycle_errors_omit_exception_canary(monkeypatch, tmp_path, caplog, boundary):
    fake = _FakeWandb()

    def fail(*args, **kwargs):
        raise RuntimeError(CANARY)

    if boundary == "init":
        fake.init = fail
    else:
        fake.run.finish = fail
    monkeypatch.setitem(sys.modules, "wandb", fake)
    result = log_assessment_to_wandb(
        experiment={"tracking": {"wandb": {"enabled": True, "mode": "offline"}}},
        summary={},
        manifest={},
        step_metrics={},
        retrieval_metrics={},
        l6_answer_quality_metrics={},
        run_dir=tmp_path,
        failed_thresholds=[],
    )
    assert CANARY not in caplog.text + json.dumps(result)


def test_explicit_artifact_opt_in_retains_legacy_upload_with_fake_sdk(
    monkeypatch, tmp_path: Path, caplog
):

    fake_wandb, result = _track(
        monkeypatch,
        experiment={"tracking": {"wandb": {"enabled": True, "log_artifacts": True}}},
        run_dir=tmp_path,
    )

    assert result["status"] == "logged"
    assert result["artifact_export_enabled"] is True
    assert len(fake_wandb.run.logged_artifacts) == 1
    assert fake_wandb.run.logged_artifacts[0].added_dirs == [str(tmp_path)]
    assert "not content-policy approval" in caplog.text
