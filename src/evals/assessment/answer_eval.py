"""Answer evaluation helpers."""

from __future__ import annotations

from typing import Any

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
