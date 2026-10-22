"""Synthetic contracts for explicit reviewed-evidence manifest execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.evals.artifacts import build_run_identity
from src.evals.assessment.orchestrator import (
    AssessmentPipeline,
    _canonical_sha256,
    _execution_snapshot,
    _read_review_dataset,
    _read_review_manifest,
    _validate_review_context_for_dataset,
    _validate_review_manifest_schema,
    _validate_review_snapshot_binding,
    _verify_review_manifest_unchanged,
)
from src.evals.assessment.retrieval_eval import evaluate_retrieval
from src.evals.schemas import AssessmentConfig
from src.experiments.config import _base_defaults, build_run_assessment_kwargs


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def _review_payload() -> tuple[list[dict], dict, dict]:
    source_content = "A synthetic evidence quotation for a non-clinical wiring test."
    source_id = "synthetic-source"
    source_sha256 = hashlib.sha256(source_content.encode()).hexdigest()
    document_id = "synthetic-document"
    document_content = f"Intro. {source_content} Closing."
    document_sha256 = hashlib.sha256(document_content.encode()).hexdigest()
    case = {
        "query_id": "synthetic-case",
        "query": "synthetic retrieval question",
        "answerability": "answerable",
        "evidence_passages": [
            {
                "passage_id": "synthetic-passage",
                "grade": 2,
                "quote": source_content,
                "source_id": source_id,
                "source_sha256": source_sha256,
            }
        ],
    }
    frozen_sources = {source_id: {"content": source_content, "source_sha256": source_sha256}}
    frozen_documents = {
        document_id: {
            "source_id": source_id,
            "source_sha256": source_sha256,
            "content_sha256": document_sha256,
        }
    }
    qrels = {
        "case_id": case["query_id"],
        "passages": [
            {
                "passage_id": "synthetic-passage",
                "grade": 2,
                "quote": source_content,
                "source_id": source_id,
                "source_sha256": source_sha256,
            }
        ],
    }
    manifest = {
        "schema_version": 1,
        "manifest_id": "synthetic-review-manifest",
        "dataset_sha256": _digest([case]),
        "corpus_sha256": _digest(
            {"frozen_sources": frozen_sources, "frozen_documents": frozen_documents}
        ),
        "frozen_sources": frozen_sources,
        "frozen_documents": frozen_documents,
        "cases": {
            case["query_id"]: {
                "review_status": "human_reviewed",
                "reviewer_id": "synthetic-reviewer",
                "qrels_sha256": _digest(qrels),
            }
        },
    }
    return [case], manifest, {"id": document_id, "content": document_content}


def test_experiment_kwargs_preserve_explicit_review_manifest_path():
    experiment = _base_defaults()
    experiment["evaluation"]["review_manifest_path"] = "synthetic/review.json"

    assert (
        build_run_assessment_kwargs(experiment)["review_manifest_path"] == "synthetic/review.json"
    )


def test_reviewed_runner_forwards_out_of_band_context_and_identity_keeps_only_digest(
    tmp_path: Path,
):
    dataset, manifest, _ = _review_payload()
    manifest_path = tmp_path / "review.json"
    dataset_path = tmp_path / "dataset.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    loaded_manifest, manifest_digest = _read_review_manifest(manifest_path)
    _validate_review_manifest_schema(loaded_manifest)
    loaded_dataset = _read_review_dataset(
        dataset_path, loaded_manifest, hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    )
    _validate_review_context_for_dataset(loaded_manifest, loaded_dataset)

    seen = {}

    def evaluator(rows, top_k, *, review_context):
        seen.update(dataset=rows, top_k=top_k, review_context=review_context)
        return [], {"query_count": len(rows)}

    pipeline = AssessmentPipeline(evaluate_retrieval_fn=evaluator)
    pipeline._run_retrieval_stage(
        AssessmentConfig(artifact_dir=tmp_path, review_manifest_path=manifest_path),
        loaded_dataset,
        None,
        review_context=loaded_manifest,
    )

    assert seen["dataset"] is loaded_dataset
    assert seen["review_context"] is loaded_manifest
    assert seen["top_k"] == 5
    assert manifest_digest == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    execution_snapshot = _execution_snapshot(
        AssessmentConfig(artifact_dir=tmp_path),
        {"review_manifest_sha256": manifest_digest},
    )
    serialized_identity = json.dumps(execution_snapshot)
    assert execution_snapshot["review_manifest_sha256"] == manifest_digest
    assert build_run_identity(config=execution_snapshot, git_head=None) != build_run_identity(
        config={**execution_snapshot, "review_manifest_sha256": "b" * 64}, git_head=None
    )
    assert "synthetic-reviewer" not in serialized_identity
    assert "synthetic evidence quotation" not in serialized_identity


def test_custom_evaluator_cannot_silently_ignore_supplied_review_context(tmp_path: Path):
    called = False

    def evaluator(dataset, top_k):
        nonlocal called
        called = True
        return [], {}

    pipeline = AssessmentPipeline(evaluate_retrieval_fn=evaluator)
    with pytest.raises(ValueError, match="does not support supplied review context"):
        pipeline._run_retrieval_stage(
            AssessmentConfig(artifact_dir=tmp_path), [], None, review_context={}
        )
    assert not called


def test_dataset_digest_mismatch_fails_before_evaluator_work(tmp_path: Path):
    dataset, manifest, _ = _review_payload()
    dataset_path = tmp_path / "dataset.json"
    changed_dataset = [dict(dataset[0], query="mutated question")]
    dataset_path.write_text(json.dumps(changed_dataset), encoding="utf-8")
    called = False

    def evaluator(*args, **kwargs):
        nonlocal called
        called = True
        return [], {}

    with pytest.raises(ValueError, match="does not match its review manifest"):
        _read_review_dataset(
            dataset_path, manifest, hashlib.sha256(dataset_path.read_bytes()).hexdigest()
        )
    assert not called


def test_snapshot_fingerprint_and_actual_document_hashes_are_required():
    _, manifest, document = _review_payload()
    manifest["index_snapshot_fingerprint"] = "a" * 64
    capture = {
        "status": "verified",
        "freeze_guarantee": True,
        "snapshot": {"ids": [document["id"]], "contents": [document["content"]]},
    }
    identity = {"fingerprint": "a" * 64}

    _validate_review_snapshot_binding(manifest, capture, identity)

    changed_capture = {
        **capture,
        "snapshot": {"ids": [document["id"]], "contents": ["changed content"]},
    }
    with pytest.raises(ValueError, match="document binding"):
        _validate_review_snapshot_binding(manifest, changed_capture, identity)
    with pytest.raises(ValueError, match="index snapshot"):
        _validate_review_snapshot_binding(manifest, capture, {"fingerprint": "b" * 64})


def test_review_manifest_is_bounded_non_symlink_and_revalidated_by_bytes(tmp_path: Path):
    _, manifest, _ = _review_payload()
    manifest_path = tmp_path / "review.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _, initial_digest = _read_review_manifest(manifest_path)
    manifest_path.write_text(json.dumps({**manifest, "manifest_id": "mutated"}), encoding="utf-8")
    _, changed_digest = _read_review_manifest(manifest_path)
    assert changed_digest != initial_digest
    with pytest.raises(ValueError, match="changed during measured execution"):
        _verify_review_manifest_unchanged(manifest_path, initial_digest)

    symlink = tmp_path / "review-link.json"
    symlink.symlink_to(manifest_path)
    with pytest.raises(ValueError, match="non-symlink"):
        _read_review_manifest(symlink)


def test_forged_dataset_review_flags_without_manifest_context_stay_unmeasured(monkeypatch):
    import src.rag.runtime as runtime

    dataset, _, document = _review_payload()
    case = dict(
        dataset[0],
        label_origin="human_reviewed",
        review_status="human_reviewed",
        expected_sources=["synthetic-source"],
    )
    retrieved = {
        "id": document["id"],
        "source": "synthetic-source",
        "content": document["content"],
    }
    trace = SimpleNamespace(
        retrieval=SimpleNamespace(documents=[retrieved], score_weights={}), total_time_ms=1.0
    )
    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda *args, **kwargs: ("context", [], trace),
    )

    rows, metrics = evaluate_retrieval([case], top_k=1)

    assert rows[0]["case_status"] == "excluded"
    assert rows[0]["metrics"]["evidence_hit_rate_at_k"] is None
    assert metrics["retrieval_measured_case_count"] == 0
    assert metrics["evidence_hit_rate_at_k"] is None


def test_review_context_binding_uses_canonical_dataset_digest():
    dataset, manifest, _ = _review_payload()
    assert manifest["dataset_sha256"] == _canonical_sha256(dataset)
    _validate_review_context_for_dataset(manifest, dataset)

    altered = [dict(dataset[0], expected_sources=["forged-source"])]
    with pytest.raises(ValueError, match="dataset or evidence binding"):
        _validate_review_context_for_dataset(manifest, altered)
