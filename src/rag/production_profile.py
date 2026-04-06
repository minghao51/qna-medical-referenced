"""Production profile loader.

Applies the optimal ablation-study configuration to the production runtime.
This bridges the gap between experiment variants and production deployment.

Usage:
    # Via environment variable
    PRODUCTION_PROFILE=pymupdf_semantic_hybrid uv run python -m src.cli.serve

    # Via .env file
    PRODUCTION_PROFILE=pymupdf_semantic_hybrid

Supported profiles:
    - pymupdf_semantic_hybrid (optimal, NDCG=0.9976)
    - baseline (default production settings)
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROFILE_REGISTRY: dict[str, dict[str, Any]] = {}


def _load_profile_from_experiment(
    config_path: str, variant_name: str
) -> dict[str, Any] | None:
    """Load a variant config from an experiment YAML file."""
    try:
        from src.experiments.config import resolve_experiment_runs

        runs = resolve_experiment_runs(config_path, variant=variant_name)
        if runs:
            return runs[-1]
    except Exception as e:
        logger.warning(f"Failed to load profile '{variant_name}' from {config_path}: {e}")
    return None


def register_builtin_profiles() -> None:
    """Register all built-in production profiles."""
    if _PROFILE_REGISTRY:
        return  # Already registered

    baseline = _load_profile_from_experiment(
        "experiments/v1/comprehensive_ablation.yaml",
        "baseline",
    )
    if baseline:
        _PROFILE_REGISTRY["baseline"] = baseline
        logger.info("Registered production profile: baseline")
    else:
        logger.warning("Failed to register baseline production profile")

    # Optimal profile from ablation study
    optimal = _load_profile_from_experiment(
        "experiments/v1/comprehensive_ablation.yaml",
        "pymupdf_semantic_hybrid",
    )
    if optimal:
        _PROFILE_REGISTRY["pymupdf_semantic_hybrid"] = optimal
        logger.info("Registered production profile: pymupdf_semantic_hybrid")
    else:
        logger.warning("Failed to register pymupdf_semantic_hybrid profile")


def get_production_profile(name: str | None = None) -> dict[str, Any] | None:
    """Get a production profile by name.

    Args:
        name: Profile name. If None, returns None (use defaults).

    Returns:
        Experiment config dict for the profile, or None if not found.
    """
    if not name:
        return None
    register_builtin_profiles()
    return _PROFILE_REGISTRY.get(name)


def apply_production_profile(name: str | None = None) -> bool:
    """Apply a production profile to the runtime.

    This configures all runtime globals (PDF extractor, chunking, retrieval, etc.)
    to match the optimal settings from the ablation study.

    Args:
        name: Profile name. If None, does nothing.

    Returns:
        True if profile was applied, False if not found or no name given.
    """
    profile = get_production_profile(name)
    if not profile:
        if name:
            logger.warning(f"Production profile '{name}' not found, using defaults")
        return False

    from src.rag.runtime import configure_runtime_for_experiment

    configure_runtime_for_experiment(profile)
    logger.info(f"Applied production profile: {name}")
    return True
