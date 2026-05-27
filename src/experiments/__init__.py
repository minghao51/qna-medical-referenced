"""Experiment configuration helpers."""

from src.experiments.config import (
    build_run_assessment_kwargs,
    compute_retrieval_delta,
    load_experiment_file,
    resolve_experiment_runs,
)

_LAZY_EXPORTS = {
    "log_assessment_to_wandb": ("src.experiments.wandb_tracking", "log_assessment_to_wandb"),
    "render_feature_ablation_summary": (
        "src.experiments.feature_ablation_runner",
        "render_feature_ablation_summary",
    ),
    "run_feature_ablation_studies": (
        "src.experiments.feature_ablation_runner",
        "run_feature_ablation_studies",
    ),
    "write_feature_ablation_outputs": (
        "src.experiments.feature_ablation_runner",
        "write_feature_ablation_outputs",
    ),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = __import__(module_name, fromlist=[attr_name])
    return getattr(module, attr_name)


__all__ = [
    "build_run_assessment_kwargs",
    "compute_retrieval_delta",
    "load_experiment_file",
    "log_assessment_to_wandb",
    "render_feature_ablation_summary",
    "resolve_experiment_runs",
    "run_feature_ablation_studies",
    "write_feature_ablation_outputs",
]
