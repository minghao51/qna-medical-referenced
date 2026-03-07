"""End-to-end pipeline quality assessment orchestration."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.config import settings
from src.evals.artifacts import ArtifactStore
from src.evals.dataset_builder import build_retrieval_dataset
from src.evals.llm_judges import judge_answer
from src.evals.metrics import (
    hit_rate_at_k,
    mean,
    ndcg_at_k,
    percentile,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from src.evals.schemas import AssessmentConfig, AssessmentResult
from src.evals.step_checks import (
    assess_l1_html_markdown_quality,
    assess_l2_pdf_quality,
    assess_l3_chunking_quality,
    assess_l4_reference_quality,
    assess_l5_index_quality,
    audit_l0_download,
)

DEFAULT_THRESHOLDS: dict[str, dict[str, Any]] = {
    "l1.markdown_empty_rate": {"op": "max", "value": 0.10},
    "l2.empty_page_rate": {"op": "max", "value": 0.20},
    "l3.duplicate_chunk_rate": {"op": "max", "value": 0.05},
    "l5.embedding_dim_consistent": {"op": "min", "value": 1.0},
    "l6.exact_chunk_hit_rate_high_conf": {"op": "min", "value": 0.40},
    "l6.evidence_hit_rate_high_conf": {"op": "min", "value": 0.50},
    "l6.hit_rate_at_k_high_conf": {"op": "min", "value": 0.70},
    "l6.mrr_high_conf": {"op": "min", "value": 0.40},
    "l6.topic_false_positive_rate": {"op": "max", "value": 0.35},
    "l6.duplicate_source_ratio_mean": {"op": "max", "value": 0.60},
}


def _git_head() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def _flatten_stage_aggregates(step_metrics: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for stage_key, stage_data in step_metrics.items():
        agg = stage_data.get("aggregate", {})
        for k, v in agg.items():
            flattened[f"{stage_key}.{k}"] = v
    return flattened


def _is_threshold_pass(metric_value: Any, threshold_spec: Any) -> tuple[bool, str, float]:
    if isinstance(threshold_spec, dict):
        op = str(threshold_spec.get("op", "min"))
        threshold_value = float(threshold_spec.get("value", 0))
    else:
        op = "min"
        threshold_value = float(threshold_spec)
    try:
        metric_num = 1.0 if metric_value is True else 0.0 if metric_value is False else float(metric_value)
        if op == "max":
            return metric_num <= threshold_value, op, threshold_value
        return metric_num >= threshold_value, op, threshold_value
    except Exception:
        return False, op, threshold_value


def _evaluate_thresholds(step_metrics: dict[str, Any], retrieval_metrics: dict[str, Any], thresholds: dict[str, Any]) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    lookup = _flatten_stage_aggregates(step_metrics)
    for key, value in retrieval_metrics.items():
        if not isinstance(value, dict):
            lookup[f"l6.{key}"] = value
    for key, threshold in thresholds.items():
        if key not in lookup:
            continue
        metric_value = lookup[key]
        passed, op, threshold_value = _is_threshold_pass(metric_value, threshold)
        if not passed:
            failed.append({"metric": key, "value": metric_value, "threshold_op": op, "threshold_value": threshold_value})
    return failed


def _normalize_source_label(source: str) -> str:
    return source.lower().replace(".pdf", "").replace(".md", "").replace(".html", "")


def _source_type_from_name(name: str) -> str:
    lowered = str(name).lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if lowered.endswith(".csv"):
        return "csv"
    if lowered.endswith(".html") or lowered.endswith(".md"):
        return "html"
    return "other"


def _expected_source_type_for_item(item: dict[str, Any]) -> str:
    explicit = item.get("target_source_type")
    if explicit:
        return str(explicit)
    expected = item.get("expected_source_types") or []
    if expected:
        return str(expected[0])
    for src in item.get("expected_sources", []):
        st = _source_type_from_name(str(src))
        if st != "other":
            return st
    return "unknown"


def _sha256_file(path: str | Path | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _doc_is_relevant(doc: dict[str, Any], item: dict[str, Any]) -> bool:
    source = _normalize_source_label(str(doc.get("source", "")))
    content = str(doc.get("content", "")).lower()
    expected_sources = [str(s).lower() for s in item.get("expected_sources", [])]
    expected_keywords = [str(k).lower() for k in item.get("expected_keywords", [])]
    evidence_phrase = str(item.get("evidence_phrase", "")).strip().lower()
    if expected_sources and any(es in source for es in expected_sources):
        return True
    if evidence_phrase and evidence_phrase in content:
        return True
    if expected_keywords:
        overlap = sum(1 for kw in expected_keywords if kw and kw in content)
        return overlap >= min(2, max(1, len(expected_keywords)))
    return False


def _binary_unique_by_key(retrieved_docs: list[dict[str, Any]], item: dict[str, Any], key_fn) -> list[int]:
    seen = set()
    out: list[int] = []
    for doc in retrieved_docs:
        key = key_fn(doc)
        if key in seen:
            continue
        seen.add(key)
        out.append(1 if _doc_is_relevant(doc, item) else 0)
    return out


def _evaluate_retrieval(
    dataset: list[dict[str, Any]],
    top_k: int,
    retrieval_options: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from src.rag.runtime import retrieve_context_with_trace

    rows: list[dict[str, Any]] = []
    hit_values: list[float] = []
    precision_values: list[float] = []
    recall_values: list[float] = []
    mrr_values: list[float] = []
    ndcg_values: list[float] = []
    source_hit_values: list[float] = []
    dedup_hit_values: list[float] = []
    dedup_precision_values: list[float] = []
    dedup_mrr_values: list[float] = []
    unique_source_hit_values: list[float] = []
    unique_source_precision_values: list[float] = []
    duplicate_source_ratio_values: list[float] = []
    duplicate_doc_ratio_values: list[float] = []
    exact_chunk_hit_values: list[float] = []
    evidence_hit_values: list[float] = []
    latencies: list[float] = []
    high_conf_hit_values: list[float] = []
    high_conf_mrr_values: list[float] = []
    high_conf_exact_chunk_values: list[float] = []
    high_conf_evidence_values: list[float] = []
    topic_false_positive_values: list[float] = []
    by_query_category: dict[str, list[dict[str, float]]] = {}
    by_task_type: dict[str, list[dict[str, float]]] = {}
    by_expected_source_type: dict[str, list[dict[str, float]]] = {}
    by_difficulty: dict[str, list[dict[str, float]]] = {}
    retrieval_contribution = {
        "semantic_ranked_hits": 0,
        "bm25_ranked_hits": 0,
        "fused_ranked_hits": 0,
    }

    for item in dataset:
        query = item["query"]
        if retrieval_options:
            context, sources, trace = retrieve_context_with_trace(query, top_k=top_k, retrieval_options=retrieval_options)
        else:
            context, sources, trace = retrieve_context_with_trace(query, top_k=top_k)
        retrieved_docs = [doc.model_dump() if hasattr(doc, "model_dump") else doc for doc in trace.retrieval.documents]
        binary_relevance = [1 if _doc_is_relevant(doc, item) else 0 for doc in retrieved_docs]
        dedup_doc_binary = _binary_unique_by_key(retrieved_docs, item, lambda d: d.get("id"))
        unique_source_binary = _binary_unique_by_key(
            retrieved_docs,
            item,
            lambda d: (str(d.get("source", "")), d.get("page")),
        )
        expected_sources = [str(s).lower() for s in item.get("expected_sources", [])]
        source_hit = 0.0
        if expected_sources:
            source_hit = 1.0 if any(any(es in str(s).lower() for es in expected_sources) for s in sources) else 0.0
        total_relevant = max(1, len(expected_sources)) if expected_sources else 1
        exact_chunk_id = item.get("expected_chunk_id")
        exact_chunk_hit = 1.0 if (exact_chunk_id and any(str(doc.get("id")) == str(exact_chunk_id) for doc in retrieved_docs)) else 0.0
        evidence_phrase = str(item.get("evidence_phrase", "")).strip().lower()
        evidence_hit = 0.0
        if evidence_phrase:
            evidence_hit = 1.0 if any(evidence_phrase in str(doc.get("content", "")).lower() for doc in retrieved_docs) else 0.0
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
        duplicate_source_ratio = 1.0 - (len(unique_sources) / len(retrieved_docs)) if retrieved_docs else 0.0
        duplicate_doc_ratio = 1.0 - (len(unique_doc_ids) / len(retrieved_docs)) if retrieved_docs else 0.0
        row_metrics = {
            "hit_rate_at_k": hit_rate_at_k(binary_relevance),
            "precision_at_k": precision_at_k(binary_relevance, top_k),
            "recall_at_k": recall_at_k(binary_relevance, total_relevant),
            "mrr": reciprocal_rank(binary_relevance),
            "ndcg_at_k": ndcg_at_k(binary_relevance, top_k),
            "source_hit": source_hit,
            "dedup_hit_rate_at_k": hit_rate_at_k(dedup_doc_binary),
            "dedup_precision_at_k": precision_at_k(dedup_doc_binary, min(top_k, len(dedup_doc_binary))),
            "dedup_mrr": reciprocal_rank(dedup_doc_binary),
            "unique_source_hit_rate_at_k": hit_rate_at_k(unique_source_binary),
            "unique_source_precision_at_k": precision_at_k(unique_source_binary, min(top_k, len(unique_source_binary))),
            "duplicate_source_ratio": duplicate_source_ratio,
            "duplicate_doc_ratio": duplicate_doc_ratio,
            "exact_chunk_hit": exact_chunk_hit,
            "evidence_hit": evidence_hit,
            "topic_false_positive_rate": topic_false_positive_rate,
        }
        if item.get("label_confidence") == "high":
            high_conf_hit_values.append(row_metrics["hit_rate_at_k"])
            high_conf_mrr_values.append(row_metrics["mrr"])
            high_conf_exact_chunk_values.append(row_metrics["exact_chunk_hit"])
            high_conf_evidence_values.append(row_metrics["evidence_hit"])
        hit_values.append(row_metrics["hit_rate_at_k"])
        precision_values.append(row_metrics["precision_at_k"])
        recall_values.append(row_metrics["recall_at_k"])
        mrr_values.append(row_metrics["mrr"])
        ndcg_values.append(row_metrics["ndcg_at_k"])
        source_hit_values.append(row_metrics["source_hit"])
        dedup_hit_values.append(row_metrics["dedup_hit_rate_at_k"])
        dedup_precision_values.append(row_metrics["dedup_precision_at_k"])
        dedup_mrr_values.append(row_metrics["dedup_mrr"])
        unique_source_hit_values.append(row_metrics["unique_source_hit_rate_at_k"])
        unique_source_precision_values.append(row_metrics["unique_source_precision_at_k"])
        duplicate_source_ratio_values.append(row_metrics["duplicate_source_ratio"])
        duplicate_doc_ratio_values.append(row_metrics["duplicate_doc_ratio"])
        exact_chunk_hit_values.append(row_metrics["exact_chunk_hit"])
        evidence_hit_values.append(row_metrics["evidence_hit"])
        topic_false_positive_values.append(row_metrics["topic_false_positive_rate"])
        latencies.append(float(trace.total_time_ms))
        category = str(item.get("query_category") or "uncategorized")
        task_type = str(item.get("task_type") or "unspecified")
        source_type = _expected_source_type_for_item(item)
        difficulty = str(item.get("difficulty") or "unspecified")
        by_query_category.setdefault(category, []).append(row_metrics)
        by_task_type.setdefault(task_type, []).append(row_metrics)
        by_expected_source_type.setdefault(source_type, []).append(row_metrics)
        by_difficulty.setdefault(difficulty, []).append(row_metrics)
        if any(doc.get("semantic_rank") for doc in retrieved_docs):
            retrieval_contribution["semantic_ranked_hits"] += int(exact_chunk_hit)
        if any(doc.get("bm25_rank") for doc in retrieved_docs):
            retrieval_contribution["bm25_ranked_hits"] += int(exact_chunk_hit)
        if any(doc.get("fused_rank") for doc in retrieved_docs):
            retrieval_contribution["fused_ranked_hits"] += int(exact_chunk_hit)
        rows.append(
            {
                "query_id": item.get("query_id"),
                "query": query,
                "dataset_origin": item.get("dataset_origin"),
                "label_confidence": item.get("label_confidence"),
                "query_category": item.get("query_category"),
                "task_type": item.get("task_type"),
                "expected_source_types": item.get("expected_source_types", []),
                "expected_sources": item.get("expected_sources", []),
                "expected_keywords": item.get("expected_keywords", []),
                "metrics": row_metrics,
                "sources": sources,
                "retrieved_docs": retrieved_docs,
                "trace": trace.model_dump() if hasattr(trace, "model_dump") else {},
                "context_preview": context[:300],
            }
        )

    def _slice_aggregate(items: list[dict[str, float]]) -> dict[str, float]:
        return {
            "query_count": len(items),
            "hit_rate_at_k": mean([r["hit_rate_at_k"] for r in items]),
            "mrr": mean([r["mrr"] for r in items]),
            "source_hit_rate": mean([r["source_hit"] for r in items]),
            "exact_chunk_hit_rate": mean([r["exact_chunk_hit"] for r in items]),
            "evidence_hit_rate": mean([r["evidence_hit"] for r in items]),
            "duplicate_source_ratio_mean": mean([r["duplicate_source_ratio"] for r in items]),
        }

    aggregate = {
        "query_count": len(rows),
        "hit_rate_at_k": mean(hit_values),
        "precision_at_k": mean(precision_values),
        "recall_at_k": mean(recall_values),
        "mrr": mean(mrr_values),
        "ndcg_at_k": mean(ndcg_values),
        "source_hit_rate": mean(source_hit_values),
        "dedup_hit_rate_at_k": mean(dedup_hit_values),
        "dedup_precision_at_k": mean(dedup_precision_values),
        "dedup_mrr": mean(dedup_mrr_values),
        "unique_source_hit_rate_at_k": mean(unique_source_hit_values),
        "unique_source_precision_at_k": mean(unique_source_precision_values),
        "duplicate_source_ratio_mean": mean(duplicate_source_ratio_values),
        "duplicate_doc_ratio_mean": mean(duplicate_doc_ratio_values),
        "exact_chunk_hit_rate": mean(exact_chunk_hit_values),
        "evidence_hit_rate": mean(evidence_hit_values),
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "hit_rate_at_k_high_conf": mean(high_conf_hit_values) if high_conf_hit_values else mean(hit_values),
        "mrr_high_conf": mean(high_conf_mrr_values) if high_conf_mrr_values else mean(mrr_values),
        "exact_chunk_hit_rate_high_conf": mean(high_conf_exact_chunk_values) if high_conf_exact_chunk_values else mean(exact_chunk_hit_values),
        "evidence_hit_rate_high_conf": mean(high_conf_evidence_values) if high_conf_evidence_values else mean(evidence_hit_values),
        "topic_false_positive_rate": mean(topic_false_positive_values),
        "retrieval_options": dict(retrieval_options or {}),
        "by_query_category": {k: _slice_aggregate(v) for k, v in sorted(by_query_category.items())},
        "by_task_type": {k: _slice_aggregate(v) for k, v in sorted(by_task_type.items())},
        "by_expected_source_type": {k: _slice_aggregate(v) for k, v in sorted(by_expected_source_type.items())},
        "by_difficulty": {k: _slice_aggregate(v) for k, v in sorted(by_difficulty.items())},
        "contribution_analysis": retrieval_contribution,
    }
    return rows, aggregate


def _evaluate_answers(dataset: list[dict[str, Any]], top_k: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not settings.dashscope_api_key or settings.dashscope_api_key == "test-api-key":
        return [], {"status": "skipped", "reason": "missing_dashscope_api_key"}

    from src.infra.llm import get_client
    from src.rag.runtime import retrieve_context_with_trace

    client = get_client()
    rows: list[dict[str, Any]] = []
    relevance_scores: list[float] = []
    faithfulness_scores: list[float] = []
    grounded_ratios: list[float] = []
    disclaimer_hits = 0
    judge_errors = 0

    for item in dataset:
        query = item["query"]
        context, sources, trace = retrieve_context_with_trace(query, top_k=top_k)
        answer = client.generate(prompt=query, context=context)
        judge = judge_answer(query=query, answer=answer, context=context)
        parsed = judge.get("parsed", {}) if judge.get("status") == "ok" else {}
        if judge.get("status") != "ok":
            judge_errors += 1
        else:
            relevance_scores.append(float(parsed.get("relevance_score", 0)))
            faithfulness_scores.append(float(parsed.get("faithfulness_score", 0)))
            grounded_ratios.append(float(parsed.get("grounded_claim_ratio", 0)))
            disclaimer_hits += int(bool(parsed.get("has_medical_disclaimer")))
        rows.append(
            {
                "query_id": item.get("query_id"),
                "query": query,
                "sources": sources,
                "trace": trace.model_dump() if hasattr(trace, "model_dump") else {},
                "answer": answer,
                "judge": judge,
            }
        )

    aggregate = {
        "status": "ok",
        "query_count": len(rows),
        "judge_error_rate": (judge_errors / len(rows)) if rows else 0.0,
        "relevance_score_mean": mean(relevance_scores),
        "faithfulness_score_mean": mean(faithfulness_scores),
        "grounded_claim_ratio_mean": mean(grounded_ratios),
        "has_medical_disclaimer_rate": (disclaimer_hits / len(rows)) if rows else 0.0,
    }
    return rows, aggregate


def _retrieval_ablation_configs(base_options: dict[str, Any] | None = None) -> list[tuple[str, dict[str, Any]]]:
    base = dict(base_options or {})
    return [
        ("legacy_hybrid", {**base, "search_mode": "legacy_hybrid", "enable_diversification": True}),
        ("semantic_only_diversified", {**base, "search_mode": "semantic_only", "enable_diversification": True}),
        ("bm25_only_diversified", {**base, "search_mode": "bm25_only", "enable_diversification": True}),
        ("rrf_hybrid", {**base, "search_mode": "rrf_hybrid", "enable_diversification": False}),
        ("rrf_hybrid_mmr", {**base, "search_mode": "rrf_hybrid", "enable_diversification": True}),
    ]


def _run_retrieval_ablations(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for name, options in _retrieval_ablation_configs(base_options):
        _, metrics = _evaluate_retrieval(dataset, top_k, retrieval_options=options)
        outputs[name] = metrics
    return outputs


def _run_diversity_sweep(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
    mmr_lambda_values: list[float] | None = None,
    overfetch_multipliers: list[int] | None = None,
    max_chunks_per_source_page_values: list[int] | None = None,
    max_chunks_per_source_values: list[int] | None = None,
) -> list[dict[str, Any]]:
    lambdas = mmr_lambda_values or [0.5, 0.75, 0.9]
    overfetches = overfetch_multipliers or [2, 4]
    per_page_caps = max_chunks_per_source_page_values or [1, 2]
    per_source_caps = max_chunks_per_source_values or [2, 3]
    rows: list[dict[str, Any]] = []
    base = dict(base_options or {})
    for mmr_lambda in lambdas:
        for overfetch in overfetches:
            for per_page in per_page_caps:
                for per_source in per_source_caps:
                    opts = {
                        **base,
                        "search_mode": "rrf_hybrid",
                        "enable_diversification": True,
                        "mmr_lambda": mmr_lambda,
                        "overfetch_multiplier": overfetch,
                        "max_chunks_per_source_page": per_page,
                        "max_chunks_per_source": per_source,
                    }
                    _, metrics = _evaluate_retrieval(dataset, top_k, retrieval_options=opts)
                    rows.append(
                        {
                            "retrieval_options": opts,
                            "query_count": metrics.get("query_count", 0),
                            "exact_chunk_hit_rate": metrics.get("exact_chunk_hit_rate", 0.0),
                            "evidence_hit_rate": metrics.get("evidence_hit_rate", 0.0),
                            "mrr": metrics.get("mrr", 0.0),
                            "duplicate_source_ratio_mean": metrics.get("duplicate_source_ratio_mean", 0.0),
                            "tradeoff_score": (
                                float(metrics.get("exact_chunk_hit_rate", 0.0))
                                + float(metrics.get("evidence_hit_rate", 0.0))
                                - float(metrics.get("duplicate_source_ratio_mean", 0.0))
                            ),
                        }
                    )
    rows.sort(key=lambda r: (r["tradeoff_score"], r["exact_chunk_hit_rate"], r["evidence_hit_rate"]), reverse=True)
    return rows


def _render_summary(
    *,
    step_metrics: dict[str, Any],
    retrieval_metrics: dict[str, Any],
    rag_metrics: dict[str, Any],
    dataset_stats: dict[str, Any],
    failed_thresholds: list[dict[str, Any]],
) -> str:
    lines = [
        "# Pipeline Quality Assessment Summary",
        "",
        "## Dataset",
        f"- Fixture records: {dataset_stats.get('fixture_records', 0)}",
        f"- Synthetic records: {dataset_stats.get('synthetic_records', 0)}",
        f"- Merged records: {dataset_stats.get('merged_records', 0)}",
        "",
        "## Step Metrics",
    ]
    for stage in ["l0", "l1", "l2", "l3", "l4", "l5"]:
        agg = step_metrics.get(stage, {}).get("aggregate", {})
        lines.append(f"- {stage.upper()}: {json.dumps(agg, ensure_ascii=False)}")
    lines.extend(
        [
            "",
            "## Retrieval Metrics (L6)",
            f"- {json.dumps(retrieval_metrics, ensure_ascii=False)}",
            "",
            "## Answer Eval",
            f"- {json.dumps(rag_metrics, ensure_ascii=False)}",
            "",
            "## Threshold Failures",
        ]
    )
    if failed_thresholds:
        for failure in failed_thresholds:
            lines.append(
                f"- {failure['metric']}: value={failure['value']} "
                f"threshold_{failure['threshold_op']}={failure['threshold_value']}"
            )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def run_assessment(
    *,
    artifact_dir: str | Path = "data/evals",
    name: str | None = None,
    dataset_path: str | Path | None = None,
    top_k: int = 5,
    max_synthetic_questions: int = 40,
    disable_llm_generation: bool = False,
    disable_llm_judging: bool = False,
    include_answer_eval: bool | None = None,
    sample_docs_per_source_type: int = 10,
    seed: int = 42,
    fail_on_thresholds: bool = False,
    thresholds_file: str | Path | None = None,
    dataset_split: str | None = None,
    min_label_confidence: str = "low",
    retrieval_mode: str = "rrf_hybrid",
    disable_page_classification: bool = False,
    disable_structured_chunking: bool = False,
    disable_bm25: bool = False,
    export_failed_generations: bool = False,
    retrieval_options: dict[str, Any] | None = None,
    run_retrieval_ablations: bool = False,
    run_diversity_sweep: bool = False,
    diversity_sweep: dict[str, Any] | None = None,
) -> AssessmentResult:
    start = time.time()
    from src.ingestion.steps.chunk_text import set_structured_chunking_enabled
    from src.ingestion.steps.convert_html import set_page_classification_enabled
    from src.ingestion.steps.load_markdown import set_index_only_classified_pages

    thresholds = dict(DEFAULT_THRESHOLDS)
    if thresholds_file:
        thresholds.update(json.loads(Path(thresholds_file).read_text(encoding="utf-8")))

    key_available = bool(settings.dashscope_api_key) and settings.dashscope_api_key != "test-api-key"
    resolved_include_answer_eval = bool(include_answer_eval) if include_answer_eval is not None else key_available
    resolved_retrieval_options = dict(retrieval_options or {})
    if disable_bm25:
        resolved_retrieval_options["search_mode"] = "semantic_only"
    elif retrieval_mode != "rrf_hybrid":
        resolved_retrieval_options["search_mode"] = retrieval_mode
    set_page_classification_enabled(not disable_page_classification)
    set_index_only_classified_pages(not disable_page_classification)
    set_structured_chunking_enabled(not disable_structured_chunking)
    config = AssessmentConfig(
        artifact_dir=Path(artifact_dir),
        name=name,
        dataset_path=Path(dataset_path) if dataset_path else None,
        top_k=top_k,
        max_synthetic_questions=max_synthetic_questions,
        disable_llm_generation=disable_llm_generation,
        disable_llm_judging=disable_llm_judging,
        include_answer_eval=resolved_include_answer_eval,
        sample_docs_per_source_type=sample_docs_per_source_type,
        seed=seed,
        fail_on_thresholds=fail_on_thresholds,
        thresholds=thresholds,
        retrieval_options=resolved_retrieval_options or None,
        dataset_split=dataset_split,
        min_label_confidence=min_label_confidence,
        retrieval_mode=retrieval_mode,
        disable_page_classification=disable_page_classification,
        disable_structured_chunking=disable_structured_chunking,
        disable_bm25=disable_bm25,
        export_failed_generations=export_failed_generations,
        run_retrieval_ablations=run_retrieval_ablations,
        run_diversity_sweep=run_diversity_sweep,
        diversity_sweep=dict(diversity_sweep or {}),
    )

    store = ArtifactStore(config.artifact_dir, config.name)
    manifest = {
        "config": asdict(config),
        "git_head": _git_head(),
        "dashscope_key_present": key_available,
        "started_at_epoch_s": start,
    }
    store.write_json("manifest.json", manifest)

    step_metrics = {
        "l0": audit_l0_download(),
        "l1": assess_l1_html_markdown_quality(),
        "l2": assess_l2_pdf_quality(),
        "l3": assess_l3_chunking_quality(),
        "l4": assess_l4_reference_quality(),
        "l5": assess_l5_index_quality(),
    }
    step_findings: list[dict[str, Any]] = []
    for stage in step_metrics.values():
        step_findings.extend(stage.get("findings", []))

    dataset_bundle = build_retrieval_dataset(
        dataset_path=config.dataset_path,
        enable_llm_generation=not config.disable_llm_generation,
        max_synthetic_questions=config.max_synthetic_questions,
        sample_docs_per_source_type=config.sample_docs_per_source_type,
        seed=config.seed,
        dataset_split=config.dataset_split,
        min_label_confidence=config.min_label_confidence,
    )
    dataset = dataset_bundle["dataset"]
    generation_attempts = dataset_bundle.get("generation_attempts", [])
    dataset_stats = dataset_bundle.get("stats", {})

    if config.retrieval_options:
        retrieval_rows, retrieval_metrics = _evaluate_retrieval(dataset, config.top_k, retrieval_options=config.retrieval_options)
    else:
        retrieval_rows, retrieval_metrics = _evaluate_retrieval(dataset, config.top_k)
    retrieval_ablations: dict[str, Any] = {}
    if config.run_retrieval_ablations:
        retrieval_ablations = _run_retrieval_ablations(dataset, config.top_k, base_options=config.retrieval_options)
    diversity_sweep_rows: list[dict[str, Any]] = []
    if config.run_diversity_sweep:
        diversity_sweep_rows = _run_diversity_sweep(
            dataset,
            config.top_k,
            base_options=config.retrieval_options,
            mmr_lambda_values=config.diversity_sweep.get("mmr_lambda_values"),
            overfetch_multipliers=config.diversity_sweep.get("overfetch_multipliers"),
            max_chunks_per_source_page_values=config.diversity_sweep.get("max_chunks_per_source_page_values"),
            max_chunks_per_source_values=config.diversity_sweep.get("max_chunks_per_source_values"),
        )
    rag_rows: list[dict[str, Any]] = []
    rag_metrics: dict[str, Any] = {"status": "skipped", "reason": "disabled"}
    if config.include_answer_eval and not config.disable_llm_judging:
        rag_rows, rag_metrics = _evaluate_answers(dataset, config.top_k)
    elif config.disable_llm_judging:
        rag_metrics = {"status": "skipped", "reason": "llm_judging_disabled"}

    failed_thresholds = _evaluate_thresholds(step_metrics, retrieval_metrics, config.thresholds)
    step_findings.extend(
        {"severity": "error", "stage": "threshold", "message": f"{f['metric']} below threshold", **f}
        for f in failed_thresholds
    )

    l3_agg = step_metrics.get("l3", {}).get("aggregate", {})
    l5_agg = step_metrics.get("l5", {}).get("aggregate", {})
    vector_path = l5_agg.get("vector_path")
    dataset_file = str(config.dataset_path) if config.dataset_path else None
    manifest["runtime_retrieval"] = retrieval_metrics.get("retrieval_options", {})
    manifest["chunking"] = {
        "chunk_size_config": l3_agg.get("chunk_size_config"),
        "chunk_overlap_config": l3_agg.get("chunk_overlap_config"),
    }
    manifest["index_provenance"] = {
        "collection_name": settings.collection_name,
        "vector_path": vector_path,
        "vector_file_mtime_epoch_s": Path(vector_path).stat().st_mtime if vector_path and Path(vector_path).exists() else None,
        "doc_counts_by_source_type": l5_agg.get("source_distribution", {}),
        "dedupe_effect_estimate": l5_agg.get("dedupe_effect_estimate"),
    }
    manifest["checksums"] = {
        "vector_file_sha256": _sha256_file(vector_path),
        "dataset_file_sha256": _sha256_file(dataset_file),
    }
    store.write_json("manifest.json", manifest)

    store.write_json("step_metrics.json", step_metrics)
    store.write_json("step_findings.json", step_findings)
    store.write_jsonl("html_metrics.jsonl", step_metrics["l1"].get("records", []))
    store.write_jsonl("pdf_metrics.jsonl", step_metrics["l2"].get("records", []))
    store.write_jsonl("chunk_metrics.jsonl", step_metrics["l3"].get("records", []))
    store.write_json("reference_metrics.json", step_metrics["l4"])
    store.write_json("index_metrics.json", step_metrics["l5"])
    store.write_json("retrieval_dataset.json", dataset)
    if config.export_failed_generations:
        store.write_jsonl("retrieval_dataset_generation.jsonl", generation_attempts)
    else:
        store.write_jsonl(
            "retrieval_dataset_generation.jsonl",
            [row for row in generation_attempts if row.get("status") == "accepted"],
        )
    store.write_jsonl("retrieval_results.jsonl", retrieval_rows)
    store.write_json("retrieval_metrics.json", retrieval_metrics)
    store.write_json("retrieval_ablations.json", retrieval_ablations)
    store.write_json("retrieval_diversity_sweep.json", diversity_sweep_rows)
    store.write_jsonl("rag_results.jsonl", rag_rows)
    store.write_json("rag_metrics.json", rag_metrics)

    summary = {
        "run_dir": str(store.run_dir),
        "duration_s": round(time.time() - start, 3),
        "retrieval_metrics": retrieval_metrics,
        "retrieval_ablations": retrieval_ablations,
        "retrieval_diversity_sweep_top": diversity_sweep_rows[:5],
        "rag_metrics": rag_metrics,
        "failed_thresholds_count": len(failed_thresholds),
        "status": "failed" if (failed_thresholds and config.fail_on_thresholds) else "ok",
    }
    store.write_text(
        "summary.md",
        _render_summary(
            step_metrics=step_metrics,
            retrieval_metrics=retrieval_metrics,
            rag_metrics=rag_metrics,
            dataset_stats=dataset_stats,
            failed_thresholds=failed_thresholds,
        ),
    )
    store.write_json("summary.json", summary)
    store.write_latest_pointer()

    status = "failed" if (failed_thresholds and config.fail_on_thresholds) else "ok"
    return AssessmentResult(run_dir=store.run_dir, status=status, failed_thresholds=failed_thresholds, summary=summary)
