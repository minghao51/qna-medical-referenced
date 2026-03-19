"""Assessment subsystem exports.

Keep package import side effects light so read-only helpers such as
`src.evals.assessment.l6_contract` can be imported without optional
evaluation dependencies like `deepeval`.
"""

__all__ = [
    "DEFAULT_THRESHOLDS",
    "evaluate_answer_quality",
    "evaluate_answers_deepeval",
    "evaluate_retrieval",
    "evaluate_thresholds",
    "git_head",
    "render_summary",
    "run_assessment",
    "run_diversity_sweep",
    "run_retrieval_ablations",
    "sha256_file",
]
