from pathlib import Path
from types import SimpleNamespace

import pytest

from src.cli import eval_pipeline


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

    monkeypatch.setattr(eval_pipeline, "run_assessment", fake_run_assessment)
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
    assert len(calls) == 2
    assert calls[0]["experiment_config"]["metadata"]["name"] == "baseline"
    assert calls[1]["experiment_config"]["variant_name"] == "chunk_small"
    assert (
        calls[1]["experiment_config"]["ingestion"]["source_chunk_configs"]["pdf"]["chunk_size"]
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

    monkeypatch.setattr(eval_pipeline, "run_assessment", fake_run_assessment)
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
    assert len(calls) == 2
    assert all(call["top_k"] == 7 for call in calls)
    assert all(call["name"] == "override-name" for call in calls)
