"""Compatibility facade for end-to-end pipeline quality assessment."""

from __future__ import annotations

from src.evals.assessment.answer_eval import evaluate_answers as _evaluate_answers
from src.evals.assessment.orchestrator import run_assessment as _run_assessment
from src.evals.assessment.reporting import (
    git_head as _git_head,
)
from src.evals.assessment.reporting import (
    render_summary as _render_summary,
)
from src.evals.assessment.reporting import (
    sha256_file as _sha256_file,
)
from src.evals.assessment.retrieval_eval import (
    evaluate_retrieval as _evaluate_retrieval,
)
from src.evals.assessment.retrieval_eval import (
    run_diversity_sweep as _run_diversity_sweep,
)
from src.evals.assessment.retrieval_eval import (
    run_retrieval_ablations as _run_retrieval_ablations,
)
from src.evals.assessment.thresholds import (
    DEFAULT_THRESHOLDS,
)
from src.evals.assessment.thresholds import (
    evaluate_thresholds as _evaluate_thresholds,
)
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
        evaluate_retrieval_fn=_evaluate_retrieval,
        evaluate_answers_fn=_evaluate_answers,
        evaluate_thresholds_fn=_evaluate_thresholds,
        git_head_fn=_git_head,
        configure_runtime_for_experiment_fn=configure_runtime_for_experiment,
        initialize_runtime_index_fn=initialize_runtime_index,
        log_assessment_to_wandb_fn=log_assessment_to_wandb,
        run_retrieval_ablations_fn=_run_retrieval_ablations,
        run_diversity_sweep_fn=_run_diversity_sweep,
        render_summary_fn=_render_summary,
        sha256_file_fn=_sha256_file,
    )


__all__ = [
    "DEFAULT_THRESHOLDS",
    "_evaluate_answers",
    "_evaluate_retrieval",
    "_evaluate_thresholds",
    "_git_head",
    "_render_summary",
    "_run_diversity_sweep",
    "_run_retrieval_ablations",
    "_sha256_file",
    "assess_l1_html_markdown_quality",
    "assess_l2_pdf_quality",
    "assess_l3_chunking_quality",
    "assess_l4_reference_quality",
    "assess_l5_index_quality",
    "audit_l0_download",
    "build_retrieval_dataset",
    "configure_runtime_for_experiment",
    "initialize_runtime_index",
    "log_assessment_to_wandb",
    "run_assessment",
]
