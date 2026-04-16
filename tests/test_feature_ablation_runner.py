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
                "ndcg_at_k": 0.9,
                "exact_chunk_hit_rate": 0.2,
                "evidence_hit_rate": 0.1,
                "latency_p50_ms": 100,
            },
            "b": {
                "ndcg_at_k": 0.9,
                "exact_chunk_hit_rate": 0.3,
                "evidence_hit_rate": 0.0,
                "latency_p50_ms": 150,
            },
        }
    )

    assert winner_name == "b"
    assert winner_metrics["exact_chunk_hit_rate"] == 0.3


def test_run_feature_family_reconfigures_keyword_winner_for_answer_eval(tmp_path: Path):
    calls: list[dict] = []
    experiment = load_reference_experiment(
        "experiments/v1/comprehensive_ablation.yaml", "pymupdf_semantic_hybrid"
    )

    def fake_run_assessment(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            summary = {
                "keyword_ablations": {
                    "baseline": {"ndcg_at_k": 0.9, "exact_chunk_hit_rate": 0.2},
                    "keywords_only": {"ndcg_at_k": 0.95, "exact_chunk_hit_rate": 0.1},
                    "summaries_only": {"ndcg_at_k": 0.95, "exact_chunk_hit_rate": 0.25},
                    "both": {"ndcg_at_k": 0.94, "exact_chunk_hit_rate": 0.4},
                }
            }
            run_dir = tmp_path / "retrieval"
        else:
            summary = {"l6_answer_quality_metrics": {"status": "ok", "query_count": 7}}
            run_dir = tmp_path / "winner"
        run_dir.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(run_dir=run_dir, status="ok", failed_thresholds=[], summary=summary)

    result = run_feature_family(
        experiment,
        "keyword",
        include_answer_eval_for_winner=True,
        run_assessment_fn=fake_run_assessment,
    )

    assert result["winner_variant"] == "summaries_only"
    assert calls[0]["run_keyword_ablations"] is True
    assert calls[0]["include_answer_eval"] is False
    winner_experiment = calls[1]["experiment_config"]
    assert winner_experiment["ingestion"]["enable_keyword_extraction"] is False
    assert winner_experiment["ingestion"]["enable_chunk_summaries"] is True
    assert winner_experiment["embedding_index"]["rebuild_policy"] == "always"
    assert winner_experiment["embedding_index"]["collection_name"].endswith(
        "_summaries_only_answer"
    )
    assert calls[1]["include_answer_eval"] is True


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
    assert "not re-ranked across all variants" in rendered

    markdown_path, json_path = write_feature_ablation_outputs(summary, tmp_path)
    assert markdown_path.exists()
    assert json_path.exists()
    assert "Feature Ablation Summary" in markdown_path.read_text(encoding="utf-8")
