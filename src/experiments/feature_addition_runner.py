"""Feature addition experiment runner.

Extends the ablation framework to test feature additions
by comparing variants against a baseline.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.evals import run_assessment
from src.experiments.config import build_run_assessment_kwargs, resolve_experiment_runs
from src.experiments.experiment_config import ExperimentConfig, ExperimentVariant
from src.experiments.metric_utils import resolve_metric_key

logger = logging.getLogger(__name__)


@dataclass
class VariantResult:
    """Results from running a single variant."""

    variant_name: str
    run_dir: str
    metrics: dict[str, Any]
    config: dict[str, Any]
    timestamp: str


@dataclass
class ExperimentSummary:
    """Summary of feature addition experiment results."""

    experiment_name: str
    baseline_result: VariantResult
    variant_results: list[VariantResult]
    timestamp: str
    config: ExperimentConfig

    def get_winner(self) -> tuple[str, VariantResult]:
        """Get the winning variant based on primary metric.

        Returns:
            Tuple of (variant_name, result)
        """
        all_results = [("baseline", self.baseline_result)] + [
            (r.variant_name, r) for r in self.variant_results
        ]

        primary_metric = self.config.metrics.primary if self.config.metrics else "ndcg@5"

        def get_metric_value(metrics: dict[str, Any]) -> float:
            value = resolve_metric_key(metrics, primary_metric)
            return float(value) if isinstance(value, (int, float)) else 0.0

        winner_name, winner_result = max(all_results, key=lambda x: get_metric_value(x[1].metrics))
        return winner_name, winner_result

    def meets_target_improvement(self, variant_name: str) -> bool:
        """Check if variant meets target improvement over baseline.

        Args:
            variant_name: Name of variant to check

        Returns:
            True if variant improves by target amount over baseline
        """
        variant = next((r for r in self.variant_results if r.variant_name == variant_name), None)
        if not variant:
            return False

        target = self.config.metrics.target_improvement if self.config.metrics else 0.03
        primary_metric = self.config.metrics.primary if self.config.metrics else "ndcg@5"

        baseline_value = self._get_metric_value(self.baseline_result.metrics, primary_metric)
        variant_value = self._get_metric_value(variant.metrics, primary_metric)

        if baseline_value == 0:
            return False

        improvement = (variant_value - baseline_value) / baseline_value
        return improvement >= target

    def _get_metric_value(self, metrics: dict[str, Any], metric_name: str) -> float:
        """Extract metric value from metrics dict.

        Args:
            metrics: Metrics dictionary
            metric_name: Name of metric to extract

        Returns:
            Metric value as float
        """
        value = resolve_metric_key(metrics, metric_name)
        return float(value) if isinstance(value, (int, float)) else 0.0


def _build_experiment_for_variant(
    base_experiment: dict[str, Any],
    variant: ExperimentVariant,
    artifact_dir: str,
    collection_name_override: str | None = None,
) -> dict[str, Any]:
    """Build experiment configuration for a variant.

    Args:
        base_experiment: Base experiment configuration
        variant: Variant configuration
        artifact_dir: Directory for experiment artifacts

    Returns:
        Experiment configuration for the variant
    """
    experiment = copy.deepcopy(base_experiment)

    # Update metadata
    experiment.setdefault("metadata", {})["name"] = f"{experiment['metadata'].get('name', 'experiment')}_{variant.name}"

    # Isolate variant in its own vector store collection
    embedding_index = experiment.setdefault("embedding_index", {})
    if collection_name_override:
        embedding_index["collection_name"] = collection_name_override
        embedding_index["collection_name_suffix"] = ""
    else:
        current_collection = str(embedding_index.get("collection_name", ""))
        if current_collection:
            embedding_index["collection_name"] = f"{current_collection}_{variant.name}"
        current_suffix = str(embedding_index.get("collection_name_suffix") or "").strip()
        embedding_index["collection_name_suffix"] = f"{current_suffix}_{variant.name}" if current_suffix else variant.name

    # Update ingestion config
    if variant.chunking_strategy:
        ingestion = experiment.setdefault("ingestion", {})
        source_configs = ingestion.setdefault("source_chunk_configs", {})
        if source_configs is None:
            source_configs = {}
        # Update strategy for all source types
        for source_type in source_configs:
            source_configs[source_type]["strategy"] = variant.chunking_strategy
        # Also update default if it exists
        if "default" in source_configs:
            source_configs["default"]["strategy"] = variant.chunking_strategy

    if variant.query_understanding:
        retrieval = experiment.setdefault("retrieval", {})
        retrieval["enable_query_understanding"] = True

    # Apply variant-specific overrides
    if variant.ingestion_overrides:
        ingestion = experiment.setdefault("ingestion", {})
        ingestion.update(variant.ingestion_overrides)

    if variant.retrieval_overrides:
        retrieval = experiment.setdefault("retrieval", {})
        retrieval.update(variant.retrieval_overrides)

    # Set artifact directory
    experiment.setdefault("evaluation", {})["artifact_dir"] = artifact_dir

    return experiment


def run_variant(
    experiment_config: dict[str, Any],
    variant: ExperimentVariant,
    artifact_dir: str,
    run_assessment_fn=run_assessment,
    skip_ingestion: bool = False,
    collection_name_override: str | None = None,
) -> VariantResult:
    """Run a single variant experiment.

    Args:
        experiment_config: Base experiment configuration
        variant: Variant configuration
        artifact_dir: Directory for artifacts
        run_assessment_fn: Assessment function to run

    Returns:
        VariantResult with run results
    """
    logger.info(f"Running variant: {variant.name}")

    # Build variant-specific experiment config
    variant_experiment = _build_experiment_for_variant(
        experiment_config, variant, artifact_dir,
        collection_name_override=collection_name_override,
    )

    # Build kwargs for assessment
    kwargs = build_run_assessment_kwargs(variant_experiment)

    # Configure for clean run
    kwargs.update(
        {
            "artifact_dir": artifact_dir,
            "name": variant_experiment["metadata"]["name"],
            "force_rerun": True,
            "skip_ingestion": skip_ingestion,
            "run_retrieval_ablations": False,
            "run_hype_ablations": False,
            "run_keyword_ablations": False,
            "run_reranking_ablations": False,
        }
    )

    # Run assessment
    result = run_assessment_fn(**kwargs)

    # Extract metrics
    metrics: dict[str, Any] = {}
    if hasattr(result, "summary"):
        # Try to get retrieval metrics
        for key in ["retrieval_metrics", "metrics"]:
            if key in result.summary:
                metrics.update(result.summary[key] or {})
        # Try to get overall metrics
        for key in ["l6_retrieval_quality_metrics", "l6_answer_quality_metrics"]:
            if key in result.summary:
                metrics.update(result.summary[key] or {})

    return VariantResult(
        variant_name=variant.name,
        run_dir=str(result.run_dir),
        metrics=metrics,
        config=variant_experiment,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _chunking_key(experiment: dict[str, Any]) -> str:
    """Extract a hashable key from the chunking config."""
    configs = experiment.get("ingestion", {}).get("source_chunk_configs", {})
    strategies = tuple(sorted(
        (k, v.get("strategy", "")) for k, v in (configs or {}).items()
    ))
    return str(strategies)


def run_feature_addition_experiment(
    config: ExperimentConfig,
    base_experiment_path: str | None = None,
    base_experiment: dict[str, Any] | None = None,
    run_assessment_fn=run_assessment,
) -> ExperimentSummary:
    """Run a feature addition experiment.

    Args:
        config: Experiment configuration
        base_experiment_path: Path to base experiment YAML
        base_experiment: Base experiment config dict (overrides path)
        run_assessment_fn: Assessment function to run

    Returns:
        ExperimentSummary with all results
    """
    if base_experiment is None and base_experiment_path is not None:
        specs = resolve_experiment_runs(base_experiment_path)
        if specs:
            base_experiment = copy.deepcopy(specs[-1])

    if base_experiment is None:
        raise ValueError("Must provide either base_experiment_path or base_experiment")

    if config.baseline is None:
        raise ValueError("Experiment config must have a baseline variant")

    # Apply dataset overrides if specified
    if config.dataset_path:
        base_experiment.setdefault("dataset", {})["path"] = config.dataset_path
    if config.dataset_split is not None:
        # Empty string means "clear split filter" (use all queries)
        base_experiment.setdefault("dataset", {})["split"] = config.dataset_split or None

    # Create base artifact directory
    base_artifact_dir = Path(f"data/evals_{config.name}")
    base_artifact_dir.mkdir(parents=True, exist_ok=True)

    # Group variants by chunking strategy to avoid redundant ingestion
    baseline_exp = _build_experiment_for_variant(
        base_experiment, config.baseline, str(base_artifact_dir / "baseline"),
    )
    baseline_key = _chunking_key(baseline_exp)

    # Build ordered list: (variant, needs_ingestion, group_key)
    all_variants: list[tuple[ExperimentVariant, bool, str]] = [
        (config.baseline, True, baseline_key),
    ]
    for variant in config.variants or []:
        if variant is None:
            continue
        v_exp = _build_experiment_for_variant(
            base_experiment, variant, str(base_artifact_dir / variant.name),
        )
        v_key = _chunking_key(v_exp)
        needs_ingestion = v_key not in {key for _, _, key in all_variants}
        all_variants.append((variant, needs_ingestion, v_key))

    # Run variants: first per chunking group ingests, others reuse collection
    collection_map: dict[str, str] = {}
    results_map: dict[str, VariantResult] = {}

    for variant, needs_ingestion, group_key in all_variants:
        try:
            if needs_ingestion:
                logger.info(f"Running variant {variant.name}: full ingestion + retrieval")
                result = run_variant(
                    base_experiment,
                    variant,
                    str(base_artifact_dir / variant.name),
                    run_assessment_fn,
                    skip_ingestion=False,
                )
                # Record collection name for group reuse
                v_exp = _build_experiment_for_variant(
                    base_experiment, variant, str(base_artifact_dir / variant.name),
                )
                collection_map[group_key] = v_exp["embedding_index"]["collection_name"]
            else:
                logger.info(f"Running variant {variant.name}: skipping ingestion, reusing collection {collection_map[group_key]}")
                result = run_variant(
                    base_experiment,
                    variant,
                    str(base_artifact_dir / variant.name),
                    run_assessment_fn,
                    skip_ingestion=True,
                    collection_name_override=collection_map[group_key],
                )
            results_map[variant.name] = result
        except Exception as e:
            logger.exception(f"Variant {variant.name} failed: {e}")

    baseline_result = results_map.get(config.baseline.name)
    if baseline_result is None:
        raise RuntimeError(f"Baseline variant '{config.baseline.name}' failed to produce results")

    variant_results = [
        results_map[v.name]
        for v in (config.variants or [])
        if v is not None and v.name in results_map
    ]

    return ExperimentSummary(
        experiment_name=config.name,
        baseline_result=baseline_result,
        variant_results=variant_results,
        timestamp=datetime.now(timezone.utc).isoformat(),
        config=config,
    )


def load_and_run_experiment(
    experiment_yaml: str | Path,
    base_experiment_path: str | None = None,
    base_experiment: dict[str, Any] | None = None,
    run_assessment_fn=run_assessment,
) -> ExperimentSummary:
    """Load experiment config from YAML and run.

    Args:
        experiment_yaml: Path to experiment YAML config
        base_experiment_path: Path to base experiment YAML
        base_experiment: Base experiment config dict (overrides path)
        run_assessment_fn: Assessment function to run

    Returns:
        ExperimentSummary with all results
    """
    config = ExperimentConfig.from_yaml(experiment_yaml)
    return run_feature_addition_experiment(config, base_experiment_path, base_experiment, run_assessment_fn)
