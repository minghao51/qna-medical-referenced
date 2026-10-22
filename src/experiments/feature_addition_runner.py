"""Feature addition experiment runner.

Extends the ablation framework to test feature additions
by comparing variants against a baseline.
"""

from __future__ import annotations

import copy
import json
import logging
import math
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlsplit

from src.experiments.addition_config import ExperimentConfig, ExperimentVariant
from src.experiments.config import build_run_assessment_kwargs, resolve_experiment_runs
from src.experiments.metric_utils import resolve_metric_key

logger = logging.getLogger(__name__)


_SUPPORTED_GENERATION_IMPLEMENTATION = "existing"
_SUPPORTED_HARNESS = "deterministic_rag"


def ensure_supported_selection_axes(config: dict[str, Any]) -> None:
    """Default legacy configs to executed axes and reject unsupported selections."""
    generation_implementation = config.get(
        "generation_implementation", _SUPPORTED_GENERATION_IMPLEMENTATION
    )
    harness = config.get("harness", _SUPPORTED_HARNESS)
    if generation_implementation != _SUPPORTED_GENERATION_IMPLEMENTATION:
        raise ValueError("Unsupported generation implementation; supported: existing")
    if harness != _SUPPORTED_HARNESS:
        raise ValueError("Unsupported evaluation harness; supported: deterministic_rag")
    config["generation_implementation"] = generation_implementation
    config["harness"] = harness


@dataclass
class VariantResult:
    """Results from running a single variant."""

    variant_name: str
    run_dir: str
    metrics: dict[str, Any]
    config: dict[str, Any]
    timestamp: str
    measurement_contract_version: int | None = None
    status: str = "unknown"
    summary_status: str = "unknown"
    execution_status: str = "unknown"
    measurement_status: str = "unknown"
    quality_gate: str = "unknown"
    identity_status: str = "unverified"
    execution_order: int | None = None
    sample_count: int | None = None
    execution_mode: str = "diagnostic"
    usage_summary: dict[str, Any] | None = None
    execution_metadata: dict[str, Any] | None = None


@dataclass
class ExperimentSummary:
    """Summary of feature addition experiment results."""

    experiment_name: str
    baseline_result: VariantResult
    variant_results: list[VariantResult]
    failed_variants: list[dict[str, str]]
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

        eligible_results = []
        for name, result in all_results:
            if not self._is_eligible(result):
                continue
            metric_value = self._get_metric_value(result.metrics, primary_metric)
            if metric_value is not None:
                eligible_results.append((name, result, metric_value))
        if not eligible_results:
            raise ValueError(
                f"No eligible winner: no completed, measured variant has a finite {primary_metric}"
            )
        winner_name, winner_result, _ = max(eligible_results, key=lambda item: item[2])
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

        if not self._is_eligible(self.baseline_result) or not self._is_eligible(variant):
            return False

        baseline_value = self._get_metric_value(self.baseline_result.metrics, primary_metric)
        variant_value = self._get_metric_value(variant.metrics, primary_metric)
        if baseline_value is None or variant_value is None or baseline_value == 0:
            return False

        improvement = (variant_value - baseline_value) / baseline_value
        return improvement >= target

    @staticmethod
    def _is_eligible(result: VariantResult) -> bool:
        return (
            isinstance(result.measurement_contract_version, int)
            and not isinstance(result.measurement_contract_version, bool)
            and result.measurement_contract_version == 1
            and result.status == "ok"
            and result.summary_status == "ok"
            and result.execution_status == "completed"
            and result.measurement_status == "complete"
            and result.quality_gate == "passed"
            and result.identity_status == "verified"
        )

    def _get_metric_value(self, metrics: dict[str, Any], metric_name: str) -> float | None:
        """Extract metric value from metrics dict.

        Args:
            metrics: Metrics dictionary
            metric_name: Name of metric to extract

        Returns:
            Finite metric value, or None when unavailable or invalid
        """
        value = resolve_metric_key(metrics, metric_name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        try:
            numeric_value = float(value)
        except (OverflowError, TypeError, ValueError):
            return None
        return numeric_value if math.isfinite(numeric_value) else None

    def format_failures_report(self) -> str:
        if not self.failed_variants:
            return ""
        lines = ["Failed variants:"]
        for entry in self.failed_variants:
            lines.append(f"  - {entry['variant']}: {entry['error']}")
        return "\n".join(lines)


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
    ensure_supported_selection_axes(experiment)

    # Update metadata
    experiment.setdefault("metadata", {})["name"] = (
        f"{experiment['metadata'].get('name', 'experiment')}_{variant.name}"
    )

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
        embedding_index["collection_name_suffix"] = (
            f"{current_suffix}_{variant.name}" if current_suffix else variant.name
        )

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


def validate_execution_mode(
    execution_mode: str, *, index_snapshot_path: str | Path | None = None
) -> None:
    """Reject unsupported modes and require an explicit frozen export for benchmarks."""
    if execution_mode not in {"diagnostic", "benchmark", "replay"}:
        raise ValueError(f"Unsupported execution mode: {execution_mode}")
    if execution_mode == "benchmark" and not index_snapshot_path:
        raise ValueError(
            "Benchmark mode cannot verify a frozen collection snapshot without an explicit "
            "index_snapshot_path; pass a verified --index-snapshot-path export"
        )


def _validate_worker_payload(value: Any) -> None:
    """Keep credential-bearing configuration out of temporary worker request files."""
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_").replace("_", "")
            if (
                normalized in {"key", "token", "auth", "bearer"}
                or any(
                    marker in normalized
                    for marker in (
                        "apikey",
                        "password",
                        "secret",
                        "credential",
                        "authorization",
                        "cookie",
                        "headers",
                    )
                )
                or normalized.endswith("token")
            ):
                raise ValueError("Credential-bearing fields are not allowed in worker payloads")
            _validate_worker_payload(item)
    elif isinstance(value, list):
        for item in value:
            _validate_worker_payload(item)
    elif isinstance(value, str) and "://" in value:
        endpoint = urlsplit(value)
        if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ValueError("Credential-bearing endpoints are not allowed in worker payloads")


def run_assessment_in_subprocess(kwargs: dict[str, Any]):
    """Run one assessment in a fresh process with private writable index/cache paths."""
    kwargs = dict(kwargs)
    if kwargs.get("index_snapshot_path") is not None:
        kwargs["index_snapshot_path"] = str(kwargs["index_snapshot_path"])
    ensure_supported_selection_axes(kwargs)
    validate_execution_mode(
        str(kwargs.get("execution_mode", "diagnostic")),
        index_snapshot_path=kwargs.get("index_snapshot_path"),
    )
    _validate_worker_payload(kwargs)
    with tempfile.TemporaryDirectory(prefix="qna-eval-attempt-") as temporary_dir:
        workspace = Path(temporary_dir)
        response_path = workspace / "response.json"
        request_payload = json.dumps(kwargs, ensure_ascii=False, allow_nan=False)
        environment = os.environ.copy()
        environment["APP__STORAGE__CHROMA_PERSIST_DIRECTORY"] = str(workspace / "chroma")
        environment["QNA_EVAL_ATTEMPT_WORKSPACE"] = str(workspace)
        environment["APP__STORAGE__CHROMA_SERVER_HOST"] = ""
        environment["APP__DEEPEVAL__DEEPEVAL_CACHE_DIR"] = str(workspace / "deepeval-cache")
        command = [
            sys.executable,
            "-m",
            "src.cli.eval_pipeline",
            "--_assessment-worker-result",
            str(response_path),
        ]
        completed = subprocess.run(
            command,
            check=False,
            cwd=Path(__file__).resolve().parents[2],
            input=request_payload,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
        )
        if completed.returncode != 0 or not response_path.is_file():
            raise RuntimeError(
                f"Isolated assessment process failed (exit code {completed.returncode})"
            )
        response = json.loads(response_path.read_text(encoding="utf-8"))
        if not isinstance(response, dict) or response.get("status") == "worker_error":
            raise RuntimeError("Isolated assessment returned an invalid result")
        return SimpleNamespace(
            run_dir=Path(response["run_dir"]),
            status=response["status"],
            failed_thresholds=[{} for _ in range(response.get("failed_threshold_count", 0))],
            summary=response.get("summary", {}),
        )


def run_variant(
    experiment_config: dict[str, Any],
    variant: ExperimentVariant,
    artifact_dir: str,
    run_assessment_fn: Callable[..., Any] | None = None,
    skip_ingestion: bool = False,
    collection_name_override: str | None = None,
    execution_mode: str = "diagnostic",
    execution_order: int | None = None,
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
    evaluation_config = experiment_config.get("evaluation", {})
    validate_execution_mode(
        execution_mode,
        index_snapshot_path=(
            evaluation_config.get("index_snapshot_path")
            if isinstance(evaluation_config, dict)
            else None
        ),
    )
    logger.info("Running %s variant: %s", execution_mode, variant.name)

    # Build variant-specific experiment config
    variant_experiment = _build_experiment_for_variant(
        experiment_config,
        variant,
        artifact_dir,
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
            "execution_mode": execution_mode,
            "execution_order": execution_order,
        }
    )

    # Production paths always cross a fresh process boundary. An injected callable
    # is reserved for deterministic unit tests and local composition.
    started = time.perf_counter()
    result = (
        run_assessment_fn(**kwargs)
        if run_assessment_fn is not None
        else run_assessment_in_subprocess(kwargs)
    )
    elapsed_seconds = time.perf_counter() - started

    # Extract metrics and measurement status
    summary = getattr(result, "summary", {})
    if not isinstance(summary, dict):
        summary = {}
    metrics: dict[str, Any] = {}
    # Try to get retrieval metrics
    for key in ["retrieval_metrics", "metrics"]:
        if key in summary:
            metrics.update(summary[key] or {})
    # Try to get overall metrics
    for key in ["l6_retrieval_quality_metrics", "l6_answer_quality_metrics"]:
        if key in summary:
            metrics.update(summary[key] or {})
    measurement = summary.get("measurement")
    if not isinstance(measurement, dict):
        measurement = {}
    contract_version = summary.get("measurement_contract_version")
    identity = summary.get("identity")
    if not isinstance(identity, dict):
        identity = {}
    query_count = metrics.get("query_count")
    sample_count = (
        int(query_count)
        if isinstance(query_count, (int, float))
        and not isinstance(query_count, bool)
        and math.isfinite(float(query_count))
        and float(query_count).is_integer()
        and query_count >= 0
        else None
    )

    return VariantResult(
        variant_name=variant.name,
        run_dir=str(result.run_dir),
        metrics=metrics,
        config=variant_experiment,
        timestamp=datetime.now(UTC).isoformat(),
        measurement_contract_version=(
            contract_version
            if isinstance(contract_version, int) and not isinstance(contract_version, bool)
            else None
        ),
        status=getattr(result, "status", "unknown") or "unknown",
        summary_status=summary.get("status", "unknown") or "unknown",
        execution_status=summary.get("execution_status", "unknown") or "unknown",
        measurement_status=measurement.get("status", "unknown") or "unknown",
        quality_gate=summary.get("quality_gate", "unknown") or "unknown",
        identity_status=str(identity.get("status", "unverified")),
        execution_order=execution_order,
        sample_count=sample_count,
        execution_mode=execution_mode,
        usage_summary=(
            summary.get("usage_summary") if isinstance(summary.get("usage_summary"), dict) else None
        ),
        execution_metadata={
            "process_wall_time_s": elapsed_seconds,
            "cold_start_ms": None,
            "warm_state": "fresh-process; model/index warmth unverified",
            "evaluator_overhead_ms": summary.get("evaluator_overhead_ms"),
            "index_execution": summary.get("index_execution"),
        },
    )


def run_feature_addition_experiment(
    config: ExperimentConfig,
    base_experiment_path: str | None = None,
    base_experiment: dict[str, Any] | None = None,
    run_assessment_fn: Callable[..., Any] | None = None,
    execution_mode: str = "diagnostic",
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
    if execution_mode not in {"diagnostic", "benchmark", "replay"}:
        validate_execution_mode(execution_mode)
    if base_experiment is None and base_experiment_path is not None:
        specs = resolve_experiment_runs(base_experiment_path)
        if specs:
            base_experiment = copy.deepcopy(specs[-1])

    if base_experiment is None:
        raise ValueError("Must provide either base_experiment_path or base_experiment")
    base_experiment = copy.deepcopy(base_experiment)
    ensure_supported_selection_axes(base_experiment)
    evaluation_config = base_experiment.get("evaluation", {})
    validate_execution_mode(
        execution_mode,
        index_snapshot_path=(
            evaluation_config.get("index_snapshot_path")
            if isinstance(evaluation_config, dict)
            else None
        ),
    )

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

    # Never reuse an index on a strategy-only key. Each run gets a fresh process
    # and private writable store; fixed-index reuse remains blocked until snapshot
    # identity can be verified before and after a run.
    all_variants = [config.baseline] + [v for v in (config.variants or []) if v is not None]
    results_map: dict[str, VariantResult] = {}
    failed_variants: list[dict[str, str]] = []

    for execution_order, variant in enumerate(all_variants):
        try:
            result = run_variant(
                base_experiment,
                variant,
                str(base_artifact_dir / variant.name),
                run_assessment_fn,
                skip_ingestion=False,
                execution_mode=execution_mode,
                execution_order=execution_order,
            )
            results_map[variant.name] = result
        except Exception as exc:
            logger.error("Variant %s failed (%s)", variant.name, type(exc).__name__)
            failed_variants.append(
                {"variant": variant.name, "error": f"isolated run failed ({type(exc).__name__})"}
            )

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
        failed_variants=failed_variants,
        timestamp=datetime.now(UTC).isoformat(),
        config=config,
    )


def load_and_run_experiment(
    experiment_yaml: str | Path,
    base_experiment_path: str | None = None,
    base_experiment: dict[str, Any] | None = None,
    run_assessment_fn: Callable[..., Any] | None = None,
    execution_mode: str = "diagnostic",
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
    return run_feature_addition_experiment(
        config,
        base_experiment_path,
        base_experiment,
        run_assessment_fn,
        execution_mode=execution_mode,
    )
