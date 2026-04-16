"""Tests for DeepEval orchestrator integration."""

from src.evals.assessment.orchestrator import run_assessment


def test_deepeval_import_exists():
    """Test that DeepEval function is importable."""
    from src.evals.assessment.orchestrator import evaluate_answer_quality

    assert callable(evaluate_answer_quality)


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


def test_orchestrator_uses_keyword_reingest_when_experiment_config_present(tmp_path):
    rebuild_calls: list[tuple[dict, str]] = []

    def fake_run_keyword_ablations_with_reingest(
        dataset,
        top_k,
        *,
        base_options=None,
        base_collection_name=None,
        reconfigure_and_rebuild_fn=None,
    ):
        reconfigure_and_rebuild_fn(
            enrichment_config={
                "enable_keyword_extraction": True,
                "enable_chunk_summaries": False,
                "keyword_extraction_sample_rate": 1.0,
                "keyword_extraction_max_chunks": 50,
            },
            collection_name=f"{base_collection_name}_keywords_only",
        )
        return {"keywords_only": {"ndcg_at_k": 0.95}}

    def fake_configure_runtime_for_experiment(config):
        rebuild_calls.append((config["ingestion"], config["embedding_index"]["collection_name"]))
        return {"vector_store": {"collection_name": config["embedding_index"]["collection_name"]}}

    result = run_assessment(
        artifact_dir=tmp_path / "evals",
        top_k=3,
        include_answer_eval=False,
        disable_llm_judging=True,
        run_keyword_ablations=True,
        experiment_config={
            "metadata": {"name": "exp"},
            "embedding_index": {
                "collection_name": "medical_docs_base",
                "rebuild_policy": "always",
                "materialize_html": True,
            },
            "ingestion": {},
            "retrieval": {"search_mode": "rrf_hybrid"},
        },
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
        evaluate_thresholds_fn=lambda step_metrics, retrieval_metrics, l6_answer_quality_metrics, thresholds: [],
        git_head_fn=lambda: "deadbeef",
        configure_runtime_for_experiment_fn=fake_configure_runtime_for_experiment,
        initialize_runtime_index_fn=lambda **kwargs: {"status": "rebuilt", **kwargs},
        log_assessment_to_wandb_fn=lambda **kwargs: {"enabled": False, "status": "skipped"},
        run_retrieval_ablations_fn=lambda dataset, top_k, base_options=None: {},
        run_keyword_ablations_with_reingest_fn=fake_run_keyword_ablations_with_reingest,
        render_summary_fn=lambda **kwargs: "summary",
        sha256_file_fn=lambda path: None,
    )

    assert result.summary["keyword_ablations"]["keywords_only"]["ndcg_at_k"] == 0.95
    assert rebuild_calls[-1][0]["enable_keyword_extraction"] is True
    assert rebuild_calls[-1][0]["enable_chunk_summaries"] is False
    assert rebuild_calls[-1][1] == "medical_docs_base_keywords_only"
