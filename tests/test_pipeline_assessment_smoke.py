from pathlib import Path

from src.evals import pipeline_assessment as pa


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
        "_evaluate_retrieval",
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
    monkeypatch.setattr(
        pa,
        "_evaluate_answers",
        lambda dataset, top_k: ([], {"status": "skipped", "reason": "test"}),
    )
    monkeypatch.setattr(pa, "_git_head", lambda: "deadbeef")

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
