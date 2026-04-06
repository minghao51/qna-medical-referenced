import json

from src.app.routes import evaluation


def _write_run(base_dir, name: str, *, variant: str, ndcg: float, mrr: float = 0.5) -> None:
    run_dir = base_dir / name
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "experiment": {"variant": variant},
                "index_preparation": {
                    "indexing_stats": {
                        "attempted": 10,
                        "inserted": 9,
                        "skipped_duplicate_content": 1,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "retrieval_metrics.json").write_text(
        json.dumps(
            {
                "ndcg_at_k": ndcg,
                "mrr": mrr,
                "hit_rate_at_k": 0.8,
                "precision_at_k": 0.7,
                "recall_at_k": 0.6,
                "latency_p50_ms": 12,
            }
        ),
        encoding="utf-8",
    )


def test_full_ablation_results_include_runs_from_20260404_onward(monkeypatch, tmp_path):
    ablation_dir = tmp_path / "evals_comprehensive_ablation"
    ablation_dir.mkdir()

    _write_run(ablation_dir, "20260403T235959Z_baseline", variant="baseline", ndcg=0.1)
    _write_run(ablation_dir, "20260404T000000Z_baseline", variant="baseline", ndcg=0.2)
    _write_run(ablation_dir, "20260405T000000Z_pdf_pymupdf", variant="pdf_pymupdf", ndcg=0.3)

    monkeypatch.setattr(evaluation, "Path", lambda _: ablation_dir)

    result = evaluation.get_full_ablation_results()

    assert [run["run_dir"] for run in result["runs"]] == [
        "20260405T000000Z_pdf_pymupdf",
        "20260404T000000Z_baseline",
    ]
    assert result["optimal_variant"] == "pdf_pymupdf"


def test_full_ablation_results_compute_delta_when_baseline_is_zero(monkeypatch, tmp_path):
    ablation_dir = tmp_path / "evals_comprehensive_ablation"
    ablation_dir.mkdir()

    _write_run(ablation_dir, "20260404T000000Z_baseline", variant="baseline", ndcg=0.0)
    _write_run(
        ablation_dir,
        "20260405T000000Z_retrieval_semantic_only",
        variant="retrieval_semantic_only",
        ndcg=0.25,
    )

    monkeypatch.setattr(evaluation, "Path", lambda _: ablation_dir)

    result = evaluation.get_full_ablation_results()
    runs_by_variant = {run["variant"]: run for run in result["runs"]}

    assert runs_by_variant["baseline"]["delta_ndcg"] == 0.0
    assert runs_by_variant["retrieval_semantic_only"]["delta_ndcg"] == 0.25
