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
                    "dedup": {"reused_existing_run": idx == 1},
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "retrieval_metrics.json").write_text(
            json.dumps(
                {
                    "query_count": idx,
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
    assert history["runs"][0]["dedup"]["reused_existing_run"] is True
    assert runs[0]["dedup"]["reused_existing_run"] is True
    assert runs[0]["run_dir"] == newer.name


def test_evaluation_history_returns_local_runs_only(monkeypatch, tmp_path):
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
                "tracking": {"wandb": {"run_url": "https://wandb/local"}},
            }
        ),
        encoding="utf-8",
    )
    (local_run / "retrieval_metrics.json").write_text(
        json.dumps(
            {
                "query_count": 1,
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

    history = evaluation.get_evaluation_history(limit=10)

    assert history["summary"]["total_runs"] == 1
    assert history["summary"]["sources"]["local"] == 1
    assert history["sources"]["mode"] == "local"
    assert history["runs"][0]["wandb_url"] == "https://wandb/local"


def test_evaluation_history_excludes_incomplete_and_zero_query_runs(monkeypatch, tmp_path):
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()

    manifest_only = evals_dir / "20260308T121010.123456Z_manifest-only"
    manifest_only.mkdir()
    (manifest_only / "manifest.json").write_text(json.dumps({"config": {}}), encoding="utf-8")

    missing_retrieval = evals_dir / "20260308T111010.123456Z_missing-retrieval"
    missing_retrieval.mkdir()
    (missing_retrieval / "summary.json").write_text(
        json.dumps({"status": "ok", "duration_s": 1, "failed_thresholds_count": 0}),
        encoding="utf-8",
    )

    zero_query = evals_dir / "20260308T101010.123456Z_zero-query"
    zero_query.mkdir()
    (zero_query / "summary.json").write_text(
        json.dumps({"status": "ok", "duration_s": 1, "failed_thresholds_count": 0}),
        encoding="utf-8",
    )
    (zero_query / "retrieval_metrics.json").write_text(
        json.dumps({"query_count": 0, "hit_rate_at_k": 0.0, "mrr": 0.0}),
        encoding="utf-8",
    )

    valid = evals_dir / "20260308T091010.123456Z_valid"
    valid.mkdir()
    (valid / "summary.json").write_text(
        json.dumps({"status": "ok", "duration_s": 2, "failed_thresholds_count": 0}),
        encoding="utf-8",
    )
    (valid / "retrieval_metrics.json").write_text(
        json.dumps(
            {
                "query_count": 2,
                "hit_rate_at_k": 0.5,
                "mrr": 0.4,
                "ndcg_at_k": 0.3,
                "latency_p50_ms": 10,
                "latency_p95_ms": 20,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(evaluation, "EVALS_DIR", evals_dir)
    monkeypatch.setattr(evaluation, "LATEST_POINTER", evals_dir / "latest_run.txt")

    history = evaluation.get_evaluation_history(limit=10)
    runs = evaluation.get_evaluation_runs()

    assert [run["run_dir"] for run in history["runs"]] == [valid.name]
    assert [run["run_dir"] for run in runs] == [valid.name]


def test_get_latest_evaluation_skips_incomplete_newest_run(monkeypatch, tmp_path):
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()

    newest_invalid = evals_dir / "20260308T111010.123456Z_invalid"
    newest_invalid.mkdir()
    (newest_invalid / "manifest.json").write_text(json.dumps({"config": {}}), encoding="utf-8")

    valid = evals_dir / "20260308T101010.123456Z_valid"
    valid.mkdir()
    (valid / "summary.json").write_text(
        json.dumps({"status": "ok", "duration_s": 2, "failed_thresholds_count": 0}),
        encoding="utf-8",
    )
    (valid / "retrieval_metrics.json").write_text(
        json.dumps(
            {
                "query_count": 1,
                "hit_rate_at_k": 0.75,
                "mrr": 0.5,
                "ndcg_at_k": 0.6,
                "latency_p50_ms": 12,
                "latency_p95_ms": 25,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(evaluation, "EVALS_DIR", evals_dir)
    monkeypatch.setattr(evaluation, "LATEST_POINTER", evals_dir / "latest_run.txt")

    latest = evaluation.get_latest_evaluation()

    assert latest["run_dir"] == valid.name
    assert latest["retrieval_metrics"]["hit_rate_at_k"] == 0.75
