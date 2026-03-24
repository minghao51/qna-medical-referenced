"""Compatibility facade for end-to-end pipeline quality assessment."""

from __future__ import annotations

from src.evals.assessment.answer_eval import evaluate_answer_quality
from src.evals.assessment.orchestrator import run_assessment as _run_assessment
from src.evals.assessment.reporting import git_head, render_summary, sha256_file
from src.evals.assessment.retrieval_eval import (
    evaluate_retrieval,
    run_diversity_sweep,
    run_retrieval_ablations,
)
from src.evals.assessment.thresholds import DEFAULT_THRESHOLDS, evaluate_thresholds
from src.evals.dataset_builder import build_retrieval_dataset
from src.evals.step_checks import (
    assess_l1_html_markdown_quality,
    assess_l2_pdf_quality,
    assess_l3_chunking_quality,
    assess_l4_reference_quality,
    assess_l5_index_quality,
    audit_l0_download,
)
from src.experiments.wandb_tracking import log_assessment_to_wandb
from src.rag.runtime import configure_runtime_for_experiment, initialize_runtime_index


def run_assessment(**kwargs):
    return _run_assessment(
        **kwargs,
        audit_l0_download_fn=audit_l0_download,
        assess_l1_html_markdown_quality_fn=assess_l1_html_markdown_quality,
        assess_l2_pdf_quality_fn=assess_l2_pdf_quality,
        assess_l3_chunking_quality_fn=assess_l3_chunking_quality,
        assess_l4_reference_quality_fn=assess_l4_reference_quality,
        assess_l5_index_quality_fn=assess_l5_index_quality,
        build_retrieval_dataset_fn=build_retrieval_dataset,
        evaluate_retrieval_fn=evaluate_retrieval,
        evaluate_answers_fn=evaluate_answer_quality,
        evaluate_thresholds_fn=evaluate_thresholds,
        git_head_fn=git_head,
        configure_runtime_for_experiment_fn=configure_runtime_for_experiment,
        initialize_runtime_index_fn=initialize_runtime_index,
        log_assessment_to_wandb_fn=log_assessment_to_wandb,
        run_retrieval_ablations_fn=run_retrieval_ablations,
        run_diversity_sweep_fn=run_diversity_sweep,
        render_summary_fn=render_summary,
        sha256_file_fn=sha256_file,
    )


__all__ = [
    "DEFAULT_THRESHOLDS",
    "assess_l1_html_markdown_quality",
    "assess_l2_pdf_quality",
    "assess_l3_chunking_quality",
    "assess_l4_reference_quality",
    "assess_l5_index_quality",
    "audit_l0_download",
    "build_retrieval_dataset",
    "configure_runtime_for_experiment",
    "evaluate_answer_quality",
    "evaluate_retrieval",
    "evaluate_thresholds",
    "git_head",
    "initialize_runtime_index",
    "log_assessment_to_wandb",
    "render_summary",
    "run_assessment",
    "run_diversity_sweep",
    "run_retrieval_ablations",
    "sha256_file",
]
