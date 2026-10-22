"""Offline contracts for the schema-v1 review-manifest authoring tool.

Drives ``src.evals.assessment.review_manifest_tool`` through its public
builder and ``main()`` with synthetic fixtures only (adapted from the
review-manifest authentication tests): no network, no chroma, and every
output lands in ``tmp_path``.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from src.evals.assessment import review_manifest_tool as tool
from src.evals.assessment.orchestrator import (
    _read_review_manifest,
    _validate_review_manifest_schema,
)
from src.evals.assessment.retrieval_eval import (
    _canonical_sha256,
    _review_context_parts,
    _review_manifest_authority_status_from_parts,
    _verify_review_attestations,
)

_SOURCE_ID = "synthetic-source"
_DOCUMENT_ID = "synthetic-document"
_SOURCE_CONTENT = "Synthetic evidence quotation for a non-clinical wiring test."
_DOCUMENT_CONTENT = f"Intro. {_SOURCE_CONTENT} Closing."
_CASE_ID = "synthetic-case"
_PASSAGE_ID = "synthetic-passage"
_REVIEWER_ID = "synthetic-reviewer"


def _source_sha256() -> str:
    return hashlib.sha256(_SOURCE_CONTENT.encode("utf-8")).hexdigest()


def _passage() -> dict[str, Any]:
    return {
        "passage_id": _PASSAGE_ID,
        "grade": 2,
        "quote": _SOURCE_CONTENT,
        "source_id": _SOURCE_ID,
        "source_sha256": _source_sha256(),
    }


def _dataset() -> list[dict[str, Any]]:
    return [
        {
            "query_id": _CASE_ID,
            "query": "synthetic retrieval question",
            "answerability": "answerable",
            "label_origin": "human_reviewed",
            "review_status": "human_reviewed",
            "evidence_passages": [_passage()],
        }
    ]


def _corpus() -> dict[str, Any]:
    return {
        "sources": {_SOURCE_ID: {"content": _SOURCE_CONTENT}},
        "documents": {_DOCUMENT_ID: {"source_id": _SOURCE_ID, "content": _DOCUMENT_CONTENT}},
    }


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run(
    tmp_path: Path,
    dataset: list[dict[str, Any]] | None = None,
    corpus: dict[str, Any] | None = None,
    dataset_raw: str | None = None,
    corpus_raw: str | None = None,
    *,
    reviewer_id: str = _REVIEWER_ID,
    manifest_id: str = "synthetic-review-manifest",
    fingerprint: str | None = None,
    output_name: str = "manifest.json",
) -> tuple[int, Path]:
    dataset_path = _write_json(
        tmp_path / "dataset.json", dataset if dataset is not None else _dataset()
    )
    corpus_path = _write_json(tmp_path / "corpus.json", corpus if corpus is not None else _corpus())
    if dataset_raw is not None:
        dataset_path.write_text(dataset_raw, encoding="utf-8")
    if corpus_raw is not None:
        corpus_path.write_text(corpus_raw, encoding="utf-8")
    output = tmp_path / output_name
    argv = [
        "--dataset",
        str(dataset_path),
        "--corpus",
        str(corpus_path),
        "--reviewer-id",
        reviewer_id,
        "--manifest-id",
        manifest_id,
        "--output",
        str(output),
    ]
    if fingerprint is not None:
        argv.extend(["--index-snapshot-fingerprint", fingerprint])
    return tool.main(argv), output


def test_unanswerable_case_with_non_list_evidence_still_refuses(tmp_path, capsys) -> None:
    # Guard order: the non-list type check precedes the unanswerable branch,
    # so malformed declared evidence refuses even for unanswerable cases.
    dataset = _dataset()
    dataset[0]["answerability"] = "unanswerable"
    dataset[0]["evidence_passages"] = {"passage_id": "x"}

    exit_code, output = _run(tmp_path, dataset=dataset)

    assert exit_code != 0
    assert not output.exists()
    assert "synthetic-case" in capsys.readouterr().err


def test_symlinked_output_alias_refuses_and_preserves_the_input(tmp_path) -> None:
    dataset_path = _write_json(tmp_path / "dataset.json", _dataset())
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    dataset_bytes = dataset_path.read_bytes()
    output = tmp_path / "aliased-output.json"
    output.symlink_to(dataset_path)

    exit_code = tool.main(
        [
            "--dataset",
            str(dataset_path),
            "--corpus",
            str(corpus_path),
            "--reviewer-id",
            _REVIEWER_ID,
            "--manifest-id",
            "synthetic-review-manifest",
            "--output",
            str(output),
        ]
    )

    assert exit_code != 0
    assert dataset_path.read_bytes() == dataset_bytes


def test_end_to_end_manifest_verifies_with_hash_verified_status(tmp_path, capsys) -> None:
    exit_code, output = _run(tmp_path)

    assert exit_code == 0
    assert output.is_file()
    manifest, _ = _read_review_manifest(output)
    _validate_review_manifest_schema(manifest)
    # Read-back equality: the parsed artifact must equal the authored manifest.
    assert manifest == tool.build_review_manifest(
        _dataset(), _corpus(), _REVIEWER_ID, "synthetic-review-manifest"
    )
    dataset = _dataset()
    assert manifest["dataset_sha256"] == _canonical_sha256(dataset)
    parts = _review_context_parts(manifest, dataset)
    assert parts is not None
    assert _verify_review_attestations(manifest, dataset, parts[0]) is True
    assert (
        _review_manifest_authority_status_from_parts(manifest, parts)
        == "manifest_hash_verified_not_identity_authenticated"
    )
    assert manifest["cases"] == {
        _CASE_ID: {
            "review_status": "human_reviewed",
            "reviewer_id": _REVIEWER_ID,
            "qrels_sha256": _canonical_sha256(
                {
                    "case_id": _CASE_ID,
                    "passages": [
                        {
                            "passage_id": _PASSAGE_ID,
                            "grade": 2,
                            "quote": _SOURCE_CONTENT,
                            "source_id": _SOURCE_ID,
                            "source_sha256": _source_sha256(),
                        }
                    ],
                }
            ),
        }
    }
    summary = capsys.readouterr().out
    assert str(output) in summary
    assert "manifest_hash_verified_not_identity_authenticated" in summary


def test_rebuild_is_byte_identical(tmp_path) -> None:
    first_code, first_output = _run(tmp_path, output_name="first.json")
    second_code, second_output = _run(tmp_path, output_name="second.json")

    assert first_code == second_code == 0
    assert first_output.read_bytes() == second_output.read_bytes()


def test_output_keys_are_exactly_the_schema_allowed_set(tmp_path) -> None:
    without_code, without_output = _run(tmp_path, output_name="without.json")
    with_code, with_output = _run(tmp_path, output_name="with.json", fingerprint="a" * 64)

    assert without_code == with_code == 0
    without_manifest, _ = _read_review_manifest(without_output)
    with_manifest, _ = _read_review_manifest(with_output)
    required = {
        "schema_version",
        "manifest_id",
        "dataset_sha256",
        "corpus_sha256",
        "frozen_sources",
        "frozen_documents",
        "cases",
    }
    assert set(without_manifest) == required | {"attestations"}
    assert set(with_manifest) == required | {"attestations", "index_snapshot_fingerprint"}


def test_tampered_evidence_quote_refuses_without_output(tmp_path, capsys) -> None:
    tampered = _dataset()
    tampered[0]["evidence_passages"] = [dict(_passage(), quote="tampered synthetic quote")]

    exit_code, output = _run(tmp_path, dataset=tampered)

    assert exit_code != 0
    assert not output.exists()
    assert "synthetic-case" in capsys.readouterr().err


@pytest.mark.parametrize(
    "declared",
    [{"passage_id": "x"}, "synthetic-passage", 3, None],
    ids=["object", "string", "number", "null"],
)
def test_non_list_evidence_passages_refuse_naming_the_case(tmp_path, capsys, declared) -> None:
    dataset = _dataset()
    dataset[0]["evidence_passages"] = declared

    exit_code, output = _run(tmp_path, dataset=dataset)

    assert exit_code != 0
    assert not output.exists()
    assert "synthetic-case" in capsys.readouterr().err


def test_corpus_missing_quoted_source_content_refuses_naming_the_case(tmp_path, capsys) -> None:
    corpus = _corpus()
    corpus["sources"][_SOURCE_ID] = {"content": "Unrelated synthetic source content."}

    exit_code, output = _run(tmp_path, corpus=corpus)

    assert exit_code != 0
    assert not output.exists()
    assert "synthetic-case" in capsys.readouterr().err


def test_duplicate_case_ids_refuse(tmp_path) -> None:
    dataset = _dataset()
    dataset.append(dict(dataset[0]))

    exit_code, output = _run(tmp_path, dataset=dataset)

    assert exit_code != 0
    assert not output.exists()


def test_case_without_usable_case_id_refuses(tmp_path) -> None:
    dataset = [{"query": "synthetic case without any stable identifier"}]

    exit_code, output = _run(tmp_path, dataset=dataset)

    assert exit_code != 0
    assert not output.exists()


def test_unanswerable_case_builds_with_canonical_empty_qrels(tmp_path) -> None:
    dataset = _dataset()
    dataset.append(
        {
            "query_id": "synthetic-unanswerable-case",
            "query": "second synthetic retrieval question",
            "answerability": "unanswerable",
            "evidence_passages": [_passage()],
        }
    )

    exit_code, output = _run(tmp_path, dataset=dataset)

    assert exit_code == 0
    manifest, _ = _read_review_manifest(output)
    assert manifest["cases"]["synthetic-unanswerable-case"]["qrels_sha256"] == _canonical_sha256(
        {"case_id": "synthetic-unanswerable-case", "passages": []}
    )
    assert _review_context_parts(manifest, dataset) is not None


def test_document_source_hash_claim_mismatch_refuses(tmp_path) -> None:
    corpus = _corpus()
    corpus["documents"][_DOCUMENT_ID] = {
        "source_id": _SOURCE_ID,
        "content": _DOCUMENT_CONTENT,
        "source_sha256": "f" * 64,
    }

    exit_code, output = _run(tmp_path, corpus=corpus)

    assert exit_code != 0
    assert not output.exists()


def test_explicit_null_source_hash_claim_refuses(tmp_path) -> None:
    corpus = _corpus()
    corpus["documents"][_DOCUMENT_ID] = {
        "source_id": _SOURCE_ID,
        "content": _DOCUMENT_CONTENT,
        "source_sha256": None,
    }

    exit_code, output = _run(tmp_path, corpus=corpus)

    assert exit_code != 0
    assert not output.exists()


def test_fingerprint_is_embedded_verbatim_and_bad_hex_refuses(tmp_path) -> None:
    exit_code, output = _run(tmp_path, fingerprint="b" * 64)

    assert exit_code == 0
    manifest, _ = _read_review_manifest(output)
    assert manifest["index_snapshot_fingerprint"] == "b" * 64

    for bad_fingerprint in ("z" * 64, "a" * 63):
        refused_code, refused_output = _run(
            tmp_path, fingerprint=bad_fingerprint, output_name="bad.json"
        )
        assert refused_code != 0
        assert not refused_output.exists()


def test_oversized_input_refuses(tmp_path) -> None:
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_bytes(json.dumps(_dataset()).encode("utf-8") + b" " * (16 * 1024 * 1024))
    output = tmp_path / "manifest.json"

    exit_code = tool.main(
        [
            "--dataset",
            str(dataset_path),
            "--corpus",
            str(_write_json(tmp_path / "corpus.json", _corpus())),
            "--reviewer-id",
            _REVIEWER_ID,
            "--manifest-id",
            "synthetic-review-manifest",
            "--output",
            str(output),
        ]
    )

    assert exit_code != 0
    assert not output.exists()


def test_output_aliasing_an_input_refuses_and_preserves_the_input(tmp_path, capsys) -> None:
    dataset_path = _write_json(tmp_path / "dataset.json", _dataset())
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    dataset_bytes = dataset_path.read_bytes()
    corpus_bytes = corpus_path.read_bytes()
    hard_link = tmp_path / "hardlink-alias.json"
    os.link(dataset_path, hard_link)

    for output_path, original_bytes in (
        (dataset_path, dataset_bytes),
        (corpus_path, corpus_bytes),
        (hard_link, dataset_bytes),
    ):
        exit_code = tool.main(
            [
                "--dataset",
                str(dataset_path),
                "--corpus",
                str(corpus_path),
                "--reviewer-id",
                _REVIEWER_ID,
                "--manifest-id",
                "synthetic-review-manifest",
                "--output",
                str(output_path),
            ]
        )

        assert exit_code != 0
        assert output_path.read_bytes() == original_bytes
        assert "must not overwrite" in capsys.readouterr().err
    assert not list(tmp_path.glob(".review-manifest-*"))


def test_pre_write_self_check_failure_writes_no_output(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(tool, "_review_context_parts", lambda manifest, dataset: None)

    exit_code, output = _run(tmp_path)

    assert exit_code != 0
    assert not output.exists()
    assert "self-check failed" in capsys.readouterr().err


def test_read_back_different_manifest_deletes_output_and_refuses(
    tmp_path, capsys, monkeypatch
) -> None:
    real_read = tool._read_review_manifest

    def read_tampered(path: Path) -> tuple[dict[str, Any], str]:
        manifest, digest = real_read(path)
        return dict(manifest, manifest_id="tampered-after-write"), digest

    monkeypatch.setattr(tool, "_read_review_manifest", read_tampered)

    exit_code, output = _run(tmp_path)

    assert exit_code != 0
    assert not output.exists()
    assert "failed verification after write" in capsys.readouterr().err


def test_read_back_digest_mismatch_deletes_output_and_refuses(
    tmp_path, capsys, monkeypatch
) -> None:
    real_read = tool._read_review_manifest

    def read_wrong_digest(path: Path) -> tuple[dict[str, Any], str]:
        manifest, _ = real_read(path)
        return manifest, "0" * 64

    monkeypatch.setattr(tool, "_read_review_manifest", read_wrong_digest)

    exit_code, output = _run(tmp_path)

    assert exit_code != 0
    assert not output.exists()
    assert "failed verification after write" in capsys.readouterr().err


def test_symlinked_input_refuses(tmp_path) -> None:
    real_dataset = _write_json(tmp_path / "real-dataset.json", _dataset())
    link = tmp_path / "dataset.json"
    link.symlink_to(real_dataset)
    output = tmp_path / "manifest.json"

    exit_code = tool.main(
        [
            "--dataset",
            str(link),
            "--corpus",
            str(_write_json(tmp_path / "corpus.json", _corpus())),
            "--reviewer-id",
            _REVIEWER_ID,
            "--manifest-id",
            "synthetic-review-manifest",
            "--output",
            str(output),
        ]
    )

    assert exit_code != 0
    assert not output.exists()


def test_duplicate_json_keys_refuse(tmp_path) -> None:
    exit_code, output = _run(tmp_path, corpus_raw='{"sources": {}, "sources": {}, "documents": {}}')

    assert exit_code != 0
    assert not output.exists()


@pytest.mark.parametrize(
    "overrides",
    [{"reviewer_id": "   "}, {"manifest_id": ""}],
    ids=["whitespace_reviewer_id", "empty_manifest_id"],
)
def test_empty_reviewer_or_manifest_id_refuses(tmp_path, overrides) -> None:
    exit_code, output = _run(tmp_path, **overrides)

    assert exit_code != 0
    assert not output.exists()


def test_output_carries_no_identity_beyond_per_case_reviewer_id(tmp_path) -> None:
    exit_code, output = _run(tmp_path)

    assert exit_code == 0
    manifest, _ = _read_review_manifest(output)
    assert list(manifest["cases"]) == [_CASE_ID]
    assert manifest["cases"][_CASE_ID] == {
        "review_status": "human_reviewed",
        "reviewer_id": _REVIEWER_ID,
        "qrels_sha256": manifest["cases"][_CASE_ID]["qrels_sha256"],
    }
    assert set(manifest["attestations"]) == {"schema_version", "records", "content_sha256"}
    assert manifest["attestations"]["schema_version"] == 1
    assert set(manifest["attestations"]["records"]) == {_CASE_ID}
    # The reviewer identifier appears exactly once: inside its single case
    # entry. Attestation records carry hashes only, never plain identity.
    assert output.read_bytes().count(_REVIEWER_ID.encode("utf-8")) == 1
