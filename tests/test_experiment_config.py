from pathlib import Path

import pytest

from src.experiments.config import (
    build_run_assessment_kwargs,
    load_experiment_file,
    resolve_experiment_runs,
)


def test_load_experiment_file_normalizes_defaults():
    config = load_experiment_file("experiments/v1/baseline.yaml")

    assert config["schema_version"] == 1
    assert config["metadata"]["name"] == "baseline"
    assert config["embedding_index"]["collection_name"] == "medical_docs_baseline"
    assert config["experiment_config_hash"]
    assert config["index_config_hash"]
    assert config["ingestion"]["source_chunk_configs"]["pdf"]["chunk_size"] == 650
    assert config["tracking"]["wandb"]["enabled"] is False
    assert config["tracking"]["wandb"]["project"] == "qna-medical-referenced"


def test_load_experiment_file_rejects_unknown_version(tmp_path: Path):
    config_file = tmp_path / "bad.yaml"
    config_file.write_text("schema_version: 99\nmetadata:\n  name: broken\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported experiment schema_version"):
        load_experiment_file(config_file)


def test_resolve_experiment_variants_includes_base_and_variant():
    runs = resolve_experiment_runs("experiments/v1/baseline.yaml", variant="chunk_small")

    assert len(runs) == 2
    assert runs[0]["variant_name"] is None
    assert runs[1]["variant_name"] == "chunk_small"
    assert runs[1]["ingestion"]["source_chunk_configs"]["pdf"]["chunk_size"] == 480


def test_build_run_assessment_kwargs_uses_experiment_values():
    config = load_experiment_file("experiments/v1/baseline.yaml")

    kwargs = build_run_assessment_kwargs(config)

    assert kwargs["artifact_dir"] == "data/evals"
    assert kwargs["dataset_split"] == "regression"
    assert kwargs["disable_llm_generation"] is True
    assert kwargs["retrieval_options"]["search_mode"] == "rrf_hybrid"
    assert kwargs["experiment_config"]["metadata"]["name"] == "baseline"
