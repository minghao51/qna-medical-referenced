"""Fresh, explicitly non-comparable attempts while full identity is unavailable."""

import json

import pytest
from pydantic import BaseModel

from src.evals.artifact_service import EvaluationService
from src.evals.assessment import orchestrator as pa
from src.evals.schemas import AssessmentRunParams


class _CredentialConfig(BaseModel):
    api_key: str


def _pipeline(source=None):
    def step(aggregate=None):
        return {"aggregate": aggregate or {}, "records": [], "findings": []}

    return pa.AssessmentPipeline(
        audit_l0_download_fn=lambda: step(),
        assess_l1_html_markdown_quality_fn=lambda: step({"markdown_empty_rate": 0.0}),
        assess_l2_pdf_quality_fn=lambda: step({"empty_page_rate": 0.0}),
        assess_l3_chunking_quality_fn=lambda: step({"duplicate_chunk_rate": 0.0}),
        assess_l4_reference_quality_fn=lambda: step(),
        assess_l5_index_quality_fn=lambda **kwargs: step({"embedding_dim_consistent": True}),
        build_retrieval_dataset_fn=lambda **kwargs: {
            "dataset": [{"query_id": "synthetic", "query": "synthetic question"}],
            "stats": {},
        },
        evaluate_retrieval_fn=lambda *args, **kwargs: (
            [],
            {
                "query_count": 1,
                "exact_chunk_hit_rate_high_conf": 1.0,
                "evidence_hit_rate_high_conf": 1.0,
                "hit_rate_at_k_high_conf": 1.0,
                "mrr_high_conf": 1.0,
                "topic_false_positive_rate": 0.0,
                "duplicate_source_ratio_mean": 0.0,
            },
        ),
        git_head_fn=lambda: "synthetic-revision",
        source_provenance_fn=lambda: (
            source
            or {
                "version": 1,
                "status": "verified",
                "git_head": "synthetic-revision",
                "dirty": True,
                "source_content_sha256": "synthetic-source-digest",
                "dependency_lock_sha256": "synthetic-lock-digest",
            }
        ),
        configure_runtime_for_experiment_fn=lambda config: {},
        log_assessment_to_wandb_fn=lambda **kwargs: {"enabled": False},
        render_summary_fn=lambda **kwargs: "synthetic summary",
        sha256_file_fn=lambda path: None,
    )


def test_fresh_attempts_do_not_collapse_or_leave_orphan_manifests(tmp_path, monkeypatch):
    monkeypatch.setattr(pa, "DATA_RAW_DIR", tmp_path / "absent-corpus")
    pipeline = _pipeline()
    params = AssessmentRunParams(artifact_dir=tmp_path / "evals", disable_llm_generation=True)
    first, second = pipeline.run(params), pipeline.run(params)
    manifests = list(params.artifact_dir.glob("*/manifest.json"))
    assert len(manifests) == 2
    assert {path.parent for path in manifests} == {first.run_dir, second.run_dir}
    assert first.run_dir != second.run_dir
    assert first.summary["execution_id"] != second.summary["execution_id"]
    assert (
        first.summary["identity"]["configuration_fingerprint"]
        == second.summary["identity"]["configuration_fingerprint"]
    )
    for result in (first, second):
        manifest = json.loads((result.run_dir / "manifest.json").read_text())
        assert manifest["execution_id"] == result.summary["execution_id"]
        assert manifest["identity"] == result.summary["identity"]
        assert result.summary["cache_policy"]["mode"] == "fresh"
        assert result.summary["cache_policy"]["run_reuse"] is False
        assert result.summary["artifact_contract_version"] == 1
    index = json.loads((params.artifact_dir / "run_index.json").read_text())
    assert set(index["entries"]) == {first.summary["execution_id"], second.summary["execution_id"]}


def test_execution_names_paths_and_force_do_not_change_configuration_fingerprint(tmp_path):
    pipeline = _pipeline()
    first = pipeline._resolve_config(AssessmentRunParams(artifact_dir=tmp_path / "a", name="a"))
    second = pipeline._resolve_config(
        AssessmentRunParams(artifact_dir=tmp_path / "b", name="b", force_rerun=True)
    )
    assert first[4] == second[4]


def test_source_content_changes_configuration_fingerprint(tmp_path):
    source = {"status": "verified", "source_content_sha256": "before"}
    pipeline = _pipeline(source)
    params = AssessmentRunParams(artifact_dir=tmp_path)
    before = pipeline._resolve_config(params)[4]
    source["source_content_sha256"] = "after"
    assert pipeline._resolve_config(params)[4] != before


@pytest.mark.parametrize("source_status", ["verified", "unverified"])
def test_unverified_index_is_not_a_valid_semantic_identity(tmp_path, source_status):
    result = _pipeline({"status": source_status}).run(AssessmentRunParams(artifact_dir=tmp_path))
    identity = result.summary["identity"]
    assert identity["status"] == "unverified"
    assert identity["semantic_fingerprint"] is None
    assert identity["index"]["status"] == "unverified"
    assert identity["reuse_eligible"] is False
    assert identity["promotion_eligible"] is False
    assert result.summary["cache_policy"]["persistent_reuse"] is False


@pytest.mark.parametrize(
    ("version", "label"), [(None, "legacy"), (1, "versioned"), (999, "unsupported")]
)
def test_readers_label_legacy_and_new_without_rewriting(tmp_path, version, label):
    run_dir = tmp_path / "20261016T000000.000000Z_synthetic"
    run_dir.mkdir()
    manifest = {"config": {}, "git_head": "synthetic"}
    if version is not None:
        manifest["artifact_contract_version"] = version
    files = {
        "manifest.json": json.dumps(manifest),
        "summary.json": json.dumps({"status": "ok"}),
        "retrieval_metrics.json": json.dumps({"query_count": 1}),
    }
    for name, content in files.items():
        (run_dir / name).write_text(content)
    service = EvaluationService(evals_dir=tmp_path, latest_pointer=tmp_path / "latest_run.txt")
    payload = service.load_run_payload(run_dir)
    assert payload["artifact_compatibility"] == label
    assert payload["comparable"] is False
    assert payload["manifest"] == manifest
    history = service.local_history_runs(10)
    assert history[0]["artifact_compatibility"] == label
    assert history[0]["comparable"] is False
    for name, content in files.items():
        assert (run_dir / name).read_text() == content


def test_run_never_consults_legacy_dedup_lookup(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("fresh execution must not consult legacy reuse")

    monkeypatch.setattr("src.evals.artifacts.find_reusable_run", forbidden)
    first = _pipeline().run(AssessmentRunParams(artifact_dir=tmp_path))
    second = _pipeline().run(AssessmentRunParams(artifact_dir=tmp_path))
    assert first.run_dir != second.run_dir


def test_snapshot_failure_does_not_invent_verified_source(tmp_path):
    pipeline = _pipeline()

    def unavailable():
        raise OSError("synthetic private path must not be persisted")

    pipeline.source_provenance_fn = unavailable
    result = pipeline.run(AssessmentRunParams(artifact_dir=tmp_path))
    manifest = json.loads((result.run_dir / "manifest.json").read_text())
    source = manifest["input_provenance"]["source"]
    assert source["status"] == "unverified"
    assert "synthetic private path" not in json.dumps(manifest)


def test_unverified_dataset_cache_replay_fails_actionably(tmp_path):
    with pytest.raises(ValueError, match="explicit dataset_path"):
        _pipeline().run(AssessmentRunParams(artifact_dir=tmp_path, reuse_cached_dataset=True))
    assert list(tmp_path.iterdir()) == []


def test_new_attempt_cannot_be_reused_through_legacy_lookup(tmp_path):
    from src.evals.artifacts import find_reusable_run

    result = _pipeline().run(AssessmentRunParams(artifact_dir=tmp_path))
    fingerprint = result.summary["identity"]["configuration_fingerprint"]
    assert find_reusable_run(tmp_path, fingerprint) is None
    assert find_reusable_run(tmp_path, result.summary["execution_id"]) is None


def test_invalid_metrics_remain_incomplete_but_artifacts_are_valid_json(tmp_path):
    pipeline = _pipeline()
    pipeline.evaluate_answers_fn = lambda *args, **kwargs: (
        [],
        {"status": "ok", "faithfulness": {"mean": float("inf"), "count": 1}},
    )
    result = pipeline.run(AssessmentRunParams(artifact_dir=tmp_path, include_answer_eval=True))
    assert result.status == "incomplete"
    assert result.summary["quality_gate"] == "incomplete"
    assert result.summary["l6_answer_quality_metrics"]["faithfulness"]["mean"] is None

    def nonfinite(value):
        raise AssertionError(f"non-JSON numeric token: {value}")

    for path in result.run_dir.glob("*.json"):
        json.loads(path.read_text(), parse_constant=nonfinite)


@pytest.mark.parametrize(
    "secret_config",
    [
        {"api_key": "synthetic-secret-canary"},
        {"apiKey": "synthetic-secret-canary"},
        {"refreshToken": "synthetic-secret-canary"},
        {"nested": _CredentialConfig(api_key="synthetic-secret-canary")},
        {"nested": {"custom_headers": {"X-Auth": "synthetic-secret-canary"}}},
        {"nested": {"provider-api-key": "synthetic-secret-canary"}},
        {"authorization": "synthetic-secret-canary"},
        {"endpoint": "https://user:synthetic-secret-canary@example.invalid/v1"},
        {"endpoint": "https://example.invalid/v1?key=synthetic-secret-canary"},
    ],
)
def test_credential_config_is_rejected_before_hashing_or_persistence(
    tmp_path, monkeypatch, secret_config
):
    def forbidden(*args, **kwargs):
        raise AssertionError("credential-bearing config must not be fingerprinted")

    monkeypatch.setattr(pa, "build_run_identity", forbidden)
    with pytest.raises(ValueError, match="must not contain credentials") as exc:
        _pipeline().run(AssessmentRunParams(artifact_dir=tmp_path, experiment_config=secret_config))
    assert "synthetic-secret-canary" not in str(exc.value)
    assert list(tmp_path.iterdir()) == []


def test_nested_diagnostic_numbers_do_not_abort_valid_jsonl_publication(tmp_path):
    pipeline = _pipeline()
    evaluate = pipeline.evaluate_retrieval_fn

    class StructuredDiagnostic(BaseModel):
        values: tuple[float, ...]

    def nested_trace(*args, **kwargs):
        _, metrics = evaluate(*args, **kwargs)
        return [
            {
                "trace": {
                    "timing": float("inf"),
                    "scores": (float("nan"),),
                    "structured": StructuredDiagnostic(values=(float("inf"),)),
                }
            }
        ], metrics

    pipeline.evaluate_retrieval_fn = nested_trace
    pipeline.audit_l0_download_fn = lambda: {
        "aggregate": {},
        "records": [],
        "findings": [{"diagnostic": float("inf")}],
    }
    result = pipeline.run(AssessmentRunParams(artifact_dir=tmp_path))
    assert result.status == "ok"

    def nonfinite(value):
        raise AssertionError(f"non-JSON numeric token: {value}")

    for path in result.run_dir.glob("*.json*"):
        lines = path.read_text().splitlines() if path.suffix == ".jsonl" else [path.read_text()]
        for line in lines:
            json.loads(line, parse_constant=nonfinite)
    row = json.loads((result.run_dir / "retrieval_results.jsonl").read_text())
    assert row["trace"] == {"timing": None, "scores": [None], "structured": {"values": [None]}}
