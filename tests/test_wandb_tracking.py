import sys
from pathlib import Path

from src.experiments.wandb_tracking import log_assessment_to_wandb


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
        self.name = "baseline"
        self.id = "run-123"
        self.url = "https://wandb.example/run-123"
        self.logged: list[dict] = []
        self.logged_artifacts: list[_FakeArtifact] = []
        self.finished = False

    def log(self, payload: dict) -> None:
        self.logged.append(payload)

    def log_artifact(self, artifact: _FakeArtifact) -> None:
        self.logged_artifacts.append(artifact)

    def finish(self) -> None:
        self.finished = True


class _FakeWandb:
    def __init__(self):
        self.run = _FakeRun()
        self.inits: list[dict] = []

    def init(self, **kwargs):
        self.inits.append(kwargs)
        return self.run

    def Artifact(self, name: str, type: str, metadata: dict | None = None):  # noqa: N802
        return _FakeArtifact(name=name, type=type, metadata=metadata)


def test_log_assessment_to_wandb_logs_metrics_and_artifacts(monkeypatch, tmp_path: Path):
    fake_wandb = _FakeWandb()
    monkeypatch.setitem(sys.modules, "wandb", fake_wandb)

    run_dir = tmp_path / "20260308T101010.123456Z_baseline"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text("{}", encoding="utf-8")

    tracking = log_assessment_to_wandb(
        experiment={
            "metadata": {"name": "baseline"},
            "tracking": {
                "wandb": {
                    "enabled": True,
                    "project": "demo-project",
                    "entity": "demo-entity",
                    "group": "nightly",
                    "job_type": "pipeline_eval",
                    "tags": ["baseline"],
                    "notes": "nightly run",
                    "mode": "offline",
                    "log_artifacts": True,
                }
            },
        },
        summary={"status": "ok", "duration_s": 1.5, "failed_thresholds_count": 0},
        manifest={"experiment": {"variant": None}},
        step_metrics={"l1": {"aggregate": {"markdown_empty_rate": 0.1}}},
        retrieval_metrics={"hit_rate_at_k": 0.9, "mrr": 0.8},
        rag_metrics={"groundedness": 0.7},
        run_dir=run_dir,
        failed_thresholds=[],
    )

    assert tracking["status"] == "logged"
    assert tracking["run_id"] == "run-123"
    assert fake_wandb.inits[0]["project"] == "demo-project"
    assert fake_wandb.run.logged
    assert fake_wandb.run.logged[0]["retrieval.hit_rate_at_k"] == 0.9
    assert fake_wandb.run.logged_artifacts[0].added_dirs == [str(run_dir)]
    assert fake_wandb.run.finished is True
