"""Evaluation and metrics API endpoints.

This module provides endpoints for accessing evaluation results, metrics,
and historical trending data. Evaluation runs assess the quality of the
RAG pipeline using LLM-based judges and retrieval metrics.

Endpoints:
    - GET /evaluation/latest - Get latest evaluation run results
    - GET /evaluation/runs - List all evaluation runs
    - GET /evaluation/history - Get historical trending metrics
    - GET /evaluation/steps/{stage} - Get metrics for a specific pipeline stage

Example:
    Get latest evaluation:
        curl http://localhost:8000/evaluation/latest

    Get evaluation history:
        curl http://localhost:8000/evaluation/history?limit=20

    Get step metrics:
        curl http://localhost:8000/evaluation/steps/l2
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from src.services.evaluation_service import EvaluationService

logger = logging.getLogger(__name__)

router = APIRouter()

EVALS_DIR = Path("data/evals")
LATEST_POINTER = Path("data/evals/latest_run.txt")
RUN_DIR_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
VALID_STAGES = {"l0", "l1", "l2", "l3", "l4", "l5", "l6"}

def _validate_run_dir(run_dir: str) -> str:
    normalized = str(run_dir or "").strip()
    if not normalized or not RUN_DIR_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=400, detail="Invalid run directory identifier")
    return normalized


def _validate_stage(stage: str) -> str:
    normalized = str(stage or "").strip().lower()
    if normalized not in VALID_STAGES:
        raise HTTPException(
            status_code=400, detail=f"Invalid stage. Must be one of: {sorted(VALID_STAGES)}"
        )
    return normalized

def _get_evaluation_service() -> EvaluationService:
    return EvaluationService(
        evals_dir=EVALS_DIR,
        latest_pointer=LATEST_POINTER,
        comprehensive_ablation_dir=Path("data/evals_comprehensive_ablation"),
    )


@router.get(
    "/evaluation/latest",
    summary="Get latest evaluation results",
    description="Retrieve all metrics and results from the most recent evaluation run",
)
def get_latest_evaluation() -> dict[str, Any]:
    """Get the latest evaluation run results.

    Returns comprehensive data from the latest evaluation run including
    summary metrics, step-level metrics, retrieval metrics, and manifest.

    Returns:
        Dictionary containing:
            - run_dir: Name of the evaluation run directory
            - summary: Overall run status and metrics (if available)
            - step_metrics: Per-stage pipeline metrics (if available)
            - retrieval_metrics: Retrieval quality metrics (if available)
            - manifest: Run configuration and metadata (if available)

    Raises:
        HTTPException(404): If no evaluation runs exist

    Example:
        GET /evaluation/latest

        Response:
        {
            "run_dir": "250228T120000Z_abc123",
            "summary": {
                "status": "passed",
                "duration_s": 45.2,
                "failed_thresholds_count": 0
            },
            "retrieval_metrics": {
                "hit_rate_at_k": 0.85,
                "mrr": 0.72,
                "ndcg_at_k": 0.78
            }
        }
    """
    try:
        return _get_evaluation_service().load_latest_evaluation()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/evaluation/runs",
    summary="List all evaluation runs",
    description="Get a list of all evaluation runs with basic metadata",
)
def get_evaluation_runs() -> list[dict[str, Any]]:
    """Get all evaluation runs with summary information.

    Returns a lightweight list of all runs with status and duration
    metadata. Useful for displaying a run history in a UI.

    Returns:
        List of dictionaries containing:
            - run_dir: Name of the evaluation run directory
            - status: Run status ("passed", "failed", "error")
            - duration_s: Run duration in seconds
            - failed_thresholds_count: Number of failed threshold checks

    Example:
        GET /evaluation/runs

        Response:
        [
            {
                "run_dir": "250228T120000Z_abc123",
                "status": "passed",
                "duration_s": 45.2,
                "failed_thresholds_count": 0
            },
            {
                "run_dir": "250228T110000Z_def456",
                "status": "failed",
                "duration_s": 38.1,
                "failed_thresholds_count": 2
            }
        ]
    """
    return _get_evaluation_service().get_all_runs()


@router.get(
    "/evaluation/history",
    summary="Get evaluation trending metrics",
    description="Get historical evaluation metrics for trending analysis and performance monitoring",
)
def get_evaluation_history(
    limit: int = 10,
) -> dict[str, Any]:
    """Get historical evaluation metrics for trending analysis.

    Aggregates metrics across multiple evaluation runs to show trends
    over time. Computes averages for key metrics like hit rate, MRR,
    and latency.

    Args:
        limit: Maximum number of recent runs to include (default: 10)

    Returns:
        Dictionary containing:
            - runs: List of run data with timestamps and metrics
            - summary: Aggregated averages across all runs

    Example:
        GET /evaluation/history?limit=20

        Response:
        {
            "runs": [
                {
                    "run_dir": "250228T120000Z_abc123",
                    "timestamp": "250228T120000Z",
                    "status": "passed",
                    "retrieval_metrics": {
                        "hit_rate_at_k": 0.85,
                        "mrr": 0.72
                    }
                }
            ],
            "summary": {
                "total_runs": 10,
                "avg_hit_rate": 0.82,
                "avg_mrr": 0.70,
                "avg_latency_p50": 150
            }
        }
    """
    limit = max(1, min(int(limit), 100))
    service = _get_evaluation_service()
    local_runs = service.local_history_runs(limit)
    return {
        "runs": local_runs,
        "summary": service.aggregate_history_summary(local_runs),
        "sources": {"mode": "local"},
    }


@router.get(
    "/evaluation/run/{run_dir}",
    summary="Get specific evaluation run",
    description="Get all metrics and results from a specific evaluation run",
)
def get_evaluation_run(run_dir: str) -> dict[str, Any]:
    """Get a specific evaluation run by directory name.

    Returns comprehensive data from the specified evaluation run including
    summary metrics, step-level metrics, retrieval metrics, and manifest.

    Args:
        run_dir: Name of the evaluation run directory

    Returns:
        Dictionary containing:
            - run_dir: Name of the evaluation run directory
            - summary: Overall run status and metrics (if available)
            - step_metrics: Per-stage pipeline metrics (if available)
            - retrieval_metrics: Retrieval quality metrics (if available)
            - manifest: Run configuration and metadata (if available)

    Raises:
        HTTPException(404): If run directory doesn't exist

    Example:
        GET /evaluation/run/250228T120000Z_abc123
    """
    run_dir = _validate_run_dir(run_dir)
    try:
        return _get_evaluation_service().load_evaluation_run(run_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/evaluation/ablation",
    summary="Get ablation study results",
    description="Get retrieval strategy comparison from ablation study",
)
def get_ablation_results() -> dict[str, Any]:
    """Get ablation study results comparing different retrieval strategies.

    Returns results from ablation studies that compare different retrieval
    approaches (e.g., hybrid vs. semantic-only vs. keyword-only).

    Returns:
        Dictionary containing:
            - ablation_runs: List of ablation results with metrics
            - is_baseline: Which run was the baseline

    Raises:
        HTTPException(404): If no evaluation runs or ablation data exists

    Example:
        GET /evaluation/ablation

        Response:
        {
            "ablation_runs": [
                {
                    "strategy": "hybrid_rrf",
                    "hit_rate_at_k": 0.85,
                    "mrr": 0.72,
                    "ndcg_at_k": 0.78,
                    "latency_p50_ms": 150,
                    "is_baseline": true
                },
                {
                    "strategy": "semantic_only",
                    "hit_rate_at_k": 0.80,
                    "mrr": 0.68,
                    "ndcg_at_k": 0.75,
                    "latency_p50_ms": 120
                }
            ]
        }
    """
    try:
        return _get_evaluation_service().load_ablation_results()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        logger.error("Failed to load ablation results: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load ablation results") from exc


@router.get(
    "/evaluation/ablation/full",
    summary="Get comprehensive ablation study results",
    description="Get all variant results from the focused ablation study with clean-state isolation",
)
def get_full_ablation_results() -> dict[str, Any]:
    """Get comprehensive ablation study results.

    Scans all clean-state runs (2026-04-04+) in the ablation directory and
    returns ranked results with per-dimension analysis and key findings.

    Returns:
        Dictionary containing:
            - runs: List of variant results ranked by NDCG
            - dimensions: Analysis grouped by dimension (pdf, chunking, retrieval, etc.)
            - findings: Key findings and recommendations
            - caching_bug_note: Explanation of the pre-fix caching issue

    Example:
        GET /evaluation/ablation/full
    """
    return _get_evaluation_service().load_full_ablation_results()


@router.get(
    "/evaluation/steps/{stage}/records",
    summary="Get detailed records for a stage",
    description="Get detailed records for debugging and drill-down",
)
def get_step_records(stage: str, limit: int = 100) -> dict[str, Any]:
    """Get detailed records for a specific pipeline stage.

    Returns individual records for a stage, useful for debugging
    and understanding which specific documents/chunks have issues.

    Args:
        stage: Pipeline stage identifier (l0, l1, l2, l3, l4, l5)
        limit: Maximum number of records to return (default: 100)

    Returns:
        Dictionary containing:
            - stage: Stage name
            - records: Array of detailed records
            - total_count: Total number of records available

    Raises:
        HTTPException(404): If no evaluation runs exist
        HTTPException(400): If stage name is invalid

    Example:
        GET /evaluation/steps/l3/records?limit=50
    """
    stage_name = _validate_stage(stage)
    limit = max(1, min(int(limit), 500))
    try:
        return _get_evaluation_service().load_step_records(stage_name, limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/evaluation/l6/records",
    summary="Get L6 answer quality per-query records",
    description="Get detailed per-query records for L6 answer quality drill-down",
)
def get_l6_records(limit: int = 100) -> dict[str, Any]:
    """Get detailed per-query L6 answer quality records.

    Returns individual query evaluation records from DeepEval including
    the query, answer, sources, and per-metric scores.

    Args:
        limit: Maximum number of records to return (default: 100)

    Returns:
        Dictionary containing:
            - records: Array of per-query L6 evaluation records
            - total_count: Total number of records available

    Raises:
        HTTPException(404): If no evaluation runs exist
        HTTPException(404): If L6 answer quality records not found

    Example:
        GET /evaluation/l6/records?limit=50
    """
    try:
        return _get_evaluation_service().load_l6_records(limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/evaluation/steps/{stage}",
    summary="Get pipeline stage metrics",
    description="Get detailed metrics for a specific pipeline stage (L0-L5)",
)
def get_step_metrics(stage: str) -> dict[str, Any]:
    """Get metrics for a specific pipeline stage.

    Retrieves detailed step-level metrics for the specified pipeline stage.
    Stages are labeled L0 through L5 representing different processing steps.

    Args:
        stage: Pipeline stage identifier (l0, l1, l2, l3, l4, l5)

    Returns:
        Dictionary containing stage-specific metrics including
        timing, document counts, and quality assessments

    Raises:
        HTTPException(404): If no evaluation runs exist
        HTTPException(400): If stage name is invalid
        HTTPException(404): If step metrics file doesn't exist

    Example:
        GET /evaluation/steps/l2

        Response:
        {
            "input_doc_count": 100,
            "output_doc_count": 95,
            "timing_ms": 250,
            "quality_score": 0.92
        }
    """
    stage_name = _validate_stage(stage)
    try:
        return _get_evaluation_service().load_step_metrics(stage_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/evaluation/answer-quality/{run_dir}",
    summary="Get DeepEval answer quality results",
    description="Get detailed LLM-judged answer quality metrics for a specific evaluation run",
)
def get_answer_quality_details(run_dir: str) -> dict[str, Any]:
    """Get detailed DeepEval results for a specific evaluation run.

    Returns per-query answer quality metrics including factual accuracy,
    completeness, clinical relevance, clarity, relevancy, and faithfulness.

    Args:
        run_dir: Name of the evaluation run directory

    Returns:
        Dictionary containing:
            - run_dir: Run directory name
            - results: List of per-query evaluation results with metrics

    Raises:
        HTTPException(404): If run directory or results file doesn't exist

    Example:
        GET /evaluation/answer-quality/250228T120000Z_abc123

        Response:
        {
            "run_dir": "250228T120000Z_abc123",
            "results": [
                {
                    "query_id": "q1",
                    "query": "What is the LDL-C target?",
                    "answer": "The target is...",
                    "metrics": {
                        "Factual Accuracy": {"score": 0.85, "reason": "..."},
                        "Completeness": {"score": 0.90, "reason": "..."}
                    }
                }
            ]
        }
    """
    run_dir = _validate_run_dir(run_dir)
    try:
        return _get_evaluation_service().load_answer_quality_details(run_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/evaluation/evaluate-single",
    summary="Evaluate a single answer",
    description="Evaluate one query-answer-context pair using DeepEval metrics (for debugging)",
)
def evaluate_single_answer(query: str, answer: str, context: str) -> dict[str, Any]:
    """Evaluate a single query-answer-context pair.

    Useful for debugging and testing specific responses. Runs all 6 DeepEval
    medical quality metrics on the provided input.

    Args:
        query: The question or query text
        answer: The generated answer to evaluate
        context: The retrieved context used to generate the answer

    Returns:
        Dictionary containing:
            - query: Input query
            - answer: Input answer
            - metrics: Dict of metric names to {score, reason}

    Raises:
        HTTPException(500): If evaluation fails

    Example:
        POST /evaluation/evaluate-single?query=...&answer=...&context=...

        Response:
        {
            "query": "What is cholesterol?",
            "answer": "Cholesterol is a lipid...",
            "metrics": {
                "Factual Accuracy": {"score": 0.85, "reason": "Well grounded..."},
                "Completeness": {"score": 0.75, "reason": "Covers key points..."},
                ...
            }
        }
    """
    from deepeval.metrics.indicator import safe_a_measure
    from deepeval.test_case import LLMTestCase

    from src.evals.metrics.medical import METRIC_SPECS, create_medical_metrics

    test_case = LLMTestCase(input=query, actual_output=answer, retrieval_context=[context])

    results = {}
    for spec, metric in zip(METRIC_SPECS, create_medical_metrics(), strict=True):
        try:
            asyncio.run(
                safe_a_measure(
                    metric,
                    test_case,
                    ignore_errors=False,
                    skip_on_missing_params=False,
                )
            )
            results[spec.key] = {
                "score": metric.score if metric.score is not None else 0.0,
                "reason": metric.reason if hasattr(metric, "reason") else None,
                "error": getattr(metric, "error", None),
            }
        except Exception as e:
            logger.error("Failed to measure metric %s: %s", spec.key, e)
            results[spec.key] = {"score": 0.0, "error": str(e)}

    return {"query": query, "answer": answer, "metrics": results}
