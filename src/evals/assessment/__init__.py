"""Assessment subsystem exports.

Keep package import side effects light so read-only helpers such as
`src.evals.assessment.l6_contract` can be imported without optional
evaluation dependencies like `deepeval`. Names are resolved lazily from
their canonical modules.
"""

_EXPORTS = {
    "DEFAULT_THRESHOLDS": "src.evals.assessment.thresholds",
    "evaluate_answer_quality": "src.evals.assessment.answer_eval",
    "evaluate_answer_quality_async": "src.evals.assessment.answer_eval",
    "evaluate_retrieval": "src.evals.assessment.retrieval_eval",
    "evaluate_thresholds": "src.evals.assessment.thresholds",
    "git_head": "src.evals.assessment.reporting",
    "render_summary": "src.evals.assessment.reporting",
    "run_assessment": "src.evals.assessment.orchestrator",
    "sha256_file": "src.evals.assessment.reporting",
    # Ablation runners live in experiments/ (Phase 2, roadmap P2.2)
    "hype_ablation_configs": "src.experiments.ablations",
    "keyword_ablation_configs": "src.experiments.ablations",
    "reranking_ablation_configs": "src.experiments.ablations",
    "retrieval_ablation_configs": "src.experiments.ablations",
    "run_diversity_sweep": "src.experiments.ablations",
    "run_hype_ablations": "src.experiments.ablations",
    "run_hype_ablations_with_reingest": "src.experiments.ablations",
    "run_keyword_ablations": "src.experiments.ablations",
    "run_keyword_ablations_with_reingest": "src.experiments.ablations",
    "run_reranking_ablations": "src.experiments.ablations",
    "run_retrieval_ablations": "src.experiments.ablations",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    if name in _EXPORTS:
        import importlib

        module = importlib.import_module(_EXPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
