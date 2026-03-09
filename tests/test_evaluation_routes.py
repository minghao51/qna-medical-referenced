import json

from src.app.routes import evaluation


def test_evaluation_history_includes_microsecond_run_dirs(monkeypatch, tmp_path):
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()

    newer = evals_dir / "20260308T101010.123456Z_baseline"
    older = evals_dir / "20260308T091010.654321Z_baseline"
    for idx, run_dir in enumerate([newer, older], start=1):
        run_dir.mkdir()
        (run_dir / "summary.json").write_text(
            json.dumps(
                {
                    "status": "ok",
                    "duration_s": idx,
                    "failed_thresholds_count": 0,
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "retrieval_metrics.json").write_text(
            json.dumps(
                {
                    "hit_rate_at_k": 0.1 * idx,
                    "mrr": 0.2 * idx,
                    "ndcg_at_k": 0.3 * idx,
                    "latency_p50_ms": 10 * idx,
                    "latency_p95_ms": 20 * idx,
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(evaluation, "EVALS_DIR", evals_dir)
    monkeypatch.setattr(evaluation, "LATEST_POINTER", evals_dir / "latest_run.txt")

    history = evaluation.get_evaluation_history(limit=10)
    runs = evaluation.get_evaluation_runs()

    assert history["runs"][0]["run_dir"] == newer.name
    assert runs[0]["run_dir"] == newer.name


def test_evaluation_history_merges_wandb_runs(monkeypatch, tmp_path):
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()

    local_run = evals_dir / "20260308T101010.123456Z_baseline"
    local_run.mkdir()
    (local_run / "summary.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "duration_s": 1,
                "failed_thresholds_count": 0,
                "tracking": {
                    "wandb": {"project": "demo", "entity": "team", "run_url": "https://wandb/local"}
                },
            }
        ),
        encoding="utf-8",
    )
    (local_run / "retrieval_metrics.json").write_text(
        json.dumps(
            {
                "hit_rate_at_k": 0.5,
                "mrr": 0.4,
                "ndcg_at_k": 0.3,
                "latency_p50_ms": 10,
                "latency_p95_ms": 20,
            }
        ),
        encoding="utf-8",
    )
    (local_run / "manifest.json").write_text(
        json.dumps(
            {
                "experiment": {"index_config_hash": "idx-local"},
                "config": {"experiment_config": {"metadata": {"name": "baseline"}}},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(evaluation, "EVALS_DIR", evals_dir)
    monkeypatch.setattr(evaluation, "LATEST_POINTER", evals_dir / "latest_run.txt")
    monkeypatch.setattr(
        evaluation,
        "fetch_wandb_runs",
        lambda **kwargs: {
            "status": "ok",
            "project": "demo",
            "entity": "team",
            "runs": [
                {
                    "run_dir": "wandb-run",
                    "timestamp": "2026-03-08T11:00:00",
                    "status": "finished",
                    "duration_s": 2,
                    "failed_thresholds_count": 1,
                    "retrieval_metrics": {"hit_rate_at_k": 0.7, "mrr": 0.6, "latency_p50_ms": 8},
                    "source": "wandb",
                    "experiment_name": "baseline",
                    "variant_name": "chunk_small",
                    "index_config_hash": "idx-remote",
                    "wandb_url": "https://wandb/remote",
                    "wandb_run_id": "abc123",
                }
            ],
        },
    )

    history = evaluation.get_evaluation_history(limit=10, source="all")

    assert history["summary"]["total_runs"] == 2
    assert history["summary"]["sources"]["local"] == 1
    assert history["summary"]["sources"]["wandb"] == 1
    assert history["sources"]["wandb"]["project"] == "demo"
    assert any(run["source"] == "wandb" for run in history["runs"])


def test_get_wandb_evaluation_run_returns_remote_summary(monkeypatch):
    monkeypatch.setattr(
        evaluation,
        "fetch_wandb_run",
        lambda **kwargs: {
            "status": "ok",
            "run": {
                "run_dir": "remote-baseline",
                "duration_s": 12,
                "status": "finished",
                "failed_thresholds_count": 1,
                "retrieval_metrics": {"hit_rate_at_k": 0.8, "mrr": 0.7},
                "manifest": {"experiment": {"variant": "chunk_small"}},
                "tracking": {"wandb": {"run_id": "abc123", "run_url": "https://wandb/run/abc123"}},
                "wandb_run_id": "abc123",
                "wandb_url": "https://wandb/run/abc123",
                "summary": {"rag_metrics": {"status": "skipped"}},
            },
        },
    )

    response = evaluation.get_wandb_evaluation_run(
        "abc123",
        wandb_project="demo",
        wandb_entity="team",
    )

    assert response["source"] == "wandb"
    assert response["summary"]["status"] == "finished"
    assert response["wandb_run_id"] == "abc123"
    assert response["retrieval_metrics"]["mrr"] == 0.7
