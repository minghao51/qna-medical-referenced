import json
from pathlib import Path

from src.evals import pipeline_assessment as pa
from src.experiments.config import load_experiment_file, resolve_experiment_runs


def _fake_step(stage: str, vector_path: str | None = None):
    aggregate = {f"{stage}_ok": True}
    if stage == "l3":
        aggregate.update({"chunk_size_config": 650, "chunk_overlap_config": 80})
    if stage == "l5":
        aggregate.update(
            {
                "vector_path": vector_path,
                "source_distribution": {"demo.pdf": 2},
                "dedupe_effect_estimate": 0,
                "embedding_dim": 2048,
            }
        )
    return {"aggregate": aggregate, "records": [{"stage": stage}], "findings": []}


def test_run_assessment_writes_experiment_provenance(monkeypatch, tmp_path: Path):
    vector_path = tmp_path / "vectors" / "medical_docs_baseline.json"
    vector_path.parent.mkdir(parents=True, exist_ok=True)
    vector_path.write_text(
        json.dumps(
            {
                "ids": [],
                "contents": [],
                "embeddings": [],
                "metadatas": [],
                "content_hashes": [],
                "index_metadata": {
                    "collection_name": "medical_docs_baseline",
                    "index_config_hash": "idx-123",
                    "embedding_model": "text-embedding-v4",
                    "embedding_batch_size": 10,
                    "semantic_weight": 0.6,
                    "keyword_weight": 0.2,
                    "boost_weight": 0.2,
                    "page_classification_enabled": True,
                    "index_only_classified_pages": True,
                    "html_extractor_mode": "auto",
                    "structured_chunking_enabled": True,
                    "source_chunk_configs": {"pdf": {"chunk_size": 650}},
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(pa, "audit_l0_download", lambda: _fake_step("l0"))
    monkeypatch.setattr(pa, "assess_l1_html_markdown_quality", lambda: _fake_step("l1"))
    monkeypatch.setattr(pa, "assess_l2_pdf_quality", lambda: _fake_step("l2"))
    monkeypatch.setattr(pa, "assess_l3_chunking_quality", lambda: _fake_step("l3"))
    monkeypatch.setattr(pa, "assess_l4_reference_quality", lambda: _fake_step("l4"))
    monkeypatch.setattr(
        pa,
        "assess_l5_index_quality",
        lambda **kwargs: _fake_step("l5", vector_path=str(vector_path)),
    )
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
        "_evaluate_retrieval",
        lambda dataset, top_k, retrieval_options=None: (
            [],
            {
                "query_count": 0,
                "hit_rate_at_k": 0.0,
                "precision_at_k": 0.0,
                "recall_at_k": 0.0,
                "mrr": 0.0,
                "ndcg_at_k": 0.0,
                "source_hit_rate": 0.0,
                "latency_p50_ms": 0.0,
                "latency_p95_ms": 0.0,
                "query_embedding_latency_p50_ms": 0.0,
                "query_embedding_latency_p95_ms": 0.0,
                "hit_rate_at_k_high_conf": 0.0,
                "mrr_high_conf": 0.0,
                "retrieval_options": retrieval_options or {},
            },
        ),
    )
    monkeypatch.setattr(pa, "_git_head", lambda: "deadbeef")
    monkeypatch.setattr(
        pa,
        "configure_runtime_for_experiment",
        lambda experiment: {
            "vector_store": {"collection_name": "medical_docs_baseline"},
        },
    )
    monkeypatch.setattr(
        pa,
        "initialize_runtime_index",
        lambda **kwargs: {"status": "ready", "indexing_stats": {"text_count": 0}},
    )
    monkeypatch.setattr(
        pa,
        "log_assessment_to_wandb",
        lambda **kwargs: {
            "enabled": True,
            "status": "logged",
            "project": "demo",
            "run_id": "wandb-123",
        },
    )

    config = load_experiment_file("experiments/v1/baseline.yaml")
    result = pa.run_assessment(
        artifact_dir=tmp_path / "evals",
        disable_llm_generation=True,
        disable_llm_judging=True,
        include_answer_eval=False,
        experiment_config=config,
    )

    manifest = json.loads((result.run_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((result.run_dir / "summary.json").read_text(encoding="utf-8"))
    assert manifest["experiment"]["file"].endswith("experiments/v1/baseline.yaml")
    assert manifest["experiment"]["config_hash"] == config["experiment_config_hash"]
    assert manifest["index_provenance"]["embedding_model"] == "text-embedding-v4"
    assert manifest["index_provenance"]["observed_embedding_dim"] == 2048
    assert manifest["checksums"]["vector_file_sha256"]
    assert manifest["tracking"]["wandb"]["run_id"] == "wandb-123"
    assert summary["tracking"]["wandb"]["status"] == "logged"


def test_variant_index_hash_changes_for_index_affecting_settings():
    runs = resolve_experiment_runs("experiments/v1/baseline.yaml", variant="chunk_small")

    assert runs[0]["index_config_hash"] != runs[1]["index_config_hash"]
