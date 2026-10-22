import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.cli import eval_pipeline


@pytest.mark.parametrize("mode", ["direct", "config", "parallel"])
@pytest.mark.parametrize("strict", [False, True])
def test_incomplete_measurement_has_nonzero_strict_cli_exit(monkeypatch, tmp_path, mode, strict):
    from src.experiments.config import _base_defaults

    result = SimpleNamespace(
        run_dir=tmp_path,
        status="incomplete",
        failed_thresholds=[],
        summary={"measurement": {"status": "incomplete"}},
    )
    monkeypatch.setattr(eval_pipeline, "run_assessment", lambda **kwargs: result)
    monkeypatch.setattr(eval_pipeline, "run_assessment_in_subprocess", lambda kwargs: result)
    argv = ["eval_pipeline", "--include-answer-eval"]
    if strict:
        argv.append("--fail-on-thresholds")
    if mode != "direct":
        specs = [_base_defaults()] * (2 if mode == "parallel" else 1)
        monkeypatch.setattr(eval_pipeline, "resolve_experiment_runs", lambda *args, **kwargs: specs)
        argv.extend(["--config=synthetic.yaml", "--all-variants"])
    if mode == "parallel":
        argv.append("--parallel")
        monkeypatch.setattr(
            eval_pipeline,
            "_run_variants_parallel",
            lambda *args, **kwargs: [
                (
                    i,
                    {
                        "run_dir": None,
                        "status": "incomplete",
                        "failed_thresholds": [],
                        "summary": result.summary,
                    },
                )
                for i in range(2)
            ],
        )
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit) as exc:
        eval_pipeline.main()
    assert exc.value.code == (1 if strict else 0)


def test_eval_pipeline_cli_uses_config(monkeypatch, tmp_path: Path):
    calls: list[dict] = []

    def fake_run_assessment(**kwargs):
        calls.append(kwargs)
        run_dir = tmp_path / kwargs["name"]
        run_dir.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(
            run_dir=run_dir,
            status="ok",
            failed_thresholds=[],
            summary={"retrieval_metrics": {"mrr": 0.5}},
        )

    monkeypatch.setattr(
        eval_pipeline,
        "run_assessment_in_subprocess",
        lambda kwargs: fake_run_assessment(**kwargs),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "eval_pipeline",
            "--config",
            "experiments/v1/baseline.yaml",
            "--variant",
            "chunk_small",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        eval_pipeline.main()

    assert exc.value.code == 0
    assert len(calls) == 1
    assert calls[0]["experiment_config"]["variant_name"] == "chunk_small"
    assert (
        calls[0]["experiment_config"]["ingestion"]["source_chunk_configs"]["pdf"]["chunk_size"]
        == 480
    )


def test_eval_pipeline_cli_applies_equals_style_overrides(monkeypatch, tmp_path: Path):
    calls: list[dict] = []

    def fake_run_assessment(**kwargs):
        calls.append(kwargs)
        run_dir = tmp_path / kwargs["name"]
        run_dir.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(
            run_dir=run_dir,
            status="ok",
            failed_thresholds=[],
            summary={"retrieval_metrics": {"mrr": 0.5}},
        )

    monkeypatch.setattr(
        eval_pipeline,
        "run_assessment_in_subprocess",
        lambda kwargs: fake_run_assessment(**kwargs),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "eval_pipeline",
            "--config=experiments/v1/baseline.yaml",
            "--variant=chunk_small",
            "--top-k=7",
            "--name=override-name",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        eval_pipeline.main()

    assert exc.value.code == 0
    assert len(calls) == 1
    assert all(call["top_k"] == 7 for call in calls)
    assert all(call["name"] == "override-name" for call in calls)


def test_eval_pipeline_cli_passes_sampling_flags(monkeypatch, tmp_path: Path):
    calls: list[dict] = []

    def fake_run_assessment(**kwargs):
        calls.append(kwargs)
        run_dir = tmp_path / "sampled"
        run_dir.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(
            run_dir=run_dir,
            status="ok",
            failed_thresholds=[],
            summary={"retrieval_metrics": {"mrr": 0.5}},
        )

    monkeypatch.setattr(eval_pipeline, "run_assessment", fake_run_assessment)
    monkeypatch.setattr(
        "sys.argv",
        [
            "eval_pipeline",
            "--dataset-path=/tmp/sample.json",
            "--disable-llm-generation",
            "--max-queries=3",
            "--sample-seed=99",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        eval_pipeline.main()

    assert exc.value.code == 0
    assert calls[0]["max_queries"] == 3
    assert calls[0]["sample_seed"] == 99


def test_eval_pipeline_cli_passes_force_rerun_and_prints_dedup_status(
    monkeypatch, tmp_path: Path, capsys
):
    calls: list[dict] = []

    def fake_run_assessment(**kwargs):
        calls.append(kwargs)
        run_dir = tmp_path / "forced"
        run_dir.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(
            run_dir=run_dir,
            status="ok",
            failed_thresholds=[],
            summary={"retrieval_metrics": {"mrr": 0.5}, "dedup": {"force_rerun": True}},
        )

    monkeypatch.setattr(eval_pipeline, "run_assessment", fake_run_assessment)
    monkeypatch.setattr("sys.argv", ["eval_pipeline", "--force-rerun"])

    with pytest.raises(SystemExit) as exc:
        eval_pipeline.main()

    assert exc.value.code == 0
    assert calls[0]["force_rerun"] is True
    stdout = capsys.readouterr().out
    assert "Dedup bypassed: force rerun" in stdout


@pytest.mark.parametrize(
    ("flags", "mode", "rerank", "reranking_mode", "top_k"),
    [
        ([], "bm25_only", False, "mmr", 2),
        (["--enable-reranking"], "bm25_only", True, "mmr", 2),
        (["--reranking-mode=both"], "bm25_only", False, "both", 2),
        (["--mmr-lambda=0"], "bm25_only", False, "mmr", 2),
        (["--no-diversification"], "bm25_only", False, "mmr", 2),
        (["--search-mode=semantic_only"], "semantic_only", False, "mmr", 2),
        (["--retrieval-mode=rrf_hybrid"], "rrf_hybrid", False, "mmr", 2),
        (["--top-k=3"], "bm25_only", False, "mmr", 3),
        (["--disable-bm25"], "semantic_only", False, "mmr", 2),
        (
            ["--search-mode=semantic_only", "--retrieval-mode=rrf_hybrid"],
            "rrf_hybrid",
            False,
            "mmr",
            2,
        ),
    ],
)
def test_cli_only_explicit_retrieval_flags_override_experiment(
    monkeypatch, tmp_path, flags, mode, rerank, reranking_mode, top_k
):
    from src.experiments.config import _base_defaults

    experiment = _base_defaults()
    experiment["retrieval"].update(
        {
            "search_mode": "bm25_only",
            "top_k": 2,
            "enable_reranking": False,
            "reranking_mode": "mmr",
        }
    )
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(run_dir=tmp_path, status="ok", failed_thresholds=[], summary={})

    monkeypatch.setattr(
        eval_pipeline, "resolve_experiment_runs", lambda *args, **kwargs: [experiment]
    )
    monkeypatch.setattr(eval_pipeline, "run_assessment_in_subprocess", lambda kwargs: run(**kwargs))
    monkeypatch.setattr("sys.argv", ["eval_pipeline", "--config=synthetic.yaml", *flags])
    with pytest.raises(SystemExit) as exc:
        eval_pipeline.main()
    assert exc.value.code == 0
    assert len(calls) == 1
    options = calls[0]["retrieval_options"]
    assert options["search_mode"] == calls[0]["retrieval_mode"] == mode
    assert options["enable_reranking"] is rerank
    assert options["reranking_mode"] == reranking_mode
    assert options["top_k"] == calls[0]["top_k"] == top_k
    assert calls[0]["disable_bm25"] is (mode == "semantic_only")
    if "--mmr-lambda=0" in flags:
        assert options["mmr_lambda"] == 0.0
    if "--no-diversification" in flags:
        assert options["enable_diversification"] is False


def test_eval_pipeline_cli_passes_explicit_replay_mode(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        eval_pipeline,
        "run_assessment",
        lambda **kwargs: (
            calls.append(kwargs)
            or SimpleNamespace(run_dir=tmp_path, status="ok", failed_thresholds=[], summary={})
        ),
    )
    monkeypatch.setattr("sys.argv", ["eval_pipeline", "--execution-mode=replay"])

    with pytest.raises(SystemExit) as exc:
        eval_pipeline.main()

    assert exc.value.code == 0
    assert calls[0]["execution_mode"] == "replay"
    assert calls[0]["generation_implementation"] == "existing"
    assert calls[0]["harness"] == "deterministic_rag"


def test_eval_pipeline_cli_rejects_unknown_config_selection_axis(monkeypatch):
    from src.experiments.config import _base_defaults

    experiment = _base_defaults()
    experiment["harness"] = "unsupported_harness"
    monkeypatch.setattr(
        eval_pipeline, "resolve_experiment_runs", lambda *args, **kwargs: [experiment]
    )
    monkeypatch.setattr("sys.argv", ["eval_pipeline", "--config=synthetic.yaml"])

    with pytest.raises(ValueError, match="Unsupported evaluation harness"):
        eval_pipeline.main()


def test_usage_summary_cli_is_offline_and_does_not_run_assessment(monkeypatch, tmp_path, capsys):
    summary_path = tmp_path / "usage.json"
    summary_path.write_text(
        '{"run_id":"unknown-run","utc_month":"2026-10",'
        '"recorded_at":"2026-10-01T00:00:00+00:00","status":"incomplete",'
        '"cash_actual_usd":null,"cash_estimate_usd":null}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        eval_pipeline,
        "run_assessment",
        lambda **kwargs: pytest.fail("usage diagnostics must not run an assessment"),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "eval_pipeline",
            "--usage-summary",
            str(summary_path),
            "--usage-month",
            "2026-10",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        eval_pipeline.main()

    assert exc.value.code == 0
    assert '"allowed": false' in capsys.readouterr().out


def test_benchmark_budget_gate_blocks_at_recorded_ceiling(monkeypatch, tmp_path, capsys):
    from src.evals.usage import build_usage_summary

    summary_path = tmp_path / "usage.json"
    record = build_usage_summary(
        "paid-run",
        usage_by_role={"generator": {"total_tokens": 1}},
        cash_actual_usd=20,
        recorded_at=datetime.fromisoformat("2026-10-01T00:00:00+00:00"),
    )
    summary_path.write_text(json.dumps([record]), encoding="utf-8")
    monkeypatch.setattr(
        eval_pipeline,
        "run_assessment",
        lambda **kwargs: pytest.fail("blocked benchmark must not run an assessment"),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "eval_pipeline",
            "--execution-mode=benchmark",
            "--usage-summary",
            str(summary_path),
            "--usage-month=2026-10",
            "--confirm-overage-off",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        eval_pipeline.main()

    assert exc.value.code == 2
    assert "recorded_monthly_cash_ceiling_reached" in capsys.readouterr().out


def test_eval_pipeline_cli_rejects_benchmark_without_snapshot_support(monkeypatch):
    monkeypatch.setattr("sys.argv", ["eval_pipeline", "--execution-mode=benchmark"])

    with pytest.raises(SystemExit) as exc:
        eval_pipeline.main()

    assert exc.value.code == 2
