import sys

from src.experiments import wandb_history


class _FakeRemoteRun:
    def __init__(self, *, run_id: str, name: str):
        self.id = run_id
        self.name = name
        self.url = f"https://wandb.example/{run_id}"
        self.state = "finished"
        self.created_at = "2026-03-09T09:00:00"
        self.summary = {
            "status": "ok",
            "duration_s": 3,
            "retrieval.hit_rate_at_k": 0.8,
            "retrieval.mrr": 0.7,
        }
        self.config = {
            "experiment": {"metadata": {"name": "baseline"}},
            "manifest": {"experiment": {"index_config_hash": "idx123"}},
        }


class _FakeApi:
    def __init__(self, runs):
        self._runs = runs
        self.calls = 0

    def runs(self, path, per_page, order):
        self.calls += 1
        return list(self._runs)


class _FakeWandb:
    def __init__(self, runs):
        self.api = _FakeApi(runs)

    def Api(self):  # noqa: N802
        return self.api


def test_fetch_wandb_runs_uses_cache(monkeypatch):
    fake_wandb = _FakeWandb([_FakeRemoteRun(run_id="run-1", name="baseline")])
    monkeypatch.setitem(sys.modules, "wandb", fake_wandb)
    monkeypatch.setattr(wandb_history.settings, "wandb_cache_ttl_seconds", 60)
    wandb_history.clear_wandb_cache()

    first = wandb_history.fetch_wandb_runs(project="demo", entity="team", limit=10)
    second = wandb_history.fetch_wandb_runs(project="demo", entity="team", limit=10)

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert fake_wandb.api.calls == 1


def test_fetch_wandb_run_cache_expires(monkeypatch):
    fake_wandb = _FakeWandb([_FakeRemoteRun(run_id="run-1", name="baseline")])
    now = {"value": 100.0}
    monkeypatch.setitem(sys.modules, "wandb", fake_wandb)
    monkeypatch.setattr(wandb_history.settings, "wandb_cache_ttl_seconds", 5)
    monkeypatch.setattr(wandb_history.time, "time", lambda: now["value"])
    wandb_history.clear_wandb_cache()

    first = wandb_history.fetch_wandb_run(project="demo", entity="team", run_id="run-1")
    now["value"] = 103.0
    second = wandb_history.fetch_wandb_run(project="demo", entity="team", run_id="run-1")
    now["value"] = 106.0
    third = wandb_history.fetch_wandb_run(project="demo", entity="team", run_id="run-1")

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert third["status"] == "ok"
    assert fake_wandb.api.calls == 2
