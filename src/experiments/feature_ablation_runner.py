"""Helpers to run feature-focused ablation studies from a reference variant."""

from __future__ import annotations

import copy
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.experiments.ablations import (
    hype_ablation_configs,
    keyword_ablation_configs,
    reranking_ablation_configs,
)
from src.experiments.comparison_report import _matched_case_comparison_paths
from src.experiments.config import build_run_assessment_kwargs, resolve_experiment_runs
from src.experiments.feature_addition_runner import (
    ensure_supported_selection_axes,
    run_assessment_in_subprocess,
    validate_execution_mode,
)

REFERENCE_CONFIG = "experiments/v1/comprehensive_ablation.yaml"
REFERENCE_VARIANT = "pymupdf_semantic_hybrid"


@dataclass(frozen=True)
class FeatureFamily:
    name: str
    artifact_dir: str
    ablation_flag: str
    summary_key: str
    baseline_variant: str
    config_builder: Any
    reingest_required: bool


FEATURE_FAMILIES: tuple[FeatureFamily, ...] = (
    FeatureFamily(
        name="keyword",
        artifact_dir="data/evals_keyword_ablation",
        ablation_flag="run_keyword_ablations",
        summary_key="keyword_ablations",
        baseline_variant="baseline",
        config_builder=keyword_ablation_configs,
        reingest_required=True,
    ),
    FeatureFamily(
        name="hype",
        artifact_dir="data/evals_hype_ablation",
        ablation_flag="run_hype_ablations",
        summary_key="hype_ablations",
        baseline_variant="hype_disabled",
        config_builder=hype_ablation_configs,
        reingest_required=True,
    ),
    FeatureFamily(
        name="reranking",
        artifact_dir="data/evals_reranking_ablation",
        ablation_flag="run_reranking_ablations",
        summary_key="reranking_ablations",
        baseline_variant="no_reranking",
        config_builder=reranking_ablation_configs,
        reingest_required=False,
    ),
)


def load_reference_experiment(
    config_path: str = REFERENCE_CONFIG, variant_name: str = REFERENCE_VARIANT
) -> dict[str, Any]:
    specs = resolve_experiment_runs(config_path, variant=variant_name)
    if not specs:
        raise ValueError(f"Variant {variant_name!r} not found in {config_path}")
    return copy.deepcopy(specs[-1])


def _base_retrieval_options(experiment: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(experiment)
    ensure_supported_selection_axes(normalized)
    kwargs = build_run_assessment_kwargs(normalized)
    return dict(kwargs.get("retrieval_options", {}))


def _family_map() -> dict[str, FeatureFamily]:
    return {family.name: family for family in FEATURE_FAMILIES}


def _run_name(reference_variant: str, family: FeatureFamily, suffix: str) -> str:
    return f"{reference_variant}_{family.name}_ablation_{suffix}"


def _finite_metric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        numeric_value = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return numeric_value if math.isfinite(numeric_value) else None


def _eligible_variant_metrics(metrics: Any) -> bool:
    if not isinstance(metrics, dict) or metrics.get("identity_status") != "verified":
        return False
    version = metrics.get("measurement_contract_version")
    if isinstance(version, bool) or version != 1:
        return False
    query_count = _finite_metric(metrics.get("query_count"))
    if query_count is None or query_count <= 0 or not query_count.is_integer():
        return False
    if _finite_metric(metrics.get("ndcg_at_k")) is None:
        return False

    for key in ("exact_chunk_hit_rate", "evidence_hit_rate", "latency_p50_ms"):
        if key in metrics and _finite_metric(metrics[key]) is None:
            return False

    success_statuses = {
        "status": "ok",
        "execution_status": "completed",
        "measurement_status": "complete",
        "quality_gate": "passed",
    }
    for key, expected_status in success_statuses.items():
        if metrics.get(key) != expected_status:
            return False
    if "measurement" in metrics:
        measurement = metrics["measurement"]
        if not isinstance(measurement, dict) or measurement.get("status") != "complete":
            return False
    error = metrics.get("error")
    return error is None or error is False or error == ""


def _winner_sort_key(metrics: dict[str, Any]) -> tuple[float, float, float, float]:
    ndcg = _finite_metric(metrics["ndcg_at_k"])
    exact_hit_rate = _finite_metric(metrics.get("exact_chunk_hit_rate"))
    evidence_hit_rate = _finite_metric(metrics.get("evidence_hit_rate"))
    latency = _finite_metric(metrics.get("latency_p50_ms"))
    assert ndcg is not None
    return (
        ndcg,
        exact_hit_rate if exact_hit_rate is not None else 0.0,
        evidence_hit_rate if evidence_hit_rate is not None else 0.0,
        -latency if latency is not None else float("-inf"),
    )


def select_best_variant(
    metrics_by_variant: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    eligible = {
        name: metrics
        for name, metrics in metrics_by_variant.items()
        if _eligible_variant_metrics(metrics)
    }
    if not eligible:
        raise ValueError(
            "No eligible ablation variant: require a positive query_count and finite ndcg_at_k"
        )
    winner_name = max(eligible, key=lambda key: _winner_sort_key(eligible[key]))
    return winner_name, eligible[winner_name]


def _validate_assessment_contract(result: Any) -> dict[str, Any]:
    summary = getattr(result, "summary", None)
    if not isinstance(summary, dict):
        raise ValueError("Ablation assessment did not provide a valid summary")
    measurement = summary.get("measurement")
    contract_version = summary.get("measurement_contract_version")
    if (
        getattr(result, "status", None) != "ok"
        or summary.get("status") != "ok"
        or not isinstance(contract_version, int)
        or isinstance(contract_version, bool)
        or contract_version != 1
        or summary.get("execution_status") != "completed"
        or not isinstance(measurement, dict)
        or measurement.get("status") != "complete"
        or summary.get("quality_gate") != "passed"
    ):
        raise ValueError(
            "Ablation assessment is not eligible: require completed, complete, passed status"
        )
    return summary


def _config_options_by_variant(
    family: FeatureFamily, experiment: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    return dict(family.config_builder(_base_retrieval_options(experiment)))


def _winner_experiment(
    experiment: dict[str, Any], family: FeatureFamily, winner_name: str
) -> dict[str, Any]:
    winner_experiment = copy.deepcopy(experiment)
    options = _config_options_by_variant(family, experiment)[winner_name]
    winner_experiment["metadata"]["name"] = _run_name(
        experiment.get("variant_name") or experiment.get("metadata", {}).get("name", "reference"),
        family,
        f"{winner_name}_answer_eval",
    )
    winner_experiment.setdefault("evaluation", {})
    winner_experiment["evaluation"]["artifact_dir"] = family.artifact_dir
    winner_experiment["evaluation"]["include_answer_eval"] = True
    winner_experiment["evaluation"]["disable_llm_judging"] = False

    retrieval = dict(winner_experiment.get("retrieval", {}))
    ingestion = dict(winner_experiment.get("ingestion", {}))
    embedding_index = dict(winner_experiment.get("embedding_index", {}))

    if family.name == "keyword":
        ingestion["enable_keyword_extraction"] = bool(options.get("enable_keyword_extraction"))
        ingestion["enable_chunk_summaries"] = bool(options.get("enable_chunk_summaries"))
        embedding_index["collection_name"] = (
            f"{embedding_index['collection_name']}_{winner_name}_answer"
        )
        embedding_index["rebuild_policy"] = "always"
    elif family.name == "hype":
        ingestion["enable_hype"] = bool(options.get("enable_hype"))
        if "hype_sample_rate" in options:
            ingestion["hype_sample_rate"] = options["hype_sample_rate"]
        retrieval["enable_hype"] = bool(options.get("enable_hype"))
        retrieval["enable_hyde"] = bool(options.get("enable_hyde"))
        embedding_index["collection_name"] = (
            f"{embedding_index['collection_name']}_{winner_name}_answer"
        )
        embedding_index["rebuild_policy"] = "always"
    else:
        retrieval.update(
            {
                "enable_diversification": bool(options.get("enable_diversification")),
                "enable_reranking": bool(options.get("enable_reranking")),
                "reranking_mode": options.get("reranking_mode", "cross_encoder"),
            }
        )

    winner_experiment["retrieval"] = retrieval
    winner_experiment["ingestion"] = ingestion
    winner_experiment["embedding_index"] = embedding_index
    return winner_experiment


def _build_ablation_experiment(
    experiment: dict[str, Any],
    family: FeatureFamily,
    variant_name: str,
    options: dict[str, Any],
    artifact_dir: str,
    order: int,
) -> dict[str, Any]:
    variant = copy.deepcopy(experiment)
    ensure_supported_selection_axes(variant)
    reference = experiment.get("variant_name") or experiment.get("metadata", {}).get(
        "name", "reference"
    )
    variant.setdefault("metadata", {})["name"] = _run_name(
        reference, family, f"{variant_name}_retrieval"
    )
    variant.setdefault("evaluation", {})["artifact_dir"] = artifact_dir
    variant["evaluation"]["include_answer_eval"] = False
    variant["evaluation"]["disable_llm_judging"] = True
    variant["embedding_index"]["collection_name"] = (
        f"{variant['embedding_index']['collection_name']}_{family.name}_{variant_name}_{order}"
    )
    variant["embedding_index"]["collection_name_suffix"] = ""
    # No strategy-only reuse: each diagnostic variant gets a new isolated index.
    variant["embedding_index"]["rebuild_policy"] = "always"

    ingestion = variant.setdefault("ingestion", {})
    retrieval = dict(variant.get("retrieval", {}))
    ingestion_only = {
        "enable_keyword_extraction",
        "enable_chunk_summaries",
        "keyword_extraction_sample_rate",
        "keyword_extraction_max_chunks",
        "enable_hype",
        "hype_sample_rate",
        "hype_questions_per_chunk",
    }
    if family.name == "keyword":
        for key in ingestion_only & options.keys():
            ingestion[key] = options[key]
    elif family.name == "hype":
        for key in ingestion_only & options.keys():
            ingestion[key] = options[key]
        if "enable_hype" in options:
            retrieval["enable_hype"] = options["enable_hype"]
    retrieval.update({key: value for key, value in options.items() if key not in ingestion_only})
    variant["retrieval"] = retrieval
    variant["skip_ingestion"] = False
    return variant


def run_feature_family(
    experiment: dict[str, Any],
    family_name: str,
    *,
    include_answer_eval_for_winner: bool = True,
    run_assessment_fn: Callable[..., Any] | None = None,
    execution_mode: str = "diagnostic",
) -> dict[str, Any]:
    validate_execution_mode(execution_mode)
    family = _family_map()[family_name]
    reference_variant = experiment.get("variant_name") or experiment.get("metadata", {}).get(
        "name", "reference"
    )
    options_by_variant = family.config_builder(_base_retrieval_options(experiment))
    metrics_by_variant: dict[str, dict[str, Any]] = {}
    run_dirs: dict[str, str] = {}
    usage_by_variant: dict[str, Any] = {}
    identity_statuses: dict[str, str] = {}
    execution_metadata: dict[str, dict[str, Any]] = {}

    for order, (variant_name, options) in enumerate(options_by_variant):
        artifact_dir = str(Path(family.artifact_dir) / reference_variant / variant_name)
        variant_experiment = _build_ablation_experiment(
            experiment, family, variant_name, options, artifact_dir, order
        )
        kwargs = build_run_assessment_kwargs(variant_experiment)
        kwargs.update(
            {
                "artifact_dir": artifact_dir,
                "name": variant_experiment["metadata"]["name"],
                "include_answer_eval": False,
                "disable_llm_judging": True,
                "export_failed_generations": False,
                "force_rerun": True,
                "skip_ingestion": False,
                "execution_mode": execution_mode,
                "run_retrieval_ablations": False,
                "run_hype_ablations": False,
                "run_keyword_ablations": False,
                "run_reranking_ablations": False,
            }
        )
        started = time.perf_counter()
        result = (
            run_assessment_fn(**kwargs)
            if run_assessment_fn is not None
            else run_assessment_in_subprocess(kwargs)
        )
        elapsed_seconds = time.perf_counter() - started
        run_dirs[variant_name] = str(result.run_dir)
        summary = getattr(result, "summary", {})
        if not isinstance(summary, dict):
            summary = {}
        identity = summary.get("identity")
        identity_status = (
            identity.get("status", "unverified") if isinstance(identity, dict) else "unverified"
        )
        identity_statuses[variant_name] = str(identity_status)
        usage = summary.get("usage_summary")
        if isinstance(usage, dict):
            usage_by_variant[variant_name] = usage
        execution_metadata[variant_name] = {
            "process_wall_time_s": elapsed_seconds,
            "cold_start_ms": None,
            "warm_state": "fresh-process; model/index warmth unverified",
            "evaluator_overhead_ms": summary.get("evaluator_overhead_ms"),
        }
        metrics = summary.get("retrieval_metrics", {})
        metrics = dict(metrics) if isinstance(metrics, dict) else {}
        metrics.update(
            {
                "identity_status": str(identity_status),
                "status": (
                    summary.get("status", getattr(result, "status", "unknown"))
                    if getattr(result, "status", "unknown") == "ok"
                    else getattr(result, "status", "unknown")
                ),
                "execution_status": summary.get("execution_status", "unknown"),
                "measurement_status": (summary.get("measurement") or {}).get("status", "unknown")
                if isinstance(summary.get("measurement"), dict)
                else "unknown",
                "quality_gate": summary.get("quality_gate", "unknown"),
                "execution_order": order,
                "execution_mode": execution_mode,
                "measurement_contract_version": summary.get("measurement_contract_version"),
                "sample_count": metrics.get("query_count"),
            }
        )
        metrics_by_variant[variant_name] = metrics

    try:
        winner_name, winner_metrics = select_best_variant(metrics_by_variant)
    except ValueError:
        winner_name, winner_metrics = None, None

    # Answer evaluation needs the same frozen index. No verified copy contract is
    # available, so never imply that a second rebuild is a matched judge run.
    winner_run_dir = None
    winner_answer_metrics = None
    baseline_metrics = metrics_by_variant.get(family.baseline_variant, {})
    return {
        "family": family.name,
        "artifact_dir": family.artifact_dir,
        "retrieval_run_dirs": run_dirs,
        "retrieval_metrics_by_variant": metrics_by_variant,
        "winner_variant": winner_name,
        "winner_metrics": winner_metrics,
        "baseline_variant": family.baseline_variant,
        "baseline_metrics": baseline_metrics,
        "identity_status_by_variant": identity_statuses,
        "execution_order": list(range(len(options_by_variant))),
        "execution_metadata_by_variant": execution_metadata,
        "matched_per_case": {
            name: _matched_case_comparison_paths(
                run_dirs.get(family.baseline_variant, ""),
                run_dirs.get(name, ""),
                ["ndcg@5", "mrr", "exact_chunk_hit_rate", "evidence_hit_rate"],
            )
            for name in run_dirs
            if name != family.baseline_variant
        },
        "comparison_mode": "exploratory_descriptive",
        "promotion_eligible": False,
        "usage_by_variant": usage_by_variant,
        "winner_answer_eval_run_dir": winner_run_dir,
        "winner_answer_eval_metrics": winner_answer_metrics,
        "answer_eval_re_ranked": False,
        "answer_eval_status": (
            "blocked; verified frozen-index copy unavailable"
            if include_answer_eval_for_winner and winner_name is not None
            else "not run"
        ),
    }


def run_feature_ablation_studies(
    *,
    config_path: str = REFERENCE_CONFIG,
    variant_name: str = REFERENCE_VARIANT,
    dataset_path: str | None = None,
    dataset_split: str | None = None,
    include_answer_eval_for_winner: bool = True,
    run_assessment_fn: Callable[..., Any] | None = None,
    execution_mode: str = "diagnostic",
) -> dict[str, Any]:
    validate_execution_mode(execution_mode)
    experiment = load_reference_experiment(config_path, variant_name)
    experiment.setdefault("dataset", {})
    if dataset_path is not None:
        experiment["dataset"]["path"] = dataset_path
    if dataset_split is not None:
        experiment["dataset"]["split"] = dataset_split
    studies: list[dict[str, Any]] = []
    for family in FEATURE_FAMILIES:
        studies.append(
            run_feature_family(
                experiment,
                family.name,
                include_answer_eval_for_winner=include_answer_eval_for_winner,
                run_assessment_fn=run_assessment_fn,
                execution_mode=execution_mode,
            )
        )
    summary = {
        "config_path": config_path,
        "reference_variant": variant_name,
        "dataset_path": experiment.get("dataset", {}).get("path"),
        "dataset_split": experiment.get("dataset", {}).get("split"),
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "execution_mode": execution_mode,
        "comparison_scope": "exploratory_descriptive; no inferential or promotion claim",
        "studies": studies,
    }
    return summary


def _delta(metrics: dict[str, Any], baseline: dict[str, Any], key: str) -> float | None:
    left = metrics.get(key)
    right = baseline.get(key)
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return None
    return float(left) - float(right)


def render_feature_ablation_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Feature Ablation Summary",
        "",
        f"- Reference config: `{summary['config_path']}`",
        f"- Reference variant: `{summary['reference_variant']}`",
        f"- Dataset path: `{summary.get('dataset_path')}`",
        f"- Dataset split: `{summary.get('dataset_split')}`",
        f"- Execution mode: `{summary.get('execution_mode', 'diagnostic')}`",
        f"- Comparison scope: `{summary.get('comparison_scope', 'legacy diagnostic')}`",
        "",
    ]
    for study in summary.get("studies", []):
        winner = study.get("winner_metrics") or {}
        baseline = study.get("baseline_metrics") or {}
        answer_metrics = study.get("winner_answer_eval_metrics") or {}
        lines.extend(
            [
                f"## {study['family'].title()}",
                "",
                f"- Retrieval runs: `{study.get('retrieval_run_dirs', study.get('retrieval_run_dir'))}`",
                f"- Descriptive leader (not promotion): `{study.get('winner_variant') or 'none eligible'}`",
                f"- Baseline: `{study['baseline_variant']}`",
                f"- Comparison scope: `{study.get('comparison_mode', 'legacy diagnostic')}`",
                f"- Delta NDCG@K: `{_delta(winner, baseline, 'ndcg_at_k')}`",
                f"- Delta MRR: `{_delta(winner, baseline, 'mrr')}`",
                f"- Delta exact chunk hit rate: `{_delta(winner, baseline, 'exact_chunk_hit_rate')}`",
                f"- Delta evidence hit rate: `{_delta(winner, baseline, 'evidence_hit_rate')}`",
                f"- Delta latency p50 ms: `{_delta(winner, baseline, 'latency_p50_ms')}`",
            ]
        )
        if answer_metrics:
            lines.append(f"- Winner answer-eval run: `{study.get('winner_answer_eval_run_dir')}`")
            lines.append(
                f"- Winner answer-eval status: `{answer_metrics.get('status', 'unknown')}`"
            )
            lines.append(
                "- Retrieval winner stayed winner after answer eval: "
                "`not re-ranked across all variants; winner-only answer eval by design`"
            )
        else:
            lines.append(f"- Answer evaluation: `{study.get('answer_eval_status', 'not run')}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_feature_ablation_outputs(
    summary: dict[str, Any], output_dir: str | Path
) -> tuple[Path, Path]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    markdown_path = output_root / "feature_ablation_summary.md"
    json_path = output_root / "feature_ablation_summary.json"
    markdown_path.write_text(render_feature_ablation_summary(summary), encoding="utf-8")
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return markdown_path, json_path
