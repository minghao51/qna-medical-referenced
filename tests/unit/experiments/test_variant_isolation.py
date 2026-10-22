import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.experiments import feature_addition_runner as addition_runner
from src.experiments.addition_config import ExperimentConfig, ExperimentVariant


def test_each_variant_uses_a_fresh_process_and_private_writable_paths(monkeypatch):
    calls = []

    def fake_subprocess(command, **kwargs):
        response_path = Path(command[command.index("--_assessment-worker-result") + 1])
        request = json.loads(kwargs["input"])
        calls.append((request, kwargs["env"]))
        response_path.write_text(
            json.dumps(
                {
                    "run_dir": "/synthetic/run",
                    "status": "ok",
                    "failed_thresholds": [],
                    "summary": {"identity": {"status": "unverified"}},
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(addition_runner.subprocess, "run", fake_subprocess)
    for _ in range(2):
        result = addition_runner.run_assessment_in_subprocess(
            {"name": "synthetic", "execution_mode": "diagnostic"}
        )
        assert result.status == "ok"

    index_paths = [env["APP__STORAGE__CHROMA_PERSIST_DIRECTORY"] for _, env in calls]
    cache_paths = [env["APP__DEEPEVAL__DEEPEVAL_CACHE_DIR"] for _, env in calls]
    assert len(set(index_paths)) == 2
    assert len(set(cache_paths)) == 2
    assert all(env["APP__STORAGE__CHROMA_SERVER_HOST"] == "" for _, env in calls)
    assert all(request["execution_mode"] == "diagnostic" for request, _ in calls)
    assert all(request["generation_implementation"] == "existing" for request, _ in calls)
    assert all(request["harness"] == "deterministic_rag" for request, _ in calls)


def test_feature_addition_variants_do_not_reuse_strategy_only_index(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls = []

    def fake_isolated_assessment(kwargs):
        calls.append(kwargs)
        run_dir = tmp_path / "runs" / str(len(calls))
        run_dir.mkdir(parents=True)
        return SimpleNamespace(
            run_dir=run_dir,
            status="ok",
            summary={
                "measurement_contract_version": 1,
                "status": "ok",
                "execution_status": "completed",
                "measurement": {"status": "complete"},
                "quality_gate": "passed",
                "identity": {"status": "verified"},
                "retrieval_metrics": {"query_count": 2, "ndcg_at_k": 0.5},
            },
        )

    monkeypatch.setattr(addition_runner, "run_assessment_in_subprocess", fake_isolated_assessment)
    config = ExperimentConfig(
        name="isolation",
        baseline=ExperimentVariant(name="baseline", chunking_strategy="same"),
        variants=[ExperimentVariant(name="candidate", chunking_strategy="same")],
    )
    base = {
        "metadata": {"name": "synthetic"},
        "dataset": {
            "path": "frozen.json",
            "split": "test",
            "max_synthetic_questions": 0,
            "sample_docs_per_source_type": 0,
            "seed": 1,
            "min_label_confidence": "low",
        },
        "evaluation": {},
        "retrieval": {"top_k": 5, "search_mode": "rrf_hybrid"},
        "ingestion": {"source_chunk_configs": {"pdf": {"strategy": "simple"}}},
        "embedding_index": {"collection_name": "synthetic", "collection_name_suffix": ""},
    }

    result = addition_runner.run_feature_addition_experiment(
        config, base_experiment=base, execution_mode="diagnostic"
    )

    assert len(calls) == 2
    assert all(call["skip_ingestion"] is False for call in calls)
    assert all(call["force_rerun"] is True for call in calls)
    assert [call["execution_mode"] for call in calls] == ["diagnostic", "diagnostic"]
    assert all(call["generation_implementation"] == "existing" for call in calls)
    assert all(call["harness"] == "deterministic_rag" for call in calls)
    assert (
        len({call["experiment_config"]["embedding_index"]["collection_name"] for call in calls})
        == 2
    )
    assert [result.baseline_result.execution_order, result.variant_results[0].execution_order] == [
        0,
        1,
    ]


def test_worker_payload_rejects_credentials_before_writing_a_request(monkeypatch):
    def no_process(*args, **kwargs):
        pytest.fail("Credential-bearing payload reached subprocess creation")

    monkeypatch.setattr(addition_runner.subprocess, "run", no_process)
    with pytest.raises(ValueError, match="Credential-bearing fields"):
        addition_runner.run_assessment_in_subprocess(
            {"experiment_config": {"llm": {"api_key": "not-a-real-key"}}}
        )


def test_unknown_selection_axes_fail_before_assessment():
    with pytest.raises(ValueError, match="Unsupported generation implementation"):
        addition_runner.run_variant(
            {"metadata": {"name": "synthetic"}, "generation_implementation": "alternate"},
            ExperimentVariant(name="candidate"),
            "unused",
            run_assessment_fn=lambda **_: pytest.fail("unsupported axis must not run"),
        )


def test_benchmark_mode_fails_closed_without_verified_snapshot_contract():
    with pytest.raises(ValueError, match="cannot verify a frozen collection snapshot"):
        addition_runner.validate_execution_mode("benchmark")
