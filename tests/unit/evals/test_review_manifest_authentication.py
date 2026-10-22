"""Synthetic contracts for content-hash attestations on review manifests."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.evals.assessment import retrieval_eval
from src.evals.assessment.orchestrator import (
    AssessmentPipeline,
    _validate_review_manifest_schema,
)
from src.evals.assessment.retrieval_eval import (
    _canonical_sha256,
    evaluate_retrieval,
    review_manifest_authority_status,
)
from src.evals.schemas import AssessmentConfig


def _review_payload() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    source_content = "Synthetic evidence quotation for a non-clinical wiring test."
    source_id = "synthetic-source"
    source_sha256 = hashlib.sha256(source_content.encode("utf-8")).hexdigest()
    document_id = "synthetic-document"
    document_content = f"Intro. {source_content} Closing."
    document_sha256 = hashlib.sha256(document_content.encode("utf-8")).hexdigest()
    case_id = "synthetic-case"
    passage = {
        "passage_id": "synthetic-passage",
        "grade": 2,
        "quote": source_content,
        "source_id": source_id,
        "source_sha256": source_sha256,
    }
    dataset = [
        {
            "query_id": case_id,
            "query": "synthetic retrieval question",
            "answerability": "answerable",
            "label_origin": "human_reviewed",
            "review_status": "human_reviewed",
            "evidence_passages": [passage],
        }
    ]
    frozen_sources = {source_id: {"content": source_content, "source_sha256": source_sha256}}
    frozen_documents = {
        document_id: {
            "source_id": source_id,
            "source_sha256": source_sha256,
            "content_sha256": document_sha256,
        }
    }
    qrels = {
        "case_id": case_id,
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
        "dataset_sha256": _canonical_sha256(dataset),
        "corpus_sha256": _canonical_sha256(
            {"frozen_sources": frozen_sources, "frozen_documents": frozen_documents}
        ),
        "frozen_sources": frozen_sources,
        "frozen_documents": frozen_documents,
        "cases": {
            case_id: {
                "review_status": "human_reviewed",
                "reviewer_id": "synthetic-reviewer",
                "qrels_sha256": _canonical_sha256(qrels),
            }
        },
    }
    document = {
        "id": document_id,
        "content": document_content,
        "metadata": {"source_id": source_id, "source_sha256": source_sha256},
    }
    return dataset, manifest, document


def _add_attestations(dataset: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    records = {
        case_id: _canonical_sha256(
            {
                "dataset_case": next(item for item in dataset if item["query_id"] == case_id),
                "review_case": review_case,
            }
        )
        for case_id, review_case in manifest["cases"].items()
    }
    manifest["attestations"] = {
        "schema_version": 1,
        "records": records,
        "content_sha256": _canonical_sha256({"schema_version": 1, "records": records}),
    }
    return manifest


def _refresh_attestation_content_hash(manifest: dict[str, Any]) -> None:
    attestations = manifest["attestations"]
    attestations["content_sha256"] = _canonical_sha256(
        {"schema_version": 1, "records": attestations["records"]}
    )


def _attest_case_without_dataset_id(
    manifest: dict[str, Any], dataset: list[dict[str, Any]], unbindable_case: dict[str, Any]
) -> None:
    """Attest a manifest whose second case has no stable dataset id to bind against."""
    manifest["dataset_sha256"] = _canonical_sha256(dataset)
    manifest["cases"]["synthetic-case-2"] = {
        "review_status": "human_reviewed",
        "reviewer_id": "second-synthetic-reviewer",
        "qrels_sha256": manifest["cases"]["synthetic-case"]["qrels_sha256"],
    }
    records = {
        "synthetic-case": _canonical_sha256(
            {"dataset_case": dataset[0], "review_case": manifest["cases"]["synthetic-case"]}
        ),
        "synthetic-case-2": _canonical_sha256(
            {
                "dataset_case": unbindable_case,
                "review_case": manifest["cases"]["synthetic-case-2"],
            }
        ),
    }
    manifest["attestations"] = {
        "schema_version": 1,
        "records": records,
        "content_sha256": _canonical_sha256({"schema_version": 1, "records": records}),
    }


def _evaluate(
    monkeypatch: pytest.MonkeyPatch,
    dataset: list[dict[str, Any]],
    manifest: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import src.rag.runtime as runtime

    _, _, document = _review_payload()
    trace = SimpleNamespace(
        retrieval=SimpleNamespace(documents=[document], score_weights={}), total_time_ms=1.0
    )
    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda *args, **kwargs: ("context", [], trace),
    )
    return evaluate_retrieval(dataset, top_k=1, review_context=manifest)


def _assert_hash_failure(
    monkeypatch: pytest.MonkeyPatch, dataset: list[dict[str, Any]], manifest: dict[str, Any]
) -> None:
    rows, aggregate = _evaluate(monkeypatch, dataset, manifest)
    assert rows
    assert all(row["case_status"] == "excluded" for row in rows)
    assert all(
        row["exclusion_reason"] == "trusted_review_manifest_hash_verification_failed"
        for row in rows
    )
    assert aggregate["review_authority_status"] == "unavailable"
    assert aggregate["retrieval_measured_case_count"] == 0
    assert aggregate["reviewed_evidence_eligible"] is False


def _record_identity(
    monkeypatch: pytest.MonkeyPatch,
    dataset: list[dict[str, Any]],
    status: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pipeline = AssessmentPipeline()
    identity_result: dict[str, Any] = {"reasons": []}
    monkeypatch.setattr(
        pipeline, "_update_execution_identity", lambda *args, **kwargs: identity_result
    )
    config_payload: dict[str, Any] = {"execution_snapshot": {"dataset": {}}}
    identity = pipeline._record_dataset_identity(
        AssessmentConfig(artifact_dir=Path("synthetic"), execution_mode="diagnostic"),
        config_payload,
        {},
        {},
        "fresh-synthetic-execution",
        dataset,
        review_authority_status=status,
    )
    return config_payload["execution_snapshot"], identity


def test_legacy_v1_manifest_keeps_current_status_and_false_eligibility(monkeypatch):
    dataset, manifest, _ = _review_payload()

    assert review_manifest_authority_status(None, dataset) is None
    assert (
        review_manifest_authority_status(manifest, dataset) == "manifest_asserted_not_authenticated"
    )
    rows, aggregate = _evaluate(monkeypatch, dataset, manifest)

    assert rows[0]["case_status"] == "measured"
    assert aggregate["review_authority_status"] == "manifest_asserted_not_authenticated"
    assert aggregate["reviewed_evidence_eligible"] is False
    _, identity = _record_identity(monkeypatch, dataset, "manifest_asserted_not_authenticated")
    assert identity["review_authority_status"] == "manifest_asserted_not_authenticated"
    assert identity["reviewed_evidence_eligible"] is False
    assert identity["cohort_eligible"] is False
    assert identity["promotion_eligible"] is False
    _, no_manifest_identity = _record_identity(monkeypatch, dataset, None)
    assert no_manifest_identity["review_authority_status"] == "manifest_asserted_not_authenticated"


def test_manifest_schema_accepts_attestation_object_and_rejects_non_object():
    _, manifest, _ = _review_payload()
    manifest["attestations"] = {}
    _validate_review_manifest_schema(manifest)
    manifest["attestations"] = []

    with pytest.raises(ValueError, match="attestations"):
        _validate_review_manifest_schema(manifest)


def test_verified_attestations_report_content_hash_status_without_eligibility(monkeypatch):
    dataset, manifest, _ = _review_payload()
    _add_attestations(dataset, manifest)

    assert (
        review_manifest_authority_status(manifest, dataset)
        == "manifest_hash_verified_not_identity_authenticated"
    )
    rows, aggregate = _evaluate(monkeypatch, dataset, manifest)

    assert rows[0]["case_status"] == "measured"
    assert aggregate["review_authority_status"] == (
        "manifest_hash_verified_not_identity_authenticated"
    )
    assert aggregate["reviewed_evidence_eligible"] is False


def test_tampered_evidence_record_rejects_whole_manifest(monkeypatch):
    dataset, manifest, _ = _review_payload()
    _add_attestations(dataset, manifest)
    changed_passage = dict(dataset[0]["evidence_passages"][0], grade=1)
    changed_dataset = [dict(dataset[0], evidence_passages=[changed_passage])]
    manifest["dataset_sha256"] = _canonical_sha256(changed_dataset)
    _refresh_attestation_content_hash(manifest)

    _assert_hash_failure(monkeypatch, changed_dataset, manifest)


def test_review_record_content_mismatch_fails_even_with_self_consistent_overall_hash(
    monkeypatch,
):
    dataset, manifest, _ = _review_payload()
    _add_attestations(dataset, manifest)
    manifest["cases"]["synthetic-case"]["reviewer_id"] = "changed-synthetic-reviewer"
    _refresh_attestation_content_hash(manifest)

    _assert_hash_failure(monkeypatch, dataset, manifest)


def test_overall_hash_collision_cannot_authenticate_changed_record(monkeypatch):
    dataset, manifest, _ = _review_payload()
    _add_attestations(dataset, manifest)
    manifest["cases"]["synthetic-case"]["reviewer_id"] = "changed-synthetic-reviewer"
    existing_overall_hash = manifest["attestations"]["content_sha256"]
    assert isinstance(existing_overall_hash, str)
    canonical_sha256: Callable[[Any], str | None] = _canonical_sha256

    def collide_overall_hash(value: Any) -> str | None:
        if isinstance(value, dict) and value.get("schema_version") == 1 and "records" in value:
            return existing_overall_hash
        return canonical_sha256(value)

    monkeypatch.setattr(retrieval_eval, "_canonical_sha256", collide_overall_hash)
    _assert_hash_failure(monkeypatch, dataset, manifest)


@pytest.mark.parametrize("bad_hash", ["0" * 64, "f" * 64])
def test_wrong_overall_attestation_hash_rejects_whole_manifest(monkeypatch, bad_hash: str):
    dataset, manifest, _ = _review_payload()
    _add_attestations(dataset, manifest)
    valid_hash = manifest["attestations"]["content_sha256"]
    manifest["attestations"]["content_sha256"] = bad_hash if bad_hash != valid_hash else "1" * 64

    _assert_hash_failure(monkeypatch, dataset, manifest)


def test_malformed_attestation_shape_rejects_whole_manifest(monkeypatch):
    dataset, manifest, _ = _review_payload()
    manifest["attestations"] = {
        "schema_version": 1,
        "records": [],
        "content_sha256": "a" * 64,
    }

    _assert_hash_failure(monkeypatch, dataset, manifest)


def test_record_key_collision_for_different_content_rejects_whole_manifest(monkeypatch):
    dataset, manifest, _ = _review_payload()
    _add_attestations(dataset, manifest)
    dataset_with_collision = [dataset[0], dict(dataset[0], query="different content")]
    manifest["dataset_sha256"] = _canonical_sha256(dataset_with_collision)
    _refresh_attestation_content_hash(manifest)

    _assert_hash_failure(monkeypatch, dataset_with_collision, manifest)


def test_dataset_and_corpus_mismatches_keep_existing_rejection(monkeypatch):
    dataset, manifest, _ = _review_payload()
    changed_dataset = [dict(dataset[0], query="changed synthetic query")]
    rows, aggregate = _evaluate(monkeypatch, changed_dataset, manifest)
    assert rows[0]["exclusion_reason"] == "trusted_review_context_missing_or_invalid"
    assert aggregate["review_authority_status"] == "unavailable"

    manifest["corpus_sha256"] = "f" * 64
    rows, aggregate = _evaluate(monkeypatch, dataset, manifest)
    assert rows[0]["exclusion_reason"] == "trusted_review_context_missing_or_invalid"
    assert aggregate["review_authority_status"] == "unavailable"


def test_orchestrator_identity_snapshot_uses_computed_status_and_keeps_guards_false(
    monkeypatch: pytest.MonkeyPatch,
):
    dataset, manifest, _ = _review_payload()
    _add_attestations(dataset, manifest)
    computed_status = review_manifest_authority_status(manifest, dataset)

    snapshot, identity = _record_identity(monkeypatch, dataset, computed_status)

    assert snapshot["dataset"]["review_authority_status"] == (
        "manifest_hash_verified_not_identity_authenticated"
    )
    assert identity["review_authority_status"] == (
        "manifest_hash_verified_not_identity_authenticated"
    )
    assert identity["reviewed_evidence_eligible"] is False
    assert identity["cohort_eligible"] is False
    assert identity["promotion_eligible"] is False


def test_tampering_one_record_rejects_every_case_in_a_multi_case_manifest(monkeypatch):
    dataset, manifest, _ = _review_payload()
    second_case = dict(dataset[0])
    second_case["query_id"] = "synthetic-case-2"
    second_case["query"] = "second synthetic retrieval question"
    dataset.append(second_case)
    manifest["dataset_sha256"] = _canonical_sha256(dataset)
    first_case_id = next(iter(manifest["cases"]))
    manifest["cases"]["synthetic-case-2"] = {
        "review_status": "human_reviewed",
        "reviewer_id": "second-synthetic-reviewer",
        "qrels_sha256": manifest["cases"][first_case_id]["qrels_sha256"],
    }
    _add_attestations(dataset, manifest)
    manifest["cases"][first_case_id]["reviewer_id"] = "tampered-synthetic-reviewer"

    rows, aggregate = _evaluate(monkeypatch, dataset, manifest)

    assert len(rows) == 2
    assert {row["query_id"] for row in rows} == {"synthetic-case", "synthetic-case-2"}
    assert all(row["case_status"] == "excluded" for row in rows)
    assert all(
        row["exclusion_reason"] == "trusted_review_manifest_hash_verification_failed"
        for row in rows
    )
    assert aggregate["review_authority_status"] == "unavailable"
    assert aggregate["retrieval_measured_case_count"] == 0
    assert aggregate["reviewed_evidence_eligible"] is False


def test_extra_attestation_keys_reject_whole_manifest(monkeypatch):
    dataset, manifest, _ = _review_payload()
    _add_attestations(dataset, manifest)
    manifest["attestations"]["reviewer_signature"] = "synthetic-extra-attestation-key"

    _assert_hash_failure(monkeypatch, dataset, manifest)


@pytest.mark.parametrize("bool_schema_version", [True, False])
def test_boolean_attestation_schema_version_rejects_whole_manifest(
    monkeypatch, bool_schema_version: bool
):
    dataset, manifest, _ = _review_payload()
    _add_attestations(dataset, manifest)
    manifest["attestations"]["schema_version"] = bool_schema_version

    _assert_hash_failure(monkeypatch, dataset, manifest)


def test_manifest_records_beyond_the_dataset_reject_whole_manifest(monkeypatch):
    dataset, manifest, _ = _review_payload()
    second_case = dict(dataset[0])
    second_case["query_id"] = "synthetic-case-2"
    second_case["query"] = "second synthetic retrieval question"
    dataset.append(second_case)
    manifest["dataset_sha256"] = _canonical_sha256(dataset)
    manifest["cases"]["synthetic-case-2"] = {
        "review_status": "human_reviewed",
        "reviewer_id": "second-synthetic-reviewer",
        "qrels_sha256": manifest["cases"]["synthetic-case"]["qrels_sha256"],
    }
    _add_attestations(dataset, manifest)
    reduced_dataset = [dataset[0]]
    manifest["dataset_sha256"] = _canonical_sha256(reduced_dataset)

    assert review_manifest_authority_status(manifest, reduced_dataset) == "unavailable"
    _assert_hash_failure(monkeypatch, reduced_dataset, manifest)


def test_dataset_cases_outside_the_manifest_stay_excluded_with_verified_status(monkeypatch):
    dataset, manifest, _ = _review_payload()
    second_case = dict(dataset[0])
    second_case["query_id"] = "synthetic-case-2"
    second_case["query"] = "second synthetic retrieval question"
    dataset.append(second_case)
    manifest["dataset_sha256"] = _canonical_sha256(dataset)
    _add_attestations(dataset, manifest)

    assert (
        review_manifest_authority_status(manifest, dataset)
        == "manifest_hash_verified_not_identity_authenticated"
    )
    rows, aggregate = _evaluate(monkeypatch, dataset, manifest)

    assert len(rows) == 2
    rows_by_id = {row["query_id"]: row for row in rows}
    assert rows_by_id["synthetic-case"]["case_status"] == "measured"
    assert rows_by_id["synthetic-case-2"]["case_status"] == "excluded"
    assert (
        rows_by_id["synthetic-case-2"]["exclusion_reason"] == "case_not_in_trusted_review_manifest"
    )
    assert aggregate["review_authority_status"] == (
        "manifest_hash_verified_not_identity_authenticated"
    )
    assert aggregate["retrieval_measured_case_count"] == 1
    assert aggregate["reviewed_evidence_eligible"] is False


@pytest.mark.parametrize("query_id", [None, "   "], ids=["missing", "whitespace-only"])
def test_dataset_case_without_usable_query_id_rejects_whole_manifest(
    monkeypatch, query_id: str | None
):
    dataset, manifest, _ = _review_payload()
    unbindable_case = dict(dataset[0])
    if query_id is None:
        del unbindable_case["query_id"]
    else:
        unbindable_case["query_id"] = query_id
    unbindable_case["query"] = "unbindable synthetic retrieval question"
    unbindable_dataset = [dataset[0], unbindable_case]
    _attest_case_without_dataset_id(manifest, unbindable_dataset, unbindable_case)

    assert review_manifest_authority_status(manifest, unbindable_dataset) == "unavailable"
    _assert_hash_failure(monkeypatch, unbindable_dataset, manifest)


def test_wrapper_guards_reject_non_dict_context_and_none_dataset() -> None:
    """Pin the wrapper-level guards: a non-dict context and dataset=None stay None."""
    dataset, manifest, _ = _review_payload()
    status_for: Callable[..., Any] = review_manifest_authority_status

    assert status_for(["not", "a", "manifest"], dataset) is None
    assert review_manifest_authority_status(manifest, None) is None


def test_evaluate_retrieval_hashes_base_parts_once_and_verifies_attestations_at_most_once(
    monkeypatch: pytest.MonkeyPatch,
):
    """Pin the evaluate path: base parts computed once, attestation verification ≤1."""
    dataset, manifest, _ = _review_payload()
    _add_attestations(dataset, manifest)

    real_base_parts = retrieval_eval._review_context_base_parts
    real_verify = retrieval_eval._verify_review_attestations
    base_parts_calls: list[dict[str, Any] | None] = []
    verify_calls: list[dict[str, Any]] = []

    def counting_base_parts(
        review_context: dict[str, Any] | None, counted_dataset: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
        base_parts_calls.append(review_context)
        return real_base_parts(review_context, counted_dataset)

    def counting_verify(
        review_context: dict[str, Any],
        counted_dataset: list[dict[str, Any]],
        cases: dict[str, Any],
    ) -> bool:
        verify_calls.append(cases)
        return real_verify(review_context, counted_dataset, cases)

    monkeypatch.setattr(retrieval_eval, "_review_context_base_parts", counting_base_parts)
    monkeypatch.setattr(retrieval_eval, "_verify_review_attestations", counting_verify)

    rows, aggregate = _evaluate(monkeypatch, dataset, manifest)

    # The reduced counts hold while the evaluation still measures the case with
    # the attested verified status, so the pins cannot pass on a broken path.
    assert len(base_parts_calls) == 1
    assert len(verify_calls) <= 1
    assert rows[0]["case_status"] == "measured"
    assert aggregate["review_authority_status"] == (
        "manifest_hash_verified_not_identity_authenticated"
    )
