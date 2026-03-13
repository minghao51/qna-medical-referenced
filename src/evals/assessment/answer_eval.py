"""Answer evaluation helpers."""

from __future__ import annotations

from typing import Any

from deepeval.test_case import LLMTestCase

from src.config import settings
from src.evals.llm_judges import judge_answer
from src.evals.metrics import mean


def evaluate_answers(
    dataset: list[dict[str, Any]], top_k: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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


async def evaluate_answers_deepeval(
    dataset: list[dict[str, Any]],
    top_k: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Comprehensive answer quality evaluation using DeepEval.

    Evaluates each query-answer pair using 6 metrics:
    - Factual Accuracy (heavyweight): Groundedness in context
    - Completeness (heavyweight): Coverage of question aspects
    - Clinical Relevance (heavyweight): Medical appropriateness
    - Clarity (lightweight): Readability and structure
    - Answer Relevancy (lightweight): Directly addresses question
    - Faithfulness (heavyweight): No hallucinations

    Args:
        dataset: List of query dicts with 'query' and optional 'query_id' keys
        top_k: Number of documents to retrieve for context

    Returns:
        Tuple of (per_query_results, aggregate_metrics):
        - per_query_results: List of dicts with query, answer, sources, metrics
        - aggregate_metrics: Dict with mean scores and counts
    """
    from src.evals.metrics.medical import (
        answer_relevancy_metric,
        clarity_metric,
        clinical_relevance_metric,
        completeness_metric,
        factual_accuracy_metric,
        faithfulness_metric,
    )
    from src.infra.llm import get_client
    from src.rag.runtime import retrieve_context_with_trace

    client = get_client()
    results = []
    all_scores = {
        "factual_accuracy": [],
        "completeness": [],
        "clinical_relevance": [],
        "clarity": [],
        "answer_relevancy": [],
        "faithfulness": []
    }

    for item in dataset:
        query = item["query"]

        # Retrieve and generate
        context, sources, trace = retrieve_context_with_trace(query, top_k=top_k)
        answer = client.generate(prompt=query, context=context)

        # Create test case
        test_case = LLMTestCase(
            input=query,
            actual_output=answer,
            retrieval_context=[context]  # DeepEval expects list
        )

        # Run all metrics
        metrics = [
            factual_accuracy_metric,
            completeness_metric,
            clinical_relevance_metric,
            clarity_metric,
            answer_relevancy_metric,
            faithfulness_metric
        ]

        metric_results = {}
        for metric in metrics:
            metric.measure(test_case)
            metric_results[metric.name] = {
                "score": metric.score,
                "reason": metric.reason if hasattr(metric, 'reason') else None
            }
            all_scores[metric.name.lower().replace(" ", "_")].append(metric.score)

        results.append({
            "query_id": item.get("query_id"),
            "query": query,
            "answer": answer,
            "sources": sources,
            "trace": trace.model_dump() if hasattr(trace, "model_dump") else {},
            "metrics": metric_results
        })

    # Calculate aggregates
    aggregate = {
        "query_count": len(results),
        **{k: {"mean": sum(v)/len(v) if v else 0, "count": len(v)}
           for k, v in all_scores.items()}
    }

    return results, aggregate
