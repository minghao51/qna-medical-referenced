"""Retrieval evaluation helpers and sweeps."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from typing import Any
from uuid import uuid4

from src.evals.metrics import (
    hit_rate_at_k,
    ndcg_at_k,
    percentile,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from src.evals.metrics._utils import (
    finite_mean,
    ndcg_from_qrels_at_k,
    precision_at_k_slots,
)
from src.infra.telemetry import ErrorCode, Operation, Stage, telemetry_operation

logger = logging.getLogger(__name__)

RETRIEVAL_METRIC_CONTRACT_VERSION = "evidence-qrels-v2"


def normalize_source_label(source: str) -> str:
    return source.lower().replace(".pdf", "").replace(".md", "").replace(".html", "")


def flatten_source_text(source: Any) -> str:
    if isinstance(source, str):
        return source
    if hasattr(source, "model_dump"):
        source = source.model_dump()
    if isinstance(source, dict):
        parts = [source.get("label"), source.get("source"), source.get("url")]
        return " ".join(str(part) for part in parts if part)
    return str(source)


def source_type_from_name(name: str) -> str:
    lowered = str(name).lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if lowered.endswith(".csv"):
        return "csv"
    if lowered.endswith((".html", ".md")):
        return "html"
    return "other"


def expected_source_type_for_item(item: dict[str, Any]) -> str:
    explicit = item.get("target_source_type")
    if explicit:
        return str(explicit)
    expected = item.get("expected_source_types") or []
    if expected:
        return str(expected[0])
    for src in item.get("expected_sources") or []:
        st = source_type_from_name(str(src))
        if st != "other":
            return st
    return "unknown"


def _sources_match(doc_source_normalized: str, expected_sources: list[str]) -> bool:
    for es in expected_sources:
        es_norm = normalize_source_label(es)
        if doc_source_normalized == es_norm:
            return True
        es_family = re.sub(r"[^a-z0-9]+", " ", es_norm).strip().split()[:3]
        doc_family = re.sub(r"[^a-z0-9]+", " ", doc_source_normalized).strip().split()[:3]
        if es_family and es_family == doc_family:
            return True
    return False


def doc_is_relevant(doc: dict[str, Any], item: dict[str, Any]) -> bool:
    """Legacy source/keyword heuristic; diagnostic proxy, not evidence relevance."""
    source = normalize_source_label(str(doc.get("source", "")))
    content = str(doc.get("content", "")).lower()
    expected_sources = [str(s).lower() for s in item.get("expected_sources") or []]
    expected_keywords = [str(k).lower() for k in item.get("expected_keywords") or []]
    evidence_phrase = str(item.get("evidence_phrase", "")).strip().lower()
    if expected_sources and _sources_match(source, expected_sources):
        return True
    if evidence_phrase and evidence_phrase in content:
        return True
    if expected_keywords:
        overlap = sum(
            1
            for kw in expected_keywords
            if kw and re.search(r"\b" + re.escape(kw) + r"\b", content)
        )
        return overlap >= min(2, max(1, len(expected_keywords)))
    return False


def graded_relevance(doc: dict[str, Any], item: dict[str, Any]) -> int:
    """Legacy source/keyword heuristic; diagnostic proxy, not independently judged."""
    source = normalize_source_label(str(doc.get("source", "")))
    content = str(doc.get("content", "")).lower()
    expected_sources = [str(s).lower() for s in item.get("expected_sources") or []]
    expected_keywords = [str(k).lower() for k in item.get("expected_keywords") or []]
    evidence_phrase = str(item.get("evidence_phrase", "")).strip().lower()
    source_match = expected_sources and _sources_match(source, expected_sources)
    keyword_overlap = (
        sum(
            1
            for kw in expected_keywords
            if kw and re.search(r"\b" + re.escape(kw) + r"\b", content)
        )
        if expected_keywords
        else 0
    )
    evidence_match = bool(evidence_phrase and evidence_phrase in content)
    exact_chunk_id = item.get("expected_chunk_id")
    chunk_match = exact_chunk_id and str(doc.get("id")) == str(exact_chunk_id)
    if source_match and chunk_match and keyword_overlap >= 2:
        return 3
    if source_match and keyword_overlap >= 2:
        return 3
    if source_match and keyword_overlap >= 1:
        return 2
    if source_match or (keyword_overlap >= 2):
        return 2
    if evidence_match or keyword_overlap >= 1:
        return 1
    return 0


def graded_ndcg_at_k(graded_rels: list[int], k: int | None = None) -> float:
    """Legacy keyword/source heuristic retained for diagnostic compatibility only."""
    import math

    rel = graded_rels[:k] if k else list(graded_rels)
    if not rel:
        return 0.0
    dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rel))
    ideal = sorted(rel, reverse=True)
    idcg = sum(r / math.log2(i + 2) for i, r in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def _is_unanswerable(item: dict[str, Any]) -> bool:
    answerability = item.get("answerability", item.get("is_answerable", "answerable"))
    return answerability is False or str(answerability).casefold() in {
        "unanswerable",
        "no_evidence",
        "not_answerable",
    }


def _canonical_sha256(value: Any) -> str | None:
    try:
        payload = json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _normalize_evidence_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).casefold().strip()


def _review_context_base_parts(
    review_context: dict[str, Any] | None, dataset: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    """Validate existing dataset/corpus bindings, not reviewer identity or qualifications."""
    if not isinstance(review_context, dict) or review_context.get("schema_version") != 1:
        return None
    manifest_id = review_context.get("manifest_id")
    if not isinstance(manifest_id, str) or not manifest_id.strip():
        return None
    if not _is_sha256(review_context.get("dataset_sha256")):
        return None
    if review_context["dataset_sha256"] != _canonical_sha256(dataset):
        return None

    sources = review_context.get("frozen_sources")
    documents = review_context.get("frozen_documents")
    cases = review_context.get("cases")
    if (
        not isinstance(sources, dict)
        or not isinstance(documents, dict)
        or not isinstance(cases, dict)
    ):
        return None
    if not _is_sha256(review_context.get("corpus_sha256")):
        return None
    if review_context["corpus_sha256"] != _canonical_sha256(
        {"frozen_sources": sources, "frozen_documents": documents}
    ):
        return None

    for source_id, source in sources.items():
        if not isinstance(source_id, str) or not isinstance(source, dict):
            return None
        content = source.get("content")
        source_hash = source.get("source_sha256")
        if not isinstance(content, str) or not _is_sha256(source_hash):
            return None
        if hashlib.sha256(content.encode("utf-8")).hexdigest() != source_hash:
            return None
    for document_id, document in documents.items():
        if not isinstance(document_id, str) or not isinstance(document, dict):
            return None
        source_id = document.get("source_id")
        if not isinstance(source_id, str) or source_id not in sources:
            return None
        if document.get("source_sha256") != sources[source_id].get("source_sha256"):
            return None
        if not _is_sha256(document.get("content_sha256")):
            return None
    for case_id, case in cases.items():
        if (
            not isinstance(case_id, str)
            or not isinstance(case, dict)
            or case.get("review_status") != "human_reviewed"
            or not isinstance(case.get("reviewer_id"), str)
            or not case["reviewer_id"].strip()
            or not _is_sha256(case.get("qrels_sha256"))
        ):
            return None
    return cases, sources, documents


def _verify_review_attestations(
    review_context: dict[str, Any], dataset: list[dict[str, Any]], cases: dict[str, Any]
) -> bool:
    attestations = review_context.get("attestations")
    if (
        not isinstance(attestations, dict)
        or set(attestations) != {"schema_version", "records", "content_sha256"}
        or isinstance(attestations.get("schema_version"), bool)
        or attestations.get("schema_version") != 1
    ):
        return False
    records = attestations.get("records")
    content_sha256 = attestations.get("content_sha256")
    if (
        not isinstance(records, dict)
        or set(records) != set(cases)
        or not _is_sha256(content_sha256)
    ):
        return False

    dataset_cases: dict[str, dict[str, Any]] = {}
    for item in dataset:
        case_id = item.get("query_id") or item.get("case_id")
        if isinstance(case_id, str) and case_id.strip():
            if case_id in dataset_cases:
                # A colliding record key cannot authenticate two different case records.
                return False
            dataset_cases[case_id] = item

    for case_id, review_case in cases.items():
        dataset_case = dataset_cases.get(case_id)
        if dataset_case is None:
            return False
        expected_record_hash = _canonical_sha256(
            {"dataset_case": dataset_case, "review_case": review_case}
        )
        record_hash = records.get(case_id)
        if not _is_sha256(record_hash) or record_hash != expected_record_hash:
            return False

    expected_content_hash = _canonical_sha256({"schema_version": 1, "records": records})
    return _is_sha256(expected_content_hash) and content_sha256 == expected_content_hash


def _review_context_parts(
    review_context: dict[str, Any] | None, dataset: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    """Validate content bindings and optional attestations, never reviewer identity."""
    parts = _review_context_base_parts(review_context, dataset)
    if parts is None:
        return None
    if isinstance(review_context, dict) and "attestations" in review_context:
        cases, _, _ = parts
        if not _verify_review_attestations(review_context, dataset, cases):
            return None
    return parts


def _review_manifest_hash_verification_failed(
    review_context: dict[str, Any] | None,
    dataset: list[dict[str, Any]],
    base_parts: tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None,
) -> bool:
    if not isinstance(review_context, dict) or "attestations" not in review_context:
        return False
    return base_parts is not None and not _verify_review_attestations(
        review_context, dataset, base_parts[0]
    )


def _review_manifest_authority_status_from_parts(
    review_context: dict[str, Any] | None,
    parts: tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None,
) -> str:
    if review_context is None or parts is None:
        return "unavailable"
    if "attestations" in review_context:
        return "manifest_hash_verified_not_identity_authenticated"
    return "manifest_asserted_not_authenticated"


def review_manifest_authority_status(
    review_context: dict[str, Any] | None, dataset: list[dict[str, Any]] | None
) -> str | None:
    """Report content consistency, without asserting reviewer identity or qualifications."""
    if review_context is None or dataset is None or not isinstance(review_context, dict):
        return None
    return _review_manifest_authority_status_from_parts(
        review_context, _review_context_parts(review_context, dataset)
    )


def _reviewed_evidence_qrels(
    item: dict[str, Any], review_case: dict[str, Any] | None, frozen_sources: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Return qrels only when the trusted manifest binds them to frozen source evidence."""
    if _is_unanswerable(item) or not isinstance(review_case, dict):
        return {}
    passages = item.get("evidence_passages")
    if not isinstance(passages, list) or not passages:
        return {}

    qrels: dict[str, dict[str, Any]] = {}
    for passage in passages:
        if not isinstance(passage, dict):
            raise ValueError("evidence judgments must be objects")
        passage_id = str(passage.get("passage_id") or passage.get("evidence_id") or "").strip()
        grade = passage.get("relevance_grade", passage.get("grade", passage.get("relevance")))
        if not passage_id:
            raise ValueError("evidence judgments require a stable passage_id")
        if isinstance(grade, bool) or not isinstance(grade, int) or grade < 0:
            raise ValueError("evidence relevance grades must be non-negative integers")
        if passage_id in qrels:
            raise ValueError("evidence passage IDs must be unique within a case")
        quote = passage.get("quote")
        source_id = passage.get("source_id")
        source_sha256 = passage.get("source_sha256")
        source = frozen_sources.get(source_id) if isinstance(source_id, str) else None
        if (
            not isinstance(quote, str)
            or not quote.strip()
            or not isinstance(source, dict)
            or source.get("source_sha256") != source_sha256
            or _normalize_evidence_text(quote)
            not in _normalize_evidence_text(str(source.get("content", "")))
        ):
            return {}
        qrels[passage_id] = {
            "grade": grade,
            "quote": quote,
            "source_id": source_id,
            "source_sha256": source_sha256,
        }

    case_id = str(item.get("query_id") or item.get("case_id") or "").strip()
    canonical_qrels = {
        "case_id": case_id,
        "passages": [
            {"passage_id": passage_id, **qrels[passage_id]} for passage_id in sorted(qrels)
        ],
    }
    if not case_id or review_case.get("qrels_sha256") != _canonical_sha256(canonical_qrels):
        return {}
    return qrels


def _retrieved_evidence_scores(
    docs: list[dict[str, Any]],
    qrels: dict[str, dict[str, Any]],
    k: int,
    frozen_documents: dict[str, Any] | None = None,
) -> dict[str, float | None]:
    empty: dict[str, float | None] = {
        "evidence_hit_rate_at_k": None,
        "evidence_precision_at_k": None,
        "evidence_recall_at_k": None,
        "evidence_ndcg_at_k": None,
        "evidence_mrr": None,
    }
    if not qrels:
        return empty
    relevant_ids = {passage_id for passage_id, qrel in qrels.items() if qrel["grade"] > 0}
    if not relevant_ids:
        return empty

    ranked_grades: list[int] = []
    ranked_binary: list[int] = []
    retrieved_relevant_ids: set[str] = set()
    seen_passages: set[str] = set()
    first_relevant_rank: int | None = None
    provenance_complete = True
    for rank, doc in enumerate(docs[:k], start=1):
        raw_metadata = doc.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        document_id = str(doc.get("id", ""))
        frozen_document = (frozen_documents or {}).get(document_id)
        content = str(doc.get("content", ""))
        if not isinstance(frozen_document, dict) or hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest() != frozen_document.get("content_sha256"):
            provenance_complete = False
            ranked_binary.append(0)
            ranked_grades.append(0)
            continue
        actual_source_id = metadata.get("source_id", doc.get("source_id"))
        actual_source_hash = metadata.get("source_sha256", doc.get("source_sha256"))
        if (
            actual_source_id is not None and actual_source_id != frozen_document.get("source_id")
        ) or (
            actual_source_hash is not None
            and actual_source_hash != frozen_document.get("source_sha256")
        ):
            provenance_complete = False
            ranked_binary.append(0)
            ranked_grades.append(0)
            continue
        matches = set()
        for passage_id, qrel in qrels.items():
            if (
                frozen_document.get("source_id") == qrel["source_id"]
                and frozen_document.get("source_sha256") == qrel["source_sha256"]
                and (actual_source_id is None or actual_source_id == qrel["source_id"])
                and (actual_source_hash is None or actual_source_hash == qrel["source_sha256"])
                and _normalize_evidence_text(qrel["quote"]) in _normalize_evidence_text(content)
            ):
                matches.add(passage_id)
        fresh = matches - seen_passages
        seen_passages.update(matches)
        relevant_fresh = fresh & relevant_ids
        retrieved_relevant_ids.update(matches & relevant_ids)
        if relevant_fresh and first_relevant_rank is None:
            first_relevant_rank = rank
        ranked_binary.append(1 if relevant_fresh else 0)
        ranked_grades.append(max((qrels[pid]["grade"] for pid in relevant_fresh), default=0))

    if not provenance_complete:
        return empty
    ideal_grades = [qrels[passage_id]["grade"] for passage_id in relevant_ids]
    return {
        "evidence_hit_rate_at_k": 1.0 if retrieved_relevant_ids else 0.0,
        "evidence_precision_at_k": precision_at_k_slots(ranked_binary, k),
        "evidence_recall_at_k": len(retrieved_relevant_ids) / len(relevant_ids),
        "evidence_ndcg_at_k": ndcg_from_qrels_at_k(ranked_grades, ideal_grades, k),
        "evidence_mrr": 1.0 / first_relevant_rank if first_relevant_rank else 0.0,
    }


def _metric_percentile(values: list[float], pct: float) -> float | None:
    return percentile(values, pct) if values else None


def _finite_metric_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def binary_unique_by_key(
    retrieved_docs: list[dict[str, Any]], item: dict[str, Any], key_fn
) -> list[int]:
    seen = set()
    out: list[int] = []
    for doc in retrieved_docs:
        key = key_fn(doc)
        if key in seen:
            continue
        seen.add(key)
        out.append(1 if doc_is_relevant(doc, item) else 0)
    return out


def evaluate_retrieval(
    dataset: list[dict[str, Any]],
    top_k: int,
    retrieval_options: dict[str, Any] | None = None,
    *,
    review_context: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from src.rag.runtime import retrieve_context_with_trace

    rows: list[dict[str, Any]] = []
    hit_values: list[float] = []
    precision_values: list[float] = []
    recall_values: list[float] = []
    mrr_values: list[float] = []
    ndcg_values: list[float] = []
    graded_ndcg_values: list[float] = []
    source_hit_values: list[float] = []
    dedup_hit_values: list[float] = []
    dedup_precision_values: list[float] = []
    dedup_mrr_values: list[float] = []
    unique_source_hit_values: list[float] = []
    unique_source_precision_values: list[float] = []
    duplicate_source_ratio_values: list[float] = []
    duplicate_doc_ratio_values: list[float] = []
    exact_chunk_hit_values: list[float] = []
    evidence_hit_proxy_values: list[float] = []
    evidence_hit_values: list[float] = []
    evidence_precision_values: list[float] = []
    evidence_recall_values: list[float] = []
    evidence_ndcg_values: list[float] = []
    evidence_mrr_values: list[float] = []
    retrieval_failed_case_count = 0
    retrieval_excluded_case_count = 0
    latencies: list[float] = []
    high_conf_hit_values: list[float] = []
    high_conf_mrr_values: list[float] = []
    high_conf_exact_chunk_values: list[float] = []
    high_conf_evidence_values: list[float] = []
    topic_false_positive_values: list[float] = []
    query_embedding_latencies: list[float] = []
    by_query_category: dict[str, list[dict[str, Any]]] = {}
    by_task_type: dict[str, list[dict[str, Any]]] = {}
    by_expected_source_type: dict[str, list[dict[str, Any]]] = {}
    by_difficulty: dict[str, list[dict[str, Any]]] = {}
    by_semantic_case: dict[str, list[dict[str, Any]]] = {}
    retrieval_contribution = {
        "semantic_ranked_hits": 0,
        "bm25_ranked_hits": 0,
        "fused_ranked_hits": 0,
    }
    hyde_queries_count = 0
    hyde_hit_values: list[float] = []
    hyde_mrr_values: list[float] = []
    hyde_source_hit_values: list[float] = []
    medical_expansion_queries_count = 0
    medical_expansion_term_counts: list[float] = []
    rerank_enabled_queries_count = 0
    rerank_timing_values: list[float] = []
    rerank_candidate_values: list[float] = []
    rerank_output_values: list[float] = []
    rerank_filtered_values: list[float] = []
    # Compute the review-context binding once; every internal consumer threads it.
    review_base_parts = _review_context_base_parts(review_context, dataset)
    review_hash_verification_failed = _review_manifest_hash_verification_failed(
        review_context, dataset, review_base_parts
    )
    review_parts = None if review_hash_verification_failed else review_base_parts
    review_cases, frozen_sources, frozen_documents = review_parts or ({}, {}, {})

    for item in dataset:
        query_id = item.get("query_id") or item.get("case_id")
        telemetry_case_id = str(uuid4())
        try:
            query = str(item.get("query", "")).strip()
            if not query:
                raise ValueError("query is required")
            case_review = review_cases.get(str(query_id)) if query_id is not None else None
            evidence_qrels = _reviewed_evidence_qrels(item, case_review, frozen_sources)
            with telemetry_operation(
                Operation.RETRIEVAL,
                case_id=telemetry_case_id,
                stage=Stage.SEARCH,
                error_code=ErrorCode.UPSTREAM,
            ):
                if retrieval_options:
                    context, sources, trace = retrieve_context_with_trace(
                        query, top_k=top_k, retrieval_options=retrieval_options
                    )
                else:
                    context, sources, trace = retrieve_context_with_trace(query, top_k=top_k)
            retrieved_docs = [
                doc.model_dump() if hasattr(doc, "model_dump") else doc
                for doc in trace.retrieval.documents
            ]
            if not all(isinstance(doc, dict) for doc in retrieved_docs):
                raise ValueError("retrieval documents must be objects")
            evidence_metrics = _retrieved_evidence_scores(
                retrieved_docs, evidence_qrels, top_k, frozen_documents
            )
            score_weights = getattr(trace.retrieval, "score_weights", {}) or {}
            if not isinstance(score_weights, dict):
                raise ValueError("retrieval score weights must be an object")
            trace_total_time_ms = _finite_metric_number(trace.total_time_ms, "total_time_ms")
            if not isinstance(context, str):
                raise ValueError("retrieval context must be a string")
            if not isinstance(sources, (list, tuple)):
                raise ValueError("retrieval sources must be a list")
            trace_payload = trace.model_dump() if hasattr(trace, "model_dump") else {}
            metric_values = {
                "query_embedding_timing_ms": _finite_metric_number(
                    score_weights.get("query_embedding_timing_ms", 0), "query_embedding_timing_ms"
                ),
                "medical_expansion_term_count": _finite_metric_number(
                    score_weights.get("medical_expansion_term_count", 0),
                    "medical_expansion_term_count",
                ),
                "rerank_timing_ms": _finite_metric_number(
                    score_weights.get("rerank_timing_ms", 0), "rerank_timing_ms"
                ),
                "rerank_candidates_reranked": _finite_metric_number(
                    score_weights.get(
                        "rerank_candidates_reranked", score_weights.get("rerank_candidates", 0)
                    ),
                    "rerank_candidates_reranked",
                ),
                "rerank_output": _finite_metric_number(
                    score_weights.get("rerank_output", 0), "rerank_output"
                ),
                "rerank_filtered_out": _finite_metric_number(
                    score_weights.get("rerank_filtered_out", 0), "rerank_filtered_out"
                ),
            }
        except Exception as exc:
            retrieval_failed_case_count += 1
            error_type = type(exc).__name__
            logger.warning(
                "Retrieval evaluation case failed: case_id=%s error_type=%s", query_id, error_type
            )
            rows.append(
                {
                    "query_id": query_id,
                    "query": item.get("query"),
                    "case_status": "failed",
                    "failure_type": error_type,
                    "metrics": {
                        "retrieval_metric_contract_version": RETRIEVAL_METRIC_CONTRACT_VERSION,
                        "case_status": "failed",
                        "evidence_hit_rate_at_k": None,
                        "evidence_precision_at_k": None,
                        "evidence_recall_at_k": None,
                        "evidence_ndcg_at_k": None,
                        "evidence_mrr": None,
                    },
                    "sources": [],
                    "retrieved_docs": [],
                    "trace": {},
                }
            )
            continue

        unanswerable = _is_unanswerable(item)
        if unanswerable:
            case_status, exclusion_reason = "excluded", "unanswerable_ranking_not_applicable"
        elif review_hash_verification_failed:
            case_status, exclusion_reason = (
                "excluded",
                "trusted_review_manifest_hash_verification_failed",
            )
        elif review_parts is None:
            case_status, exclusion_reason = "excluded", "trusted_review_context_missing_or_invalid"
        elif not isinstance(case_review, dict):
            case_status, exclusion_reason = "excluded", "case_not_in_trusted_review_manifest"
        elif not evidence_qrels:
            case_status, exclusion_reason = (
                "excluded",
                "reviewed_qrels_or_frozen_source_binding_invalid",
            )
        elif not any(qrel["grade"] > 0 for qrel in evidence_qrels.values()):
            case_status, exclusion_reason = "excluded", "no_relevant_evidence_qrels"
        elif evidence_metrics["evidence_hit_rate_at_k"] is None:
            case_status, exclusion_reason = "excluded", "retrieved_document_provenance_missing"
        else:
            case_status, exclusion_reason = "measured", None
            for metric_name, eligible_values in (
                ("evidence_hit_rate_at_k", evidence_hit_values),
                ("evidence_precision_at_k", evidence_precision_values),
                ("evidence_recall_at_k", evidence_recall_values),
                ("evidence_ndcg_at_k", evidence_ndcg_values),
                ("evidence_mrr", evidence_mrr_values),
            ):
                score = evidence_metrics[metric_name]
                if score is not None:
                    eligible_values.append(score)
        if case_status == "excluded":
            retrieval_excluded_case_count += 1

        binary_relevance = [1 if doc_is_relevant(doc, item) else 0 for doc in retrieved_docs]
        graded_rels = [graded_relevance(doc, item) for doc in retrieved_docs]
        dedup_doc_binary = binary_unique_by_key(retrieved_docs, item, lambda d: d.get("id"))
        unique_source_binary = binary_unique_by_key(
            retrieved_docs,
            item,
            lambda d: (str(d.get("source", "")), d.get("page")),
        )
        expected_sources = [str(s).lower() for s in item.get("expected_sources") or []]
        source_hit = 0.0
        if expected_sources:
            source_hit = (
                1.0
                if any(
                    any(es in flatten_source_text(source).lower() for es in expected_sources)
                    for source in sources
                )
                else 0.0
            )
        total_relevant = max(1, len(expected_sources)) if expected_sources else 1
        exact_chunk_id = item.get("expected_chunk_id")
        exact_chunk_hit = (
            1.0
            if (
                exact_chunk_id
                and any(str(doc.get("id")) == str(exact_chunk_id) for doc in retrieved_docs)
            )
            else 0.0
        )
        evidence_phrase = str(item.get("evidence_phrase", "")).strip().lower()
        evidence_hit = 0.0
        if evidence_phrase:
            evidence_hit = (
                1.0
                if any(
                    evidence_phrase in str(doc.get("content", "")).lower() for doc in retrieved_docs
                )
                else 0.0
            )
        topic_false_positive_rate = 0.0
        if retrieved_docs and expected_sources:
            mismatches = 0
            for doc in retrieved_docs:
                source_name = str(doc.get("source", "")).lower()
                if not any(es in source_name for es in expected_sources):
                    mismatches += 1
            topic_false_positive_rate = mismatches / len(retrieved_docs)
        unique_sources = {(str(doc.get("source", "")), doc.get("page")) for doc in retrieved_docs}
        unique_doc_ids = {str(doc.get("id", "")) for doc in retrieved_docs}
        duplicate_source_ratio = (
            1.0 - (len(unique_sources) / len(retrieved_docs)) if retrieved_docs else 0.0
        )
        duplicate_doc_ratio = (
            1.0 - (len(unique_doc_ids) / len(retrieved_docs)) if retrieved_docs else 0.0
        )
        legacy_hit = hit_rate_at_k(binary_relevance)
        legacy_precision = precision_at_k(binary_relevance, top_k)
        legacy_recall = recall_at_k(binary_relevance, total_relevant)
        legacy_binary_ndcg = ndcg_at_k(binary_relevance, top_k)
        legacy_graded_ndcg = graded_ndcg_at_k(graded_rels, top_k)
        mrr = reciprocal_rank(binary_relevance)
        dedup_hit = hit_rate_at_k(dedup_doc_binary)
        dedup_precision = precision_at_k_slots(dedup_doc_binary, top_k)
        dedup_mrr = reciprocal_rank(dedup_doc_binary)
        unique_source_hit = hit_rate_at_k(unique_source_binary)
        unique_source_precision = precision_at_k_slots(unique_source_binary, top_k)
        row_metrics = {
            "retrieval_metric_contract_version": RETRIEVAL_METRIC_CONTRACT_VERSION,
            "case_status": case_status,
            "exclusion_reason": exclusion_reason,
            "evidence_hit_rate_at_k": evidence_metrics["evidence_hit_rate_at_k"],
            "evidence_precision_at_k": evidence_metrics["evidence_precision_at_k"],
            "evidence_recall_at_k": evidence_metrics["evidence_recall_at_k"],
            "evidence_ndcg_at_k": evidence_metrics["evidence_ndcg_at_k"],
            "evidence_mrr": evidence_metrics["evidence_mrr"],
            "hit_rate_at_k": evidence_metrics["evidence_hit_rate_at_k"],
            "precision_at_k": evidence_metrics["evidence_precision_at_k"],
            "recall_at_k": evidence_metrics["evidence_recall_at_k"],
            "ndcg_at_k": evidence_metrics["evidence_ndcg_at_k"],
            "graded_ndcg_at_k": evidence_metrics["evidence_ndcg_at_k"],
            "legacy_heuristic_hit_rate_proxy": legacy_hit,
            "legacy_returned_precision_proxy": legacy_precision,
            "legacy_expected_source_recall_proxy": legacy_recall,
            "legacy_binary_ndcg_proxy": legacy_binary_ndcg,
            "legacy_heuristic_graded_ndcg_at_k_proxy": legacy_graded_ndcg,
            "mrr": evidence_metrics["evidence_mrr"],
            "source_keyword_mrr_proxy": mrr,
            "source_hit": source_hit,
            "source_family_hit_rate_proxy": source_hit,
            "dedup_hit_rate_at_k": dedup_hit,
            "dedup_precision_at_k": dedup_precision,
            "dedup_mrr": dedup_mrr,
            "unique_source_hit_rate_at_k": unique_source_hit,
            "unique_source_precision_at_k": unique_source_precision,
            "duplicate_source_ratio": duplicate_source_ratio,
            "duplicate_doc_ratio": duplicate_doc_ratio,
            "exact_chunk_hit": exact_chunk_hit,
            "evidence_hit": evidence_hit,
            "evidence_phrase_hit_proxy": evidence_hit,
            "topic_false_positive_rate": topic_false_positive_rate,
            "hyde_enabled": bool(score_weights.get("hyde_enabled", False)),
            "medical_expansion_enabled": bool(score_weights.get("enable_medical_expansion", False)),
            "medical_expansion_term_count": metric_values["medical_expansion_term_count"],
            "reranking_enabled": bool(score_weights.get("enable_reranking", False)),
            "rerank_timing_ms": metric_values["rerank_timing_ms"],
            "rerank_candidates_reranked": metric_values["rerank_candidates_reranked"],
            "rerank_output": metric_values["rerank_output"],
            "rerank_filtered_out": metric_values["rerank_filtered_out"],
        }
        if item.get("label_confidence") == "high" and case_status == "measured":
            high_conf_hit = evidence_metrics["evidence_hit_rate_at_k"]
            if high_conf_hit is not None:
                high_conf_hit_values.append(high_conf_hit)
            high_conf_mrr = evidence_metrics["evidence_mrr"]
            if high_conf_mrr is not None:
                high_conf_mrr_values.append(high_conf_mrr)
            high_conf_exact_chunk_values.append(exact_chunk_hit)
            high_conf_evidence_values.append(evidence_hit)
        hit_values.append(legacy_hit)
        precision_values.append(legacy_precision)
        recall_values.append(legacy_recall)
        mrr_values.append(mrr)
        ndcg_values.append(legacy_binary_ndcg)
        graded_ndcg_values.append(legacy_graded_ndcg)
        source_hit_values.append(source_hit)
        dedup_hit_values.append(dedup_hit)
        dedup_precision_values.append(dedup_precision)
        dedup_mrr_values.append(dedup_mrr)
        unique_source_hit_values.append(unique_source_hit)
        unique_source_precision_values.append(unique_source_precision)
        duplicate_source_ratio_values.append(duplicate_source_ratio)
        duplicate_doc_ratio_values.append(duplicate_doc_ratio)
        exact_chunk_hit_values.append(exact_chunk_hit)
        evidence_hit_proxy_values.append(evidence_hit)
        topic_false_positive_values.append(topic_false_positive_rate)
        latencies.append(trace_total_time_ms)
        query_embedding_latencies.append(metric_values["query_embedding_timing_ms"])
        hyde_enabled = bool(score_weights.get("hyde_enabled", False))
        if hyde_enabled:
            hyde_queries_count += 1
            hyde_hit = evidence_metrics["evidence_hit_rate_at_k"]
            if hyde_hit is not None:
                hyde_hit_values.append(hyde_hit)
            hyde_mrr = evidence_metrics["evidence_mrr"]
            if hyde_mrr is not None:
                hyde_mrr_values.append(hyde_mrr)
            hyde_source_hit_values.append(source_hit)
        if row_metrics["medical_expansion_enabled"]:
            medical_expansion_queries_count += 1
        medical_expansion_term_counts.append(metric_values["medical_expansion_term_count"])
        if row_metrics["reranking_enabled"]:
            rerank_enabled_queries_count += 1
        rerank_timing_values.append(metric_values["rerank_timing_ms"])
        rerank_candidate_values.append(metric_values["rerank_candidates_reranked"])
        rerank_output_values.append(metric_values["rerank_output"])
        rerank_filtered_values.append(metric_values["rerank_filtered_out"])
        category = str(item.get("query_category") or "uncategorized")
        task_type = str(item.get("task_type") or "unspecified")
        source_type = expected_source_type_for_item(item)
        difficulty = str(item.get("difficulty") or "unspecified")
        semantic_case = str(item.get("semantic_case") or category or "default")
        by_query_category.setdefault(category, []).append(row_metrics)
        by_task_type.setdefault(task_type, []).append(row_metrics)
        by_expected_source_type.setdefault(source_type, []).append(row_metrics)
        by_difficulty.setdefault(difficulty, []).append(row_metrics)
        if semantic_case in {"paraphrase", "synonym", "acronym", "semantic_only"}:
            by_semantic_case.setdefault(semantic_case, []).append(row_metrics)
        if any(doc.get("semantic_rank") for doc in retrieved_docs):
            retrieval_contribution["semantic_ranked_hits"] += int(exact_chunk_hit)
        if any(doc.get("bm25_rank") for doc in retrieved_docs):
            retrieval_contribution["bm25_ranked_hits"] += int(exact_chunk_hit)
        if any(doc.get("fused_rank") for doc in retrieved_docs):
            retrieval_contribution["fused_ranked_hits"] += int(exact_chunk_hit)
        rows.append(
            {
                "query_id": query_id,
                "query": query,
                "case_status": case_status,
                "exclusion_reason": exclusion_reason,
                "dataset_origin": item.get("dataset_origin"),
                "label_origin": item.get("label_origin"),
                "review_status": item.get("review_status"),
                "dataset_split": item.get("dataset_split"),
                "label_confidence": item.get("label_confidence"),
                "query_category": item.get("query_category"),
                "task_type": item.get("task_type"),
                "expected_source_types": item.get("expected_source_types", []),
                "expected_sources": item.get("expected_sources", []),
                "expected_keywords": item.get("expected_keywords", []),
                "metrics": row_metrics,
                "sources": sources,
                "retrieved_docs": retrieved_docs,
                "trace": trace_payload,
                "context_preview": context[:300],
            }
        )

    def _slice_aggregate(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "query_count": len(items),
            "legacy_heuristic_hit_rate_proxy": finite_mean(
                [r["legacy_heuristic_hit_rate_proxy"] for r in items]
            ),
            "evidence_hit_rate_at_k": finite_mean(
                [
                    r["evidence_hit_rate_at_k"]
                    for r in items
                    if r["evidence_hit_rate_at_k"] is not None
                ]
            ),
            "source_keyword_mrr_proxy": finite_mean([r["source_keyword_mrr_proxy"] for r in items]),
            "source_hit_rate": finite_mean([r["source_hit"] for r in items]),
            "source_family_hit_rate_proxy": finite_mean(
                [r["source_family_hit_rate_proxy"] for r in items]
            ),
            "exact_chunk_hit_rate": finite_mean([r["exact_chunk_hit"] for r in items]),
            "evidence_hit_rate": finite_mean([r["evidence_phrase_hit_proxy"] for r in items]),
            "evidence_phrase_hit_rate_proxy": finite_mean(
                [r["evidence_phrase_hit_proxy"] for r in items]
            ),
            "duplicate_source_ratio_mean": finite_mean(
                [r["duplicate_source_ratio"] for r in items]
            ),
        }

    retrieval_expected_case_count = len(dataset)
    retrieval_measured_case_count = len(evidence_hit_values)
    aggregate = {
        "query_count": len(rows),
        "retrieval_metric_contract_version": RETRIEVAL_METRIC_CONTRACT_VERSION,
        "review_authority_status": _review_manifest_authority_status_from_parts(
            review_context, review_parts
        ),
        "reviewed_evidence_eligible": False,
        "retrieval_expected_case_count": retrieval_expected_case_count,
        "retrieval_measured_case_count": retrieval_measured_case_count,
        "retrieval_failed_case_count": retrieval_failed_case_count,
        "retrieval_excluded_case_count": retrieval_excluded_case_count,
        "retrieval_coverage": (
            retrieval_measured_case_count / retrieval_expected_case_count
            if retrieval_expected_case_count
            else None
        ),
        "evidence_hit_rate_at_k": finite_mean(evidence_hit_values),
        "evidence_precision_at_k": finite_mean(evidence_precision_values),
        "evidence_recall_at_k": finite_mean(evidence_recall_values),
        "evidence_ndcg_at_k": finite_mean(evidence_ndcg_values),
        # Standard metric names use reviewed evidence qrels; old heuristics stay explicit proxies.
        "hit_rate_at_k": finite_mean(evidence_hit_values),
        "precision_at_k": finite_mean(evidence_precision_values),
        "recall_at_k": finite_mean(evidence_recall_values),
        "mrr": finite_mean(evidence_mrr_values),
        "ndcg_at_k": finite_mean(evidence_ndcg_values),
        "graded_ndcg_at_k": finite_mean(evidence_ndcg_values),
        "legacy_heuristic_hit_rate_proxy": finite_mean(hit_values),
        "legacy_returned_precision_proxy": finite_mean(precision_values),
        "legacy_expected_source_recall_proxy": finite_mean(recall_values),
        "legacy_binary_ndcg_proxy": finite_mean(ndcg_values),
        "legacy_heuristic_graded_ndcg_at_k_proxy": finite_mean(graded_ndcg_values),
        "source_keyword_mrr_proxy": finite_mean(mrr_values),
        "source_hit_rate": finite_mean(source_hit_values),
        "source_family_hit_rate_proxy": finite_mean(source_hit_values),
        "dedup_hit_rate_at_k": finite_mean(dedup_hit_values),
        "dedup_precision_at_k": finite_mean(dedup_precision_values),
        "dedup_mrr": finite_mean(dedup_mrr_values),
        "unique_source_hit_rate_at_k": finite_mean(unique_source_hit_values),
        "unique_source_precision_at_k": finite_mean(unique_source_precision_values),
        "duplicate_source_ratio_mean": finite_mean(duplicate_source_ratio_values),
        "duplicate_doc_ratio_mean": finite_mean(duplicate_doc_ratio_values),
        "exact_chunk_hit_rate": finite_mean(exact_chunk_hit_values),
        "evidence_hit_rate": finite_mean(evidence_hit_proxy_values),
        "evidence_phrase_hit_rate_proxy": finite_mean(evidence_hit_proxy_values),
        "latency_p50_ms": _metric_percentile(latencies, 50),
        "latency_p95_ms": _metric_percentile(latencies, 95),
        "query_embedding_latency_p50_ms": _metric_percentile(query_embedding_latencies, 50),
        "query_embedding_latency_p95_ms": _metric_percentile(query_embedding_latencies, 95),
        "hit_rate_at_k_high_conf": finite_mean(high_conf_hit_values),
        "mrr_high_conf": finite_mean(high_conf_mrr_values),
        "exact_chunk_hit_rate_high_conf": finite_mean(high_conf_exact_chunk_values),
        "evidence_hit_rate_high_conf": finite_mean(high_conf_evidence_values),
        "topic_false_positive_rate": finite_mean(topic_false_positive_values),
        "hyde_enabled": hyde_queries_count > 0,
        "hyde_queries_count": hyde_queries_count,
        "hyde_hit_rate": finite_mean(hyde_hit_values),
        "hyde_mrr": finite_mean(hyde_mrr_values),
        "hyde_source_hit_rate": finite_mean(hyde_source_hit_values),
        "medical_expansion_enabled": medical_expansion_queries_count > 0,
        "medical_expansion_queries_count": medical_expansion_queries_count,
        "medical_expansion_term_count_mean": finite_mean(medical_expansion_term_counts),
        "reranking_enabled": rerank_enabled_queries_count > 0,
        "rerank_latency_p50_ms": _metric_percentile(rerank_timing_values, 50),
        "rerank_latency_p95_ms": _metric_percentile(rerank_timing_values, 95),
        "rerank_candidates_mean": finite_mean(rerank_candidate_values),
        "rerank_output_mean": finite_mean(rerank_output_values),
        "rerank_filtered_out_mean": finite_mean(rerank_filtered_values),
        "retrieval_options": dict(retrieval_options or {}),
        "by_query_category": {k: _slice_aggregate(v) for k, v in sorted(by_query_category.items())},
        "by_task_type": {k: _slice_aggregate(v) for k, v in sorted(by_task_type.items())},
        "by_expected_source_type": {
            k: _slice_aggregate(v) for k, v in sorted(by_expected_source_type.items())
        },
        "by_difficulty": {k: _slice_aggregate(v) for k, v in sorted(by_difficulty.items())},
        "by_semantic_case": {k: _slice_aggregate(v) for k, v in sorted(by_semantic_case.items())},
        "contribution_analysis": retrieval_contribution,
    }
    return rows, aggregate
