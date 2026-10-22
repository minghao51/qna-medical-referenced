"""Failed assessment attempts retain only safe, fail-closed usage diagnostics."""

import asyncio
import json

import pytest

import src.evals.assessment.orchestrator as orchestrator
from src.evals.assessment.orchestrator import AssessmentPipeline
from src.evals.schemas import AssessmentRunParams
from src.infra.usage import usage_call


def _pipeline(*, initialize_runtime_index_fn=None):
    def step(aggregate=None):
        return {"aggregate": aggregate or {}, "records": [], "findings": []}

    retrieval_metrics = {
        "query_count": 1,
        "exact_chunk_hit_rate_high_conf": 1.0,
        "evidence_hit_rate_high_conf": 1.0,
        "hit_rate_at_k_high_conf": 1.0,
        "mrr_high_conf": 1.0,
        "topic_false_positive_rate": 0.0,
        "duplicate_source_ratio_mean": 0.0,
    }
    return AssessmentPipeline(
        audit_l0_download_fn=lambda: step(),
        assess_l1_html_markdown_quality_fn=lambda: step({"markdown_empty_rate": 0.0}),
        assess_l2_pdf_quality_fn=lambda: step({"empty_page_rate": 0.0}),
        assess_l3_chunking_quality_fn=lambda: step({"duplicate_chunk_rate": 0.0}),
        assess_l4_reference_quality_fn=lambda: step(),
        assess_l5_index_quality_fn=lambda **kwargs: step({"embedding_dim_consistent": True}),
        build_retrieval_dataset_fn=lambda **kwargs: {
            "dataset": [{"query_id": "synthetic-1", "query": "synthetic question"}],
            "stats": {},
        },
        evaluate_retrieval_fn=lambda *args, **kwargs: ([], retrieval_metrics),
        git_head_fn=lambda: "synthetic-revision",
        configure_runtime_for_experiment_fn=lambda config: {
            "vector_store": {"collection_name": "synthetic"}
        },
        initialize_runtime_index_fn=initialize_runtime_index_fn
        or (lambda **kwargs: {"status": "ready"}),
        log_assessment_to_wandb_fn=lambda **kwargs: {"enabled": False},
        render_summary_fn=lambda **kwargs: "synthetic summary",
        sha256_file_fn=lambda path: None,
    )


def _reported_usage(role="embedder", total_tokens=11):
    with usage_call(role=role) as call:
        assert call is not None
        call.record_response(
            {
                "usage": {
                    "prompt_tokens": total_tokens - 3,
                    "completion_tokens": 3,
                    "total_tokens": total_tokens,
                }
            }
        )


def _failed_artifact(artifact_dir):
    run_dirs = [path for path in artifact_dir.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    return run_dir, json.loads((run_dir / "manifest.json").read_text())


def test_later_failure_persists_partial_usage_without_exception_details(tmp_path):
    pipeline = _pipeline()

    def fail_after_usage(*args, **kwargs):
        _reported_usage(total_tokens=11)
        raise RuntimeError("synthetic-private-provider-detail")

    pipeline.evaluate_retrieval_fn = fail_after_usage
    with pytest.raises(RuntimeError, match="synthetic-private-provider-detail"):
        pipeline.run(
            AssessmentRunParams(
                artifact_dir=tmp_path,
                name="failed-usage",
                skip_ingestion=True,
                disable_llm_generation=True,
                disable_llm_judging=True,
            )
        )

    run_dir, manifest = _failed_artifact(tmp_path)
    summary = json.loads((run_dir / "summary.json").read_text())
    usage = manifest["usage_summary"]
    assert manifest["execution_status"] == summary["execution_status"] == "failed"
    assert manifest["execution_id"] == summary["execution_id"] == usage["run_id"]
    assert usage["usage_by_role"]["embedder"]["total_tokens"] == 11
    assert usage["usage_status"] == usage["cash_status"] == usage["quota_status"] == "incomplete"
    assert usage["cash_actual_usd"] is None
    assert usage["cash_estimate_usd"] is None
    assert usage["quota_value_usd"] is None
    assert "assessment_attempt_failed" in usage["unknowns"]
    assert "synthetic-private-provider-detail" not in json.dumps([manifest, summary])


def test_index_preparation_failure_has_one_early_store_and_preserves_usage(tmp_path, monkeypatch):
    created = []
    original_store = orchestrator.ArtifactStore

    class CountedArtifactStore(original_store):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created.append(self)

    monkeypatch.setattr(orchestrator, "ArtifactStore", CountedArtifactStore)

    def fail_during_index_preparation(**kwargs):
        _reported_usage(total_tokens=19)
        raise RuntimeError("synthetic-index-failure")

    pipeline = _pipeline(initialize_runtime_index_fn=fail_during_index_preparation)
    with pytest.raises(RuntimeError, match="synthetic-index-failure"):
        pipeline.run(
            AssessmentRunParams(
                artifact_dir=tmp_path,
                name="index-failure",
                experiment_config={"embedding_index": {"rebuild_policy": "always"}},
                disable_llm_generation=True,
                disable_llm_judging=True,
            )
        )

    assert len(created) == 1
    run_dir, manifest = _failed_artifact(tmp_path)
    assert manifest["execution_id"] == created[0].execution_id
    assert (
        manifest["execution_id"]
        == json.loads((run_dir / "summary.json").read_text())["execution_id"]
    )
    assert manifest["usage_summary"]["usage_by_role"]["embedder"]["total_tokens"] == 19


def test_cancellation_remains_primary_while_failed_usage_is_written(tmp_path):
    pipeline = _pipeline()

    def cancel_after_usage(*args, **kwargs):
        _reported_usage(total_tokens=7)
        raise asyncio.CancelledError

    pipeline.evaluate_retrieval_fn = cancel_after_usage
    with pytest.raises(asyncio.CancelledError):
        pipeline.run(
            AssessmentRunParams(
                artifact_dir=tmp_path,
                name="cancelled-usage",
                skip_ingestion=True,
                disable_llm_generation=True,
                disable_llm_judging=True,
            )
        )

    run_dir, manifest = _failed_artifact(tmp_path)
    summary = json.loads((run_dir / "summary.json").read_text())
    assert manifest["execution_status"] == summary["execution_status"] == "cancelled"
    assert manifest["usage_summary"]["usage_by_role"]["embedder"]["total_tokens"] == 7
    assert "assessment_attempt_cancelled" in manifest["usage_summary"]["unknowns"]


def test_missing_usage_is_unknown_and_capture_resets_between_failed_runs(tmp_path):
    pipeline = _pipeline()
    attempts = 0

    def fail_each_time(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            _reported_usage(total_tokens=23)
        raise RuntimeError("synthetic-failure")

    pipeline.evaluate_retrieval_fn = fail_each_time
    params = AssessmentRunParams(
        artifact_dir=tmp_path,
        name="reset-usage",
        skip_ingestion=True,
        disable_llm_generation=True,
        disable_llm_judging=True,
    )
    for _ in range(2):
        with pytest.raises(RuntimeError, match="synthetic-failure"):
            pipeline.run(params)

    run_dirs = sorted(path for path in tmp_path.iterdir() if path.is_dir())
    assert len(run_dirs) == 2
    first, second = [
        json.loads((path / "manifest.json").read_text())["usage_summary"] for path in run_dirs
    ]
    assert first["run_id"] != second["run_id"]
    assert first["usage_by_role"]["embedder"]["total_tokens"] == 23
    assert second["usage_by_role"]["embedder"]["total_tokens"] is None
    assert second["usage_status"] == second["cash_status"] == second["quota_status"] == "incomplete"
    assert "embedder_usage_unknown" in second["unknowns"]


def test_invalid_review_manifest_fails_before_index_preparation(tmp_path):
    pipeline = _pipeline()
    index_calls = []
    pipeline.configure_runtime_for_experiment_fn = lambda config: index_calls.append(config) or {}
    manifest_path = tmp_path / "invalid-review.json"
    manifest_path.write_text("{}")
    artifact_dir = tmp_path / "artifacts"

    with pytest.raises(ValueError, match="Review manifest schema"):
        pipeline.run(
            AssessmentRunParams(
                artifact_dir=artifact_dir,
                review_manifest_path=manifest_path,
                dataset_path=tmp_path / "frozen-dataset.json",
            )
        )

    assert index_calls == []
    assert not artifact_dir.exists()
