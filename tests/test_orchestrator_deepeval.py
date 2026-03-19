"""Tests for DeepEval orchestrator integration."""

from src.evals.assessment.orchestrator import run_assessment


def test_deepeval_import_exists():
    """Test that DeepEval function is importable."""
    from src.evals.assessment.orchestrator import evaluate_answers_deepeval

    assert callable(evaluate_answers_deepeval)


def test_orchestrator_runs_l6_answer_quality_evaluator(tmp_path):
    """Test that the orchestrator executes the canonical L6 answer quality evaluator."""

    def fake_evaluate_answer_quality(
        dataset, top_k, cache_dir=None, retrieval_options=None, cache_namespace=None
    ):
        assert dataset == [{"query": "What is LDL-C?"}]
        assert top_k == 3
        assert cache_dir is not None
        assert retrieval_options is None or isinstance(retrieval_options, dict)
        assert isinstance(cache_namespace, dict)
        return (
            [{"query": "What is LDL-C?", "metrics": {"factual_accuracy": {"score": 1.0}}}],
            {"query_count": 1, "factual_accuracy": {"mean": 1.0, "count": 1}},
        )

    result = run_assessment(
        artifact_dir=tmp_path / "evals",
        top_k=3,
        include_answer_eval=True,
        disable_llm_judging=False,
        audit_l0_download_fn=lambda: {"aggregate": {}, "records": [], "findings": []},
        assess_l1_html_markdown_quality_fn=lambda: {"aggregate": {}, "records": [], "findings": []},
        assess_l2_pdf_quality_fn=lambda: {"aggregate": {}, "records": [], "findings": []},
        assess_l3_chunking_quality_fn=lambda: {"aggregate": {}, "records": [], "findings": []},
        assess_l4_reference_quality_fn=lambda: {"aggregate": {}, "records": [], "findings": []},
        assess_l5_index_quality_fn=lambda collection_name=None: {
            "aggregate": {},
            "records": [],
            "findings": [],
        },
        build_retrieval_dataset_fn=lambda **kwargs: {
            "dataset": [{"query": "What is LDL-C?"}],
            "generation_attempts": [],
            "stats": {},
        },
        evaluate_retrieval_fn=lambda dataset, top_k, retrieval_options=None: (
            [],
            {"query_count": 1},
        ),
        evaluate_answers_fn=fake_evaluate_answer_quality,
        evaluate_thresholds_fn=lambda step_metrics, retrieval_metrics, l6_answer_quality_metrics, thresholds: [],
        git_head_fn=lambda: "deadbeef",
        configure_runtime_for_experiment_fn=lambda config: {},
        initialize_runtime_index_fn=lambda **kwargs: {"status": "not_requested"},
        log_assessment_to_wandb_fn=lambda **kwargs: {"enabled": False, "status": "skipped"},
        run_retrieval_ablations_fn=lambda dataset, top_k, base_options=None: {},
        run_diversity_sweep_fn=lambda dataset, top_k, base_options=None, **kwargs: [],
        render_summary_fn=lambda **kwargs: "summary",
        sha256_file_fn=lambda path: None,
    )

    assert result.summary["l6_answer_quality_metrics"]["query_count"] == 1
    assert result.summary["l6_answer_quality_metrics"]["factual_accuracy"]["mean"] == 1.0
    assert (result.run_dir / "l6_answer_quality.jsonl").exists()
    assert (result.run_dir / "l6_answer_quality_metrics.json").exists()
    assert not (result.run_dir / "rag_results.jsonl").exists()
    assert not (result.run_dir / "rag_metrics.json").exists()
