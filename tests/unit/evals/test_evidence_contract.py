from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.evals.assessment.retrieval_eval import (
    RETRIEVAL_METRIC_CONTRACT_VERSION,
    _retrieved_evidence_scores,
    evaluate_retrieval,
)
from src.evals.dataset_builder import build_retrieval_dataset, normalize_golden_queries
from src.evals.metrics._utils import finite_mean


class _Trace:
    def __init__(self, docs):
        self.retrieval = SimpleNamespace(documents=docs, score_weights={})
        self.total_time_ms = 1.0

    def model_dump(self):
        return {"total_time_ms": self.total_time_ms}


def _reviewed_case(query: str, passages: list[dict], **kwargs) -> dict:
    return {
        "query_id": query,
        "query": query,
        "label_origin": "human_reviewed",
        "review_status": "human_reviewed",
        "answerability": "answerable",
        "evidence_passages": passages,
        **kwargs,
    }


def _digest(value) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _trusted_review_context(dataset: list[dict], docs: list[dict]) -> dict:
    quotes = [
        passage["quote"]
        for case in dataset
        for passage in case.get("evidence_passages", [])
        if isinstance(passage.get("quote"), str)
    ]
    source_content = " ".join(quotes)
    source_hash = hashlib.sha256(source_content.encode("utf-8")).hexdigest()
    source_id = "frozen-source-1"
    for case in dataset:
        for passage in case.get("evidence_passages", []):
            passage["source_id"] = source_id
            passage["source_sha256"] = source_hash
    frozen_sources = {source_id: {"source_sha256": source_hash, "content": source_content}}
    frozen_documents = {
        doc["id"]: {
            "source_id": source_id,
            "source_sha256": source_hash,
            "content_sha256": hashlib.sha256(doc["content"].encode("utf-8")).hexdigest(),
        }
        for doc in docs
    }
    cases = {}
    for item in dataset:
        case_id = item.get("query_id") or item.get("case_id")
        passages = [
            {
                "passage_id": passage["passage_id"],
                "grade": passage.get("relevance_grade", passage.get("grade")),
                "quote": passage["quote"],
                "source_id": passage["source_id"],
                "source_sha256": passage["source_sha256"],
            }
            for passage in item.get("evidence_passages", [])
        ]
        cases[case_id] = {
            "review_status": "human_reviewed",
            "reviewer_id": "reviewer-1",
            "qrels_sha256": _digest(
                {
                    "case_id": case_id,
                    "passages": sorted(passages, key=lambda passage: passage["passage_id"]),
                }
            ),
        }
    return {
        "schema_version": 1,
        "manifest_id": "offline-review-manifest-v1",
        "dataset_sha256": _digest(dataset),
        "corpus_sha256": _digest(
            {"frozen_sources": frozen_sources, "frozen_documents": frozen_documents}
        ),
        "frozen_sources": frozen_sources,
        "frozen_documents": frozen_documents,
        "cases": cases,
    }


def test_same_source_irrelevant_text_is_only_a_proxy(monkeypatch):
    import src.rag.runtime as runtime

    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda query, top_k=5, retrieval_options=None: (
            "context",
            ["guideline.pdf"],
            _Trace([{"id": "irrelevant", "source": "guideline.pdf", "content": "unrelated text"}]),
        ),
    )
    rows, aggregate = evaluate_retrieval(
        [
            _reviewed_case(
                "q",
                [{"passage_id": "p1", "quote": "answer-bearing quote", "relevance_grade": 2}],
                expected_sources=["guideline"],
            )
        ],
        top_k=3,
    )

    assert rows[0]["case_status"] == "excluded"
    assert rows[0]["metrics"]["evidence_hit_rate_at_k"] is None
    assert rows[0]["metrics"]["evidence_precision_at_k"] is None
    assert rows[0]["metrics"]["precision_at_k"] is None
    assert "legacy_returned_precision_proxy" in rows[0]["metrics"]
    assert aggregate["source_family_hit_rate_proxy"] == 1.0
    assert aggregate["retrieval_metric_contract_version"] == RETRIEVAL_METRIC_CONTRACT_VERSION


def test_forged_dataset_review_flags_do_not_qualify_without_out_of_band_context(monkeypatch):
    import src.rag.runtime as runtime

    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda query, top_k=5, retrieval_options=None: (
            "context",
            ["guide.pdf"],
            _Trace([{"id": "c1", "source": "guide.pdf", "content": "quoted evidence"}]),
        ),
    )
    case = _reviewed_case(
        "forged",
        [{"passage_id": "p1", "quote": "quoted evidence", "grade": 2}],
        expected_sources=["guide.pdf"],
    )

    rows, aggregate = evaluate_retrieval([case], top_k=2)

    assert rows[0]["case_status"] == "excluded"
    assert rows[0]["exclusion_reason"] == "trusted_review_context_missing_or_invalid"
    assert rows[0]["metrics"]["hit_rate_at_k"] is None
    assert rows[0]["metrics"]["mrr"] is None
    assert aggregate["retrieval_measured_case_count"] == 0
    assert aggregate["hit_rate_at_k"] is None
    assert aggregate["mrr"] is None


def test_trusted_manifest_requires_exact_quote_in_frozen_retrieved_chunk(monkeypatch):
    import src.rag.runtime as runtime

    case = _reviewed_case(
        "trusted",
        [{"passage_id": "p1", "quote": "quoted evidence", "grade": 2}],
    )
    doc = {
        "id": "c1",
        "source": "guide.pdf",
        "content": "unrelated content",
        "metadata": {"evidence_passage_id": "p1"},
    }
    review_context = _trusted_review_context([case], [doc])
    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda query, top_k=5, retrieval_options=None: ("context", ["guide.pdf"], _Trace([doc])),
    )

    rows, aggregate = evaluate_retrieval([case], top_k=2, review_context=review_context)

    assert rows[0]["case_status"] == "measured"
    assert rows[0]["metrics"]["evidence_hit_rate_at_k"] == 0.0
    assert aggregate["retrieval_measured_case_count"] == 1


def test_unmapped_retrieved_document_makes_evidence_unmeasured(monkeypatch):
    import src.rag.runtime as runtime

    case = _reviewed_case(
        "missing-map",
        [{"passage_id": "p1", "quote": "quoted evidence", "grade": 2}],
    )
    mapped_doc = {"id": "mapped", "content": "quoted evidence"}
    review_context = _trusted_review_context([case], [mapped_doc])
    actual_doc = {"id": "not-in-frozen-map", "content": "unrelated content"}
    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda query, top_k=5, retrieval_options=None: ("context", [], _Trace([actual_doc])),
    )

    rows, aggregate = evaluate_retrieval([case], top_k=2, review_context=review_context)

    assert rows[0]["case_status"] == "excluded"
    assert rows[0]["exclusion_reason"] == "retrieved_document_provenance_missing"
    assert aggregate["retrieval_measured_case_count"] == 0
    assert aggregate["evidence_hit_rate_at_k"] is None


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("relevance_grade", 3),
        ("source_sha256", "f" * 64),
        ("quote", "tampered quote"),
    ],
)
def test_qrel_source_or_quote_tampering_invalidates_review_binding(monkeypatch, field, replacement):
    import src.rag.runtime as runtime

    case = _reviewed_case(
        "tampered",
        [{"passage_id": "p1", "quote": "quoted evidence", "grade": 2}],
    )
    doc = {"id": "c1", "content": "quoted evidence"}
    review_context = _trusted_review_context([case], [doc])
    case["evidence_passages"][0][field] = replacement
    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda query, top_k=5, retrieval_options=None: ("context", [], _Trace([doc])),
    )

    rows, aggregate = evaluate_retrieval([case], top_k=2, review_context=review_context)

    assert rows[0]["case_status"] == "excluded"
    assert aggregate["retrieval_measured_case_count"] == 0
    assert aggregate["evidence_hit_rate_at_k"] is None


def test_duplicate_chunks_for_one_passage_do_not_inflate_evidence_recall():
    source_hash = hashlib.sha256(b"unique evidence quote").hexdigest()
    scores = _retrieved_evidence_scores(
        [
            {"id": "c1", "content": "unique evidence quote"},
            {"id": "c2", "content": "unique evidence quote"},
        ],
        {
            "p1": {
                "grade": 2,
                "quote": "unique evidence quote",
                "source_id": "source-1",
                "source_sha256": source_hash,
            }
        },
        3,
        {
            chunk_id: {
                "source_id": "source-1",
                "source_sha256": source_hash,
                "content_sha256": hashlib.sha256(b"unique evidence quote").hexdigest(),
            }
            for chunk_id in ("c1", "c2")
        },
    )
    assert scores["evidence_recall_at_k"] == 1.0
    assert scores["evidence_precision_at_k"] == pytest.approx(1 / 3)
    assert scores["evidence_ndcg_at_k"] == 1.0


def test_ndcg_ideal_uses_judged_evidence_missing_from_results():
    source_hash = hashlib.sha256(b"unretrieved high-grade quote lower-grade quote").hexdigest()
    scores = _retrieved_evidence_scores(
        [{"id": "c1", "content": "lower-grade quote"}],
        {
            "high": {
                "grade": 3,
                "quote": "unretrieved high-grade quote",
                "source_id": "source-1",
                "source_sha256": source_hash,
            },
            "low": {
                "grade": 1,
                "quote": "lower-grade quote",
                "source_id": "source-1",
                "source_sha256": source_hash,
            },
        },
        2,
        {
            "c1": {
                "source_id": "source-1",
                "source_sha256": source_hash,
                "content_sha256": hashlib.sha256(b"lower-grade quote").hexdigest(),
            }
        },
    )
    assert scores["evidence_ndcg_at_k"] == pytest.approx(1 / (7 + 1 / math.log2(3)))
    assert scores["evidence_ndcg_at_k"] < 1.0


def test_unanswerable_rows_have_n_a_ranking_metrics(monkeypatch):
    import src.rag.runtime as runtime

    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda query, top_k=5, retrieval_options=None: ("", [], _Trace([])),
    )
    rows, aggregate = evaluate_retrieval(
        [{"query_id": "u", "query": "unknown", "answerability": "unanswerable"}],
        top_k=2,
    )
    assert rows[0]["case_status"] == "excluded"
    assert rows[0]["metrics"]["evidence_ndcg_at_k"] is None
    assert aggregate["retrieval_excluded_case_count"] == 1
    assert aggregate["evidence_ndcg_at_k"] is None


def test_case_failure_is_isolated_and_sdk_message_is_not_returned(monkeypatch):
    import src.rag.runtime as runtime

    def retrieve(query, top_k=5, retrieval_options=None):
        if query == "bad":
            raise RuntimeError("private raw sdk response")
        return "", [], _Trace([{"id": "c", "content": "quoted evidence"}])

    monkeypatch.setattr(runtime, "retrieve_context_with_trace", retrieve)
    cases = [
        _reviewed_case("bad", [{"passage_id": "p1", "quote": "quoted evidence", "grade": 1}]),
        _reviewed_case("good", [{"passage_id": "p2", "quote": "quoted evidence", "grade": 1}]),
    ]
    review_context = _trusted_review_context(cases, [{"id": "c", "content": "quoted evidence"}])
    rows, aggregate = evaluate_retrieval(cases, top_k=2, review_context=review_context)

    assert [row["case_status"] for row in rows] == ["failed", "measured"]
    assert rows[0]["failure_type"] == "RuntimeError"
    assert aggregate["retrieval_expected_case_count"] == 2
    assert aggregate["retrieval_measured_case_count"] == 1
    assert aggregate["retrieval_failed_case_count"] == 1
    assert aggregate["retrieval_coverage"] == 0.5
    assert "private raw sdk response" not in json.dumps([rows, aggregate])


def test_invalid_boolean_grade_fails_case_and_empty_measurements_are_null(monkeypatch):
    import src.rag.runtime as runtime

    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda query, top_k=5, retrieval_options=None: ("", [], _Trace([])),
    )
    cases = [_reviewed_case("invalid", [{"passage_id": "p", "quote": "q", "grade": True}])]
    review_context = _trusted_review_context(cases, [{"id": "c", "content": "q"}])
    rows, aggregate = evaluate_retrieval(cases, top_k=2, review_context=review_context)
    assert rows[0]["case_status"] == "failed"
    assert aggregate["retrieval_measured_case_count"] == 0
    assert aggregate["evidence_recall_at_k"] is None
    assert finite_mean([]) is None
    with pytest.raises(ValueError, match="finite"):
        finite_mean([float("nan")])
    with pytest.raises(ValueError, match="finite"):
        finite_mean([True])


def test_nonfinite_trace_measurement_fails_case_without_poisoning_aggregate(monkeypatch):
    import src.rag.runtime as runtime

    trace = _Trace([])
    trace.total_time_ms = float("inf")
    monkeypatch.setattr(
        runtime,
        "retrieve_context_with_trace",
        lambda query, top_k=5, retrieval_options=None: ("", [], trace),
    )
    rows, aggregate = evaluate_retrieval([{"query_id": "bad-time", "query": "q"}], top_k=2)

    assert rows[0]["case_status"] == "failed"
    assert rows[0]["failure_type"] == "ValueError"
    assert aggregate["retrieval_failed_case_count"] == 1
    assert aggregate["latency_p50_ms"] is None


def test_benchmark_dataset_is_frozen_and_reports_overlap(tmp_path, monkeypatch):
    data_path = tmp_path / "cases.json"
    data_path.write_text(
        json.dumps(
            {
                "dataset_id": "frozen-test",
                "schema_version": "1.0",
                "dataset_origin": "synthetic_test",
                "cases": [
                    {
                        "case_id": "a",
                        "query": "same query",
                        "source_family": "fam",
                        "dataset_split": "dev",
                    },
                    {
                        "case_id": "b",
                        "query": "same query",
                        "source_family": "fam",
                        "dataset_split": "test",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.evals.dataset_builder._bootstrap_precise_labels",
        lambda records: pytest.fail("benchmark must not bootstrap labels"),
    )
    monkeypatch.setattr(
        "src.evals.dataset_builder._try_generate_synthetic_questions",
        lambda **kwargs: pytest.fail("benchmark must not generate cases"),
    )

    bundle = build_retrieval_dataset(
        dataset_path=data_path,
        benchmark_mode=True,
        enable_llm_generation=False,
    )
    assert [item["query_id"] for item in bundle["dataset"]] == ["a", "b"]
    assert bundle["stats"]["duplicate_query_group_count"] == 1
    assert bundle["stats"]["duplicate_query_detection"] == "normalized_exact_only"
    assert bundle["stats"]["near_duplicate_query_status"] == "not_assessed"
    assert bundle["stats"]["source_family_overlap_count"] == 1
    assert all(item["review_status"] == "unreviewed" for item in bundle["dataset"])
    assert bundle["stats"]["dataset_mode"] == "benchmark"


def test_benchmark_rejects_generation_and_case_ids_are_stable(tmp_path):
    data_path = tmp_path / "golden.json"
    data_path.write_text(
        json.dumps(
            {"golden_queries": [{"query": "stable question", "expected_sources": ["Guide"]}]}
        ),
        encoding="utf-8",
    )
    first = normalize_golden_queries(data_path)
    second = normalize_golden_queries(data_path)
    assert first[0]["query_id"] == second[0]["query_id"]
    assert first[0]["dataset_split"] == second[0]["dataset_split"]
    assert first[0]["label_origin"] == "heuristic"
    assert first[0]["review_status"] == "unreviewed"
    with pytest.raises(ValueError, match="forbids synthetic generation"):
        build_retrieval_dataset(
            dataset_path=data_path,
            benchmark_mode=True,
            enable_llm_generation=True,
        )


def test_versioned_synthetic_wiring_fixture_is_explicitly_unreviewed():
    from src.evals.dataset_builder import _normalize_cached_dataset

    fixture = _normalize_cached_dataset(
        Path("tests/fixtures/evals/phase123/retrieval-cases.v1.json")
    )
    assert len(fixture) == 4
    assert {case["dataset_version"] for case in fixture} == {"1.0"}
    assert {case["dataset_id"] for case in fixture} == {"phase123-evidence-contract-wiring"}
    assert {case["label_origin"] for case in fixture} == {"synthetic"}
    assert {case["review_status"] for case in fixture} == {"unreviewed"}
    assert {case["dataset_split"] for case in fixture} == {"test", "regression", "dev"}
