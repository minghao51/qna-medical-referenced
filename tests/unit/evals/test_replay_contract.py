"""Replay rejects artifact tampering and never emits a fresh latency sample."""

from __future__ import annotations

import hashlib
import json

import pytest

from src.evals.artifacts import build_run_identity
from src.evals.assessment.l6_contract import (
    IDENTITY_CONTRACT_VERSION,
    L6_ANSWER_QUALITY_METRICS,
    L6_ANSWER_QUALITY_ROWS,
    REPLAY_SNAPSHOT_CONTRACT_VERSION,
)
from src.evals.assessment.orchestrator import AssessmentPipeline
from src.evals.schemas import AssessmentRunParams


def _write_verified_benchmark(directory):
    directory.mkdir(parents=True)
    artifacts = {
        "retrieval_dataset.json": json.dumps([{"query_id": "case-1", "query": "synthetic"}]),
        "retrieval_results.jsonl": json.dumps({"query_id": "case-1", "latency_ms": 12.0}) + "\n",
        "retrieval_metrics.json": json.dumps({"latency_p50_ms": 12.0}),
        L6_ANSWER_QUALITY_ROWS: "",
        L6_ANSWER_QUALITY_METRICS: json.dumps({"status": "not_applicable"}),
    }
    for name, content in artifacts.items():
        (directory / name).write_text(content, encoding="utf-8")

    artifact_hashes = {
        name: hashlib.sha256(content.encode("utf-8")).hexdigest()
        for name, content in artifacts.items()
    }
    dataset_hash = "d" * 64
    source_hash = "s" * 64
    lock_hash = "l" * 64
    corpus_hash = "c" * 64
    index_fingerprint = "i" * 64
    execution_snapshot = {
        "dataset": {"file_sha256": dataset_hash, "case_ids_sha256": "q" * 64},
        "source": {"source_content_sha256": source_hash},
        "corpus": {"content_sha256": corpus_hash},
        "retrieval": {
            "index_execution": {
                "actual_index_path_verified": True,
                "retrieval_routed_to_snapshot": True,
            }
        },
    }
    semantic_fingerprint = build_run_identity(
        config={
            "identity_contract_version": IDENTITY_CONTRACT_VERSION,
            "execution_snapshot": execution_snapshot,
            "index_fingerprint": index_fingerprint,
        },
        git_head=None,
    )
    manifest = {
        "execution_id": "synthetic-benchmark",
        "execution_mode": "benchmark",
        "execution_status": "completed",
        "identity_contract_version": IDENTITY_CONTRACT_VERSION,
        "identity": {
            "status": "verified",
            "semantic_fingerprint": semantic_fingerprint,
            "index": {"fingerprint": index_fingerprint},
        },
        "index_snapshot": {"status": "verified", "fingerprint": index_fingerprint},
        "index_execution": {
            "actual_index_path_verified": True,
            "retrieval_routed_to_snapshot": True,
        },
        "input_provenance": {
            "dataset_file_sha256": dataset_hash,
            "source": {
                "status": "verified",
                "source_content_sha256": source_hash,
                "dependency_lock_sha256": lock_hash,
            },
            "corpus": {"status": "verified", "content_sha256": corpus_hash},
        },
        "config": {"execution_snapshot": execution_snapshot},
        "replay_snapshot": {
            "contract_version": REPLAY_SNAPSHOT_CONTRACT_VERSION,
            "eligible": True,
            "artifact_sha256": artifact_hashes,
            "payload_sha256": build_run_identity(config=artifact_hashes, git_head=None),
        },
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def test_tampered_replay_artifact_is_rejected_before_creating_output(tmp_path):
    source = tmp_path / "verified-source"
    _write_verified_benchmark(source)
    (source / "retrieval_metrics.json").write_text(
        json.dumps({"latency_p50_ms": 999.0}), encoding="utf-8"
    )
    output = tmp_path / "replays"

    with pytest.raises(ValueError, match="artifact checksum mismatch"):
        AssessmentPipeline().run(
            AssessmentRunParams(
                artifact_dir=output,
                execution_mode="replay",
                replay_snapshot=source,
            )
        )

    assert not output.exists()


def test_verified_replay_is_explicitly_not_a_latency_or_generation_sample(tmp_path):
    source = tmp_path / "verified-source"
    _write_verified_benchmark(source)

    result = AssessmentPipeline().run(
        AssessmentRunParams(
            artifact_dir=tmp_path / "replays",
            execution_mode="replay",
            replay_snapshot=source,
        )
    )

    assert result.summary["execution_status"] == "replayed"
    assert result.summary["latency_sample"] is False
    assert result.summary["generation_sample"] is False
    assert result.summary["measurement"]["status"] == "not_applicable"
    assert (result.run_dir / "replay_snapshot.json").is_file()
