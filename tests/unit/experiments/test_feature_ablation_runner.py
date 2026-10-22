from pathlib import Path
from types import SimpleNamespace

from src.experiments.feature_ablation_runner import (
    load_reference_experiment,
    render_feature_ablation_summary,
    run_feature_family,
    select_best_variant,
    write_feature_ablation_outputs,
)


def test_select_best_variant_uses_tie_breakers():
    winner_name, winner_metrics = select_best_variant(
        {
            "a": {
                "query_count": 7,
                "ndcg_at_k": 0.9,
                "exact_chunk_hit_rate": 0.2,
                "evidence_hit_rate": 0.1,
                "latency_p50_ms": 100,
                "identity_status": "verified",
                "measurement_contract_version": 1,
                "status": "ok",
                "execution_status": "completed",
                "measurement_status": "complete",
                "quality_gate": "passed",
            },
            "b": {
                "query_count": 7,
                "ndcg_at_k": 0.9,
                "exact_chunk_hit_rate": 0.3,
                "evidence_hit_rate": 0.0,
                "latency_p50_ms": 150,
                "identity_status": "verified",
                "measurement_contract_version": 1,
                "status": "ok",
                "execution_status": "completed",
                "measurement_status": "complete",
                "quality_gate": "passed",
            },
        }
    )

    assert winner_name == "b"
    assert winner_metrics["exact_chunk_hit_rate"] == 0.3


def test_run_feature_family_runs_each_keyword_variant_in_isolation(tmp_path: Path):
    calls: list[dict] = []
    experiment = load_reference_experiment(
        "experiments/v1/comprehensive_ablation.yaml", "pymupdf_semantic_hybrid"
    )

    def fake_run_assessment(**kwargs):
        calls.append(kwargs)
        run_dir = tmp_path / f"run-{len(calls)}"
        run_dir.mkdir(parents=True, exist_ok=True)
        ndcg = [0.9, 0.95, 0.95, 0.94][len(calls) - 1]
        exact = [0.2, 0.1, 0.25, 0.4][len(calls) - 1]
        summary = {
            "measurement_contract_version": 1,
            "execution_status": "completed",
            "measurement": {"status": "complete"},
            "quality_gate": "passed",
            "status": "ok",
            "identity": {"status": "verified"},
            "retrieval_metrics": {
                "query_count": 7,
                "ndcg_at_k": ndcg,
                "exact_chunk_hit_rate": exact,
                "evidence_hit_rate": 0.2,
                "latency_p50_ms": 10,
            },
        }
        return SimpleNamespace(run_dir=run_dir, status="ok", summary=summary)

    result = run_feature_family(
        experiment,
        "keyword",
        include_answer_eval_for_winner=True,
        run_assessment_fn=fake_run_assessment,
    )

    assert result["winner_variant"] == "summaries_only"
    assert len(calls) == 4
    assert all(call["run_keyword_ablations"] is False for call in calls)
    assert all(call["include_answer_eval"] is False for call in calls)
    assert all(call["skip_ingestion"] is False for call in calls)
    assert (
        len({call["experiment_config"]["embedding_index"]["collection_name"] for call in calls})
        == 4
    )
    winner_experiment = calls[2]["experiment_config"]
    assert winner_experiment["ingestion"]["enable_keyword_extraction"] is False
    assert winner_experiment["ingestion"]["enable_chunk_summaries"] is True
    assert result["answer_eval_status"].startswith("blocked")


def test_render_and_write_feature_ablation_summary(tmp_path: Path):
    summary = {
        "config_path": "experiments/v1/comprehensive_ablation.yaml",
        "reference_variant": "pymupdf_semantic_hybrid",
        "studies": [
            {
                "family": "reranking",
                "retrieval_run_dir": "data/evals_reranking_ablation/run-1",
                "winner_variant": "both_reranking",
                "baseline_variant": "no_reranking",
                "winner_metrics": {
                    "ndcg_at_k": 0.9,
                    "mrr": 0.8,
                    "exact_chunk_hit_rate": 0.7,
                    "evidence_hit_rate": 0.6,
                    "latency_p50_ms": 50,
                },
                "baseline_metrics": {
                    "ndcg_at_k": 0.8,
                    "mrr": 0.7,
                    "exact_chunk_hit_rate": 0.6,
                    "evidence_hit_rate": 0.5,
                    "latency_p50_ms": 40,
                },
                "winner_answer_eval_run_dir": "data/evals_reranking_ablation/run-2",
                "winner_answer_eval_metrics": {"status": "ok"},
            }
        ],
    }

    rendered = render_feature_ablation_summary(summary)
    assert "both_reranking" in rendered
    assert "not promotion" in rendered

    markdown_path, json_path = write_feature_ablation_outputs(summary, tmp_path)
    assert markdown_path.exists()
    assert json_path.exists()
    assert "Feature Ablation Summary" in markdown_path.read_text(encoding="utf-8")
