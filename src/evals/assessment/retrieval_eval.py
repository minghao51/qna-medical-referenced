"""Retrieval evaluation helpers and sweeps."""

from __future__ import annotations

import logging
from typing import Any

from src.evals.metrics import (
    hit_rate_at_k,
    mean,
    ndcg_at_k,
    percentile,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

logger = logging.getLogger(__name__)


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
    if lowered.endswith(".html") or lowered.endswith(".md"):
        return "html"
    return "other"


def expected_source_type_for_item(item: dict[str, Any]) -> str:
    explicit = item.get("target_source_type")
    if explicit:
        return str(explicit)
    expected = item.get("expected_source_types") or []
    if expected:
        return str(expected[0])
    for src in item.get("expected_sources", []):
        st = source_type_from_name(str(src))
        if st != "other":
            return st
    return "unknown"


def doc_is_relevant(doc: dict[str, Any], item: dict[str, Any]) -> bool:
    source = normalize_source_label(str(doc.get("source", "")))
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
    query_embedding_latencies: list[float] = []
    by_query_category: dict[str, list[dict[str, float]]] = {}
    by_task_type: dict[str, list[dict[str, float]]] = {}
    by_expected_source_type: dict[str, list[dict[str, float]]] = {}
    by_difficulty: dict[str, list[dict[str, float]]] = {}
    by_semantic_case: dict[str, list[dict[str, float]]] = {}
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

    for item in dataset:
        query = item["query"]
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
        binary_relevance = [1 if doc_is_relevant(doc, item) else 0 for doc in retrieved_docs]
        dedup_doc_binary = binary_unique_by_key(retrieved_docs, item, lambda d: d.get("id"))
        unique_source_binary = binary_unique_by_key(
            retrieved_docs,
            item,
            lambda d: (str(d.get("source", "")), d.get("page")),
        )
        expected_sources = [str(s).lower() for s in item.get("expected_sources", [])]
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
        row_metrics = {
            "hit_rate_at_k": hit_rate_at_k(binary_relevance),
            "precision_at_k": precision_at_k(binary_relevance, top_k),
            "recall_at_k": recall_at_k(binary_relevance, total_relevant),
            "mrr": reciprocal_rank(binary_relevance),
            "ndcg_at_k": ndcg_at_k(binary_relevance, top_k),
            "source_hit": source_hit,
            "dedup_hit_rate_at_k": hit_rate_at_k(dedup_doc_binary),
            "dedup_precision_at_k": precision_at_k(
                dedup_doc_binary, min(top_k, len(dedup_doc_binary))
            ),
            "dedup_mrr": reciprocal_rank(dedup_doc_binary),
            "unique_source_hit_rate_at_k": hit_rate_at_k(unique_source_binary),
            "unique_source_precision_at_k": precision_at_k(
                unique_source_binary, min(top_k, len(unique_source_binary))
            ),
            "duplicate_source_ratio": duplicate_source_ratio,
            "duplicate_doc_ratio": duplicate_doc_ratio,
            "exact_chunk_hit": exact_chunk_hit,
            "evidence_hit": evidence_hit,
            "topic_false_positive_rate": topic_false_positive_rate,
            "hyde_enabled": bool(
                getattr(trace.retrieval, "score_weights", {}).get("hyde_enabled", False)
            ),
            "medical_expansion_enabled": bool(
                getattr(trace.retrieval, "score_weights", {}).get(
                    "enable_medical_expansion", False
                )
            ),
            "medical_expansion_term_count": float(
                getattr(trace.retrieval, "score_weights", {}).get(
                    "medical_expansion_term_count", 0
                )
            ),
            "reranking_enabled": bool(
                getattr(trace.retrieval, "score_weights", {}).get("enable_reranking", False)
            ),
            "rerank_timing_ms": float(
                getattr(trace.retrieval, "score_weights", {}).get("rerank_timing_ms", 0)
            ),
            "rerank_candidates_reranked": float(
                getattr(trace.retrieval, "score_weights", {}).get(
                    "rerank_candidates_reranked",
                    getattr(trace.retrieval, "score_weights", {}).get("rerank_candidates", 0),
                )
            ),
            "rerank_output": float(
                getattr(trace.retrieval, "score_weights", {}).get("rerank_output", 0)
            ),
            "rerank_filtered_out": float(
                getattr(trace.retrieval, "score_weights", {}).get("rerank_filtered_out", 0)
            ),
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
        query_embedding_latencies.append(
            float(getattr(trace.retrieval, "score_weights", {}).get("query_embedding_timing_ms", 0))
        )
        hyde_enabled = bool(
            getattr(trace.retrieval, "score_weights", {}).get("hyde_enabled", False)
        )
        if hyde_enabled:
            hyde_queries_count += 1
            hyde_hit_values.append(row_metrics["hit_rate_at_k"])
            hyde_mrr_values.append(row_metrics["mrr"])
            hyde_source_hit_values.append(row_metrics["source_hit"])
        if row_metrics["medical_expansion_enabled"]:
            medical_expansion_queries_count += 1
        medical_expansion_term_counts.append(row_metrics["medical_expansion_term_count"])
        if row_metrics["reranking_enabled"]:
            rerank_enabled_queries_count += 1
        rerank_timing_values.append(row_metrics["rerank_timing_ms"])
        rerank_candidate_values.append(row_metrics["rerank_candidates_reranked"])
        rerank_output_values.append(row_metrics["rerank_output"])
        rerank_filtered_values.append(row_metrics["rerank_filtered_out"])
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
        "query_embedding_latency_p50_ms": percentile(query_embedding_latencies, 50),
        "query_embedding_latency_p95_ms": percentile(query_embedding_latencies, 95),
        "hit_rate_at_k_high_conf": mean(high_conf_hit_values)
        if high_conf_hit_values
        else mean(hit_values),
        "mrr_high_conf": mean(high_conf_mrr_values) if high_conf_mrr_values else mean(mrr_values),
        "exact_chunk_hit_rate_high_conf": mean(high_conf_exact_chunk_values)
        if high_conf_exact_chunk_values
        else mean(exact_chunk_hit_values),
        "evidence_hit_rate_high_conf": mean(high_conf_evidence_values)
        if high_conf_evidence_values
        else mean(evidence_hit_values),
        "topic_false_positive_rate": mean(topic_false_positive_values),
        "hyde_enabled": hyde_queries_count > 0,
        "hyde_queries_count": hyde_queries_count,
        "hyde_hit_rate": mean(hyde_hit_values) if hyde_hit_values else None,
        "hyde_mrr": mean(hyde_mrr_values) if hyde_mrr_values else None,
        "hyde_source_hit_rate": mean(hyde_source_hit_values) if hyde_source_hit_values else None,
        "medical_expansion_enabled": medical_expansion_queries_count > 0,
        "medical_expansion_queries_count": medical_expansion_queries_count,
        "medical_expansion_term_count_mean": mean(medical_expansion_term_counts),
        "reranking_enabled": rerank_enabled_queries_count > 0,
        "rerank_latency_p50_ms": percentile(rerank_timing_values, 50),
        "rerank_latency_p95_ms": percentile(rerank_timing_values, 95),
        "rerank_candidates_mean": mean(rerank_candidate_values),
        "rerank_output_mean": mean(rerank_output_values),
        "rerank_filtered_out_mean": mean(rerank_filtered_values),
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


def retrieval_ablation_configs(
    base_options: dict[str, Any] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    base = dict(base_options or {})
    return [
        ("rrf_hybrid", {**base, "search_mode": "rrf_hybrid", "enable_diversification": False}),
        ("rrf_hybrid_mmr", {**base, "search_mode": "rrf_hybrid", "enable_diversification": True}),
        (
            "semantic_only_diversified",
            {**base, "search_mode": "semantic_only", "enable_diversification": True},
        ),
        (
            "bm25_only_diversified",
            {**base, "search_mode": "bm25_only", "enable_diversification": True},
        ),
    ]


def hype_ablation_configs(
    base_options: dict[str, Any] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Ablation configs for HyPE (Hypothetical Prompt Embedding) evaluation.

    Tests the impact of HyPE at different sample rates and in combination with HyDE.
    HyPE generates hypothetical questions at index time, storing them in chunk metadata
    for zero-LLM-cost query expansion at retrieval time.
    """
    base = dict(base_options or {})
    return [
        ("hype_disabled", {**base, "enable_hype": False, "enable_hyde": False}),
        ("hype_10pct", {**base, "enable_hype": True, "enable_hyde": False}),
        (
            "hype_50pct",
            {**base, "enable_hype": True, "enable_hyde": False, "hype_sample_rate": 0.5},
        ),
        (
            "hype_100pct",
            {**base, "enable_hype": True, "enable_hyde": False, "hype_sample_rate": 1.0},
        ),
        ("hyde_only", {**base, "enable_hype": False, "enable_hyde": True}),
        ("hype_plus_hyde", {**base, "enable_hype": True, "enable_hyde": True}),
    ]


def run_hype_ablations(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run HyPE ablation study to evaluate HyPE impact on retrieval quality.

    Note: This version assumes the index already has HyPE questions stored.
    For full ablation with re-ingestion, use run_hype_ablations_with_reingest.
    """
    outputs: dict[str, Any] = {}
    for name, options in hype_ablation_configs(base_options):
        _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=options)
        outputs[name] = metrics
    return outputs


def run_hype_ablations_with_reingest(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
    base_collection_name: str | None = None,
    reconfigure_and_rebuild_fn=None,
) -> dict[str, Any]:
    """Run HyPE ablation with automatic re-ingestion for each variant.

    HyPE is an index-time feature, so each variant requires rebuilding the index
    with different HyPE settings (sample rate, questions per chunk, etc.).

    Args:
        dataset: Evaluation dataset
        top_k: Retrieval top-k
        base_options: Base retrieval options
        base_collection_name: Base name for ChromaDB collections (default: settings.storage.collection_name)
        reconfigure_and_rebuild_fn: Callback that accepts hype_config dict and rebuilds the index.
            The hype_config dict contains: enable_hype, hype_sample_rate, hype_questions_per_chunk

    Returns:
        Dict mapping variant name to metrics dict
    """
    from src.config import settings

    collection_base = base_collection_name or settings.storage.collection_name
    outputs: dict[str, Any] = {}
    configs = hype_ablation_configs(base_options)

    for name, options in configs:
        hype_config = {
            "enable_hype": options.get("enable_hype", False),
            "hype_sample_rate": options.get("hype_sample_rate", settings.hype_sample_rate),
            "hype_questions_per_chunk": options.get(
                "hype_questions_per_chunk", settings.hype_questions_per_chunk
            ),
        }
        variant_collection = f"{collection_base}_{name}"

        if reconfigure_and_rebuild_fn:
            logger.info(
                "Rebuilding index for HyPE variant: %s (collection: %s)", name, variant_collection
            )
            reconfigure_and_rebuild_fn(
                hype_config=hype_config,
                collection_name=variant_collection,
            )

        _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=options)
        metrics["collection_name"] = variant_collection
        metrics["hype_config"] = hype_config
        outputs[name] = metrics

    return outputs


def run_retrieval_ablations(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for name, options in retrieval_ablation_configs(base_options):
        _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=options)
        outputs[name] = metrics
    return outputs


def keyword_ablation_configs(
    base_options: dict[str, Any] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Ablation configs for LLM-extracted keyword and chunk summary evaluation.

    Tests the impact of keyword extraction and chunk summarization at ingestion time
    on retrieval quality. Variants:
    - baseline: Neither keywords nor summaries
    - keywords_only: LLM-extracted keywords for BM25 boosting
    - summaries_only: Chunk summaries prepended to content
    - both: Keywords + summaries combined
    """
    base = dict(base_options or {})
    return [
        (
            "baseline",
            {**base, "enable_keyword_extraction": False, "enable_chunk_summaries": False},
        ),
        (
            "keywords_only",
            {**base, "enable_keyword_extraction": True, "enable_chunk_summaries": False},
        ),
        (
            "summaries_only",
            {**base, "enable_keyword_extraction": False, "enable_chunk_summaries": True},
        ),
        (
            "both",
            {**base, "enable_keyword_extraction": True, "enable_chunk_summaries": True},
        ),
    ]


def run_keyword_ablations(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run keyword extraction and chunk summary ablation study.

    Evaluates the impact of LLM-extracted keywords and chunk summaries
    on retrieval quality across four variants: baseline, keywords_only,
    summaries_only, and both.
    """
    outputs: dict[str, Any] = {}
    for name, options in keyword_ablation_configs(base_options):
        _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=options)
        outputs[name] = metrics
    return outputs


def run_keyword_ablations_with_reingest(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
    base_collection_name: str | None = None,
    reconfigure_and_rebuild_fn=None,
) -> dict[str, Any]:
    """Run keyword/summaries ablation with automatic re-ingestion for each variant."""
    from src.config import settings

    collection_base = base_collection_name or settings.storage.collection_name
    outputs: dict[str, Any] = {}

    for name, options in keyword_ablation_configs(base_options):
        enrichment_config = {
            "enable_keyword_extraction": bool(options.get("enable_keyword_extraction", False)),
            "enable_chunk_summaries": bool(options.get("enable_chunk_summaries", False)),
            "keyword_extraction_sample_rate": options.get(
                "keyword_extraction_sample_rate", settings.keyword_extraction_sample_rate
            ),
            "keyword_extraction_max_chunks": options.get(
                "keyword_extraction_max_chunks", settings.keyword_extraction_max_chunks
            ),
        }
        variant_collection = f"{collection_base}_{name}"

        if reconfigure_and_rebuild_fn:
            logger.info(
                "Rebuilding index for keyword variant: %s (collection: %s)",
                name,
                variant_collection,
            )
            reconfigure_and_rebuild_fn(
                enrichment_config=enrichment_config,
                collection_name=variant_collection,
            )

        _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=options)
        metrics["collection_name"] = variant_collection
        metrics["enrichment_config"] = enrichment_config
        outputs[name] = metrics

    return outputs


def reranking_ablation_configs(
    base_options: dict[str, Any] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Ablation configs for cross-encoder reranking evaluation."""
    base = dict(base_options or {})
    return [
        (
            "no_reranking",
            {
                **base,
                "enable_diversification": False,
                "enable_reranking": False,
                "reranking_mode": "cross_encoder",
            },
        ),
        (
            "cross_encoder_only",
            {
                **base,
                "enable_diversification": False,
                "enable_reranking": True,
                "reranking_mode": "cross_encoder",
            },
        ),
        (
            "mmr_only",
            {
                **base,
                "enable_diversification": True,
                "enable_reranking": False,
                "reranking_mode": "mmr",
            },
        ),
        (
            "both_reranking",
            {
                **base,
                "enable_diversification": True,
                "enable_reranking": True,
                "reranking_mode": "both",
            },
        ),
    ]


def run_reranking_ablations(
    dataset: list[dict[str, Any]],
    top_k: int,
    *,
    base_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run cross-encoder reranking ablation study."""
    outputs: dict[str, Any] = {}
    for name, options in reranking_ablation_configs(base_options):
        _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=options)
        outputs[name] = metrics
    if "no_reranking" in outputs:
        baseline = outputs["no_reranking"]
        for name in outputs:
            if name != "no_reranking":
                variant = outputs[name]
                variant["rerank_improvement_delta"] = (
                    variant.get("hit_rate_at_k", 0) - baseline.get("hit_rate_at_k", 0)
                )
                variant["rerank_mrr_delta"] = variant.get("mrr", 0) - baseline.get("mrr", 0)
                variant["rerank_exact_chunk_delta"] = variant.get(
                    "exact_chunk_hit_rate", 0
                ) - baseline.get("exact_chunk_hit_rate", 0)
                variant["rerank_evidence_delta"] = variant.get(
                    "evidence_hit_rate", 0
                ) - baseline.get("evidence_hit_rate", 0)
                variant["rerank_latency_delta_ms"] = variant.get(
                    "rerank_latency_p50_ms", 0
                ) - baseline.get("rerank_latency_p50_ms", 0)
    return outputs


def run_diversity_sweep(
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
                    _, metrics = evaluate_retrieval(dataset, top_k, retrieval_options=opts)
                    rows.append(
                        {
                            "retrieval_options": opts,
                            "query_count": metrics.get("query_count", 0),
                            "exact_chunk_hit_rate": metrics.get("exact_chunk_hit_rate", 0.0),
                            "evidence_hit_rate": metrics.get("evidence_hit_rate", 0.0),
                            "mrr": metrics.get("mrr", 0.0),
                            "duplicate_source_ratio_mean": metrics.get(
                                "duplicate_source_ratio_mean", 0.0
                            ),
                            "tradeoff_score": (
                                float(metrics.get("exact_chunk_hit_rate", 0.0))
                                + float(metrics.get("evidence_hit_rate", 0.0))
                                - float(metrics.get("duplicate_source_ratio_mean", 0.0))
                            ),
                        }
                    )
    rows.sort(
        key=lambda r: (r["tradeoff_score"], r["exact_chunk_hit_rate"], r["evidence_hit_rate"]),
        reverse=True,
    )
    return rows
