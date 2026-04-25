import json
from dataclasses import asdict
from pathlib import Path

import pytest

from src.evals import pipeline_assessment as pa
from src.evals.artifacts import ArtifactStore, build_run_identity, to_serializable
from src.evals.schemas import AssessmentConfig

pytestmark = pytest.mark.smoke


def _fake_step(stage: str):
    return {
        "aggregate": {f"{stage}_ok": True},
        "records": [{"stage": stage}],
        "findings": [],
    }


def test_run_assessment_smoke(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pa, "audit_l0_download", lambda: _fake_step("l0"))
    monkeypatch.setattr(pa, "assess_l1_html_markdown_quality", lambda: _fake_step("l1"))
    monkeypatch.setattr(pa, "assess_l2_pdf_quality", lambda: _fake_step("l2"))
    monkeypatch.setattr(pa, "assess_l3_chunking_quality", lambda: _fake_step("l3"))
    monkeypatch.setattr(pa, "assess_l4_reference_quality", lambda: _fake_step("l4"))
    monkeypatch.setattr(pa, "assess_l5_index_quality", lambda: _fake_step("l5"))
    monkeypatch.setattr(
        pa,
        "build_retrieval_dataset",
        lambda **kwargs: {
            "dataset": [
                {
                    "query_id": "q1",
                    "query": "What is LDL target?",
                    "expected_keywords": ["LDL", "target"],
                    "expected_sources": ["lipid"],
                    "label_confidence": "high",
                    "dataset_origin": "test",
                }
            ],
            "generation_attempts": [{"status": "skipped", "reason": "test"}],
            "stats": {"fixture_records": 1, "synthetic_records": 0, "merged_records": 1},
        },
    )
    monkeypatch.setattr(
        pa,
        "evaluate_retrieval",
        lambda dataset, top_k: (
            [{"query_id": "q1", "metrics": {"hit_rate_at_k": 1.0}}],
            {
                "query_count": 1,
                "hit_rate_at_k": 1.0,
                "precision_at_k": 1.0,
                "recall_at_k": 1.0,
                "mrr": 1.0,
                "ndcg_at_k": 1.0,
                "source_hit_rate": 1.0,
                "latency_p50_ms": 10.0,
                "latency_p95_ms": 10.0,
                "hit_rate_at_k_high_conf": 1.0,
                "mrr_high_conf": 1.0,
            },
        ),
    )
    import src.evals.assessment.reporting as reporting

    monkeypatch.setattr(reporting, "git_head", lambda: "deadbeef")

    result = pa.run_assessment(
        artifact_dir=tmp_path / "evals",
        disable_llm_generation=True,
        disable_llm_judging=True,
        include_answer_eval=False,
        fail_on_thresholds=True,
    )

    assert result.status == "ok"
    assert (result.run_dir / "summary.md").exists()
    assert (result.run_dir / "retrieval_metrics.json").exists()
    assert (tmp_path / "evals" / "latest_run.txt").exists()


def test_artifact_store_uses_unique_run_dirs(tmp_path: Path):
    first = ArtifactStore(tmp_path / "evals", "same-name")
    second = ArtifactStore(tmp_path / "evals", "same-name")

    assert first.run_dir != second.run_dir


def test_run_assessment_reuses_matching_completed_run(monkeypatch, tmp_path: Path):
    call_counter = {"steps": 0}

    def fake_step(stage: str):
        def _inner():
            call_counter["steps"] += 1
            return {
                "aggregate": {f"{stage}_ok": True},
                "records": [{"stage": stage}],
                "findings": [],
            }

        return _inner

    monkeypatch.setattr(pa, "audit_l0_download", fake_step("l0"))
    monkeypatch.setattr(pa, "assess_l1_html_markdown_quality", fake_step("l1"))
    monkeypatch.setattr(pa, "assess_l2_pdf_quality", fake_step("l2"))
    monkeypatch.setattr(pa, "assess_l3_chunking_quality", fake_step("l3"))
    monkeypatch.setattr(pa, "assess_l4_reference_quality", fake_step("l4"))
    monkeypatch.setattr(pa, "assess_l5_index_quality", fake_step("l5"))
    monkeypatch.setattr(
        pa,
        "build_retrieval_dataset",
        lambda **kwargs: {
            "dataset": [],
            "generation_attempts": [],
            "stats": {"fixture_records": 0, "synthetic_records": 0, "merged_records": 0},
        },
    )
    monkeypatch.setattr(
        pa,
        "evaluate_retrieval",
        lambda dataset, top_k, retrieval_options=None: (
            [],
            {"query_count": 0, "hit_rate_at_k": 0.0, "mrr": 0.0, "ndcg_at_k": 0.0},
        ),
    )
    import src.evals.assessment.reporting as reporting

    monkeypatch.setattr(reporting, "git_head", lambda: "deadbeef")

    first = pa.run_assessment(
        artifact_dir=tmp_path / "evals",
        disable_llm_generation=True,
        disable_llm_judging=True,
        include_answer_eval=False,
    )
    assert call_counter["steps"] == 6

    def should_not_run():
        raise AssertionError("dedup should have reused the prior completed run")

    monkeypatch.setattr(pa, "audit_l0_download", should_not_run)
    monkeypatch.setattr(pa, "assess_l1_html_markdown_quality", should_not_run)
    monkeypatch.setattr(pa, "assess_l2_pdf_quality", should_not_run)
    monkeypatch.setattr(pa, "assess_l3_chunking_quality", should_not_run)
    monkeypatch.setattr(pa, "assess_l4_reference_quality", should_not_run)
    monkeypatch.setattr(pa, "assess_l5_index_quality", should_not_run)
    monkeypatch.setattr(pa, "build_retrieval_dataset", should_not_run)
    monkeypatch.setattr(pa, "evaluate_retrieval", should_not_run)

    second = pa.run_assessment(
        artifact_dir=tmp_path / "evals",
        disable_llm_generation=True,
        disable_llm_judging=True,
        include_answer_eval=False,
    )

    assert second.run_dir == first.run_dir
    assert second.summary["dedup"]["reused_existing_run"] is True


def test_run_assessment_ignores_incomplete_matching_run(monkeypatch, tmp_path: Path):
    config = AssessmentConfig(
        artifact_dir=tmp_path / "evals",
        disable_llm_generation=True,
        disable_llm_judging=True,
        include_answer_eval=False,
    )
    incomplete = tmp_path / "evals" / "20260317T000000.000000Z_incomplete"
    incomplete.mkdir(parents=True)
    (incomplete / "manifest.json").write_text(
        json.dumps(
            {
                "config": to_serializable(asdict(config)),
                "git_head": "deadbeef",
                "input_provenance": {
                    "dataset_file_sha256": None,
                    "download_manifest_sha256": None,
                    "raw_data_snapshot": {"exists": False, "entries": []},
                },
                "run_identity": build_run_identity(
                    config={
                        "assessment": to_serializable(asdict(config)),
                        "input_provenance": {
                            "dataset_file_sha256": None,
                            "download_manifest_sha256": None,
                            "raw_data_snapshot": {"exists": False, "entries": []},
                        },
                    },
                    git_head="deadbeef",
                ),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pa, "audit_l0_download", lambda: _fake_step("l0"))
    monkeypatch.setattr(pa, "assess_l1_html_markdown_quality", lambda: _fake_step("l1"))
    monkeypatch.setattr(pa, "assess_l2_pdf_quality", lambda: _fake_step("l2"))
    monkeypatch.setattr(pa, "assess_l3_chunking_quality", lambda: _fake_step("l3"))
    monkeypatch.setattr(pa, "assess_l4_reference_quality", lambda: _fake_step("l4"))
    monkeypatch.setattr(pa, "assess_l5_index_quality", lambda: _fake_step("l5"))
    monkeypatch.setattr(
        pa,
        "build_retrieval_dataset",
        lambda **kwargs: {
            "dataset": [],
            "generation_attempts": [],
            "stats": {"fixture_records": 0, "synthetic_records": 0, "merged_records": 0},
        },
    )
    monkeypatch.setattr(
        pa,
        "evaluate_retrieval",
        lambda dataset, top_k, retrieval_options=None: (
            [],
            {"query_count": 0, "hit_rate_at_k": 0.0, "mrr": 0.0, "ndcg_at_k": 0.0},
        ),
    )
    import src.evals.assessment.reporting as reporting

    monkeypatch.setattr(reporting, "git_head", lambda: "deadbeef")

    result = pa.run_assessment(
        artifact_dir=tmp_path / "evals",
        disable_llm_generation=True,
        disable_llm_judging=True,
        include_answer_eval=False,
    )

    assert result.run_dir != incomplete
    assert (result.run_dir / "summary.json").exists()


def test_run_assessment_dedup_invalidates_when_dataset_file_changes(monkeypatch, tmp_path: Path):
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        '{"golden_queries":[{"query":"Q1","expected_sources":["S1"]}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(pa, "audit_l0_download", lambda: _fake_step("l0"))
    monkeypatch.setattr(pa, "assess_l1_html_markdown_quality", lambda: _fake_step("l1"))
    monkeypatch.setattr(pa, "assess_l2_pdf_quality", lambda: _fake_step("l2"))
    monkeypatch.setattr(pa, "assess_l3_chunking_quality", lambda: _fake_step("l3"))
    monkeypatch.setattr(pa, "assess_l4_reference_quality", lambda: _fake_step("l4"))
    monkeypatch.setattr(pa, "assess_l5_index_quality", lambda: _fake_step("l5"))
    monkeypatch.setattr(
        pa,
        "build_retrieval_dataset",
        lambda **kwargs: {
            "dataset": [{"query": "Q1"}],
            "generation_attempts": [],
            "stats": {"fixture_records": 1, "synthetic_records": 0, "merged_records": 1},
        },
    )
    monkeypatch.setattr(
        pa,
        "evaluate_retrieval",
        lambda dataset, top_k, retrieval_options=None: (
            [],
            {"query_count": 1, "hit_rate_at_k": 0.0, "mrr": 0.0, "ndcg_at_k": 0.0},
        ),
    )
    import src.evals.assessment.reporting as reporting

    monkeypatch.setattr(reporting, "git_head", lambda: "deadbeef")

    first = pa.run_assessment(
        artifact_dir=tmp_path / "evals",
        dataset_path=dataset_path,
        disable_llm_generation=True,
        disable_llm_judging=True,
        include_answer_eval=False,
    )

    dataset_path.write_text(
        '{"golden_queries":[{"query":"Q2","expected_sources":["S2"]}]}',
        encoding="utf-8",
    )

    second = pa.run_assessment(
        artifact_dir=tmp_path / "evals",
        dataset_path=dataset_path,
        disable_llm_generation=True,
        disable_llm_judging=True,
        include_answer_eval=False,
    )

    assert second.run_dir != first.run_dir
