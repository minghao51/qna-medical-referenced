"""Helpers to run feature-focused ablation studies from a reference variant."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.evals import run_assessment
from src.evals.assessment.retrieval_eval import (
    hype_ablation_configs,
    keyword_ablation_configs,
    reranking_ablation_configs,
)
from src.experiments.config import build_run_assessment_kwargs, resolve_experiment_runs

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
    kwargs = build_run_assessment_kwargs(experiment)
    return dict(kwargs.get("retrieval_options", {}))


def _family_map() -> dict[str, FeatureFamily]:
    return {family.name: family for family in FEATURE_FAMILIES}


def _run_name(reference_variant: str, family: FeatureFamily, suffix: str) -> str:
    return f"{reference_variant}_{family.name}_ablation_{suffix}"


def _winner_sort_key(metrics: dict[str, Any]) -> tuple[float, float, float, float]:
    latency = metrics.get("latency_p50_ms")
    latency_value = float(latency) if isinstance(latency, (int, float)) else float("inf")
    return (
        float(metrics.get("ndcg_at_k", 0.0) or 0.0),
        float(metrics.get("exact_chunk_hit_rate", 0.0) or 0.0),
        float(metrics.get("evidence_hit_rate", 0.0) or 0.0),
        -latency_value,
    )


def select_best_variant(metrics_by_variant: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    if not metrics_by_variant:
        raise ValueError("Cannot select best variant from empty metrics")
    winner_name = max(metrics_by_variant, key=lambda key: _winner_sort_key(metrics_by_variant[key]))
    return winner_name, metrics_by_variant[winner_name]


def _config_options_by_variant(family: FeatureFamily, experiment: dict[str, Any]) -> dict[str, dict[str, Any]]:
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
        embedding_index["collection_name"] = f"{embedding_index['collection_name']}_{winner_name}_answer"
        embedding_index["rebuild_policy"] = "always"
    elif family.name == "hype":
        ingestion["enable_hype"] = bool(options.get("enable_hype"))
        if "hype_sample_rate" in options:
            ingestion["hype_sample_rate"] = options["hype_sample_rate"]
        retrieval["enable_hype"] = bool(options.get("enable_hype"))
        retrieval["enable_hyde"] = bool(options.get("enable_hyde"))
        embedding_index["collection_name"] = f"{embedding_index['collection_name']}_{winner_name}_answer"
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


def run_feature_family(
    experiment: dict[str, Any],
    family_name: str,
    *,
    include_answer_eval_for_winner: bool = True,
    run_assessment_fn=run_assessment,
) -> dict[str, Any]:
    family = _family_map()[family_name]
    kwargs = build_run_assessment_kwargs(experiment)
    reference_variant = experiment.get("variant_name") or experiment.get("metadata", {}).get(
        "name", "reference"
    )
    kwargs.update(
        {
            "artifact_dir": family.artifact_dir,
            "name": _run_name(reference_variant, family, "retrieval"),
            "include_answer_eval": False,
            "disable_llm_judging": True,
            "export_failed_generations": False,
            "force_rerun": True,
            "run_retrieval_ablations": False,
            "run_hype_ablations": False,
            "run_keyword_ablations": False,
            "run_reranking_ablations": False,
        }
    )
    kwargs[family.ablation_flag] = True
    retrieval_result = run_assessment_fn(**kwargs)
    family_metrics = dict(retrieval_result.summary.get(family.summary_key, {}) or {})
    winner_name, winner_metrics = select_best_variant(family_metrics)

    winner_run_dir: str | None = None
    winner_answer_metrics: dict[str, Any] | None = None
    if include_answer_eval_for_winner:
        winner_experiment = _winner_experiment(experiment, family, winner_name)
        winner_kwargs = build_run_assessment_kwargs(winner_experiment)
        winner_kwargs.update(
            {
                "artifact_dir": family.artifact_dir,
                "name": winner_experiment["metadata"]["name"],
                "include_answer_eval": True,
                "disable_llm_judging": False,
                "export_failed_generations": False,
                "force_rerun": True,
                "run_retrieval_ablations": False,
                "run_hype_ablations": False,
                "run_keyword_ablations": False,
                "run_reranking_ablations": False,
            }
        )
        winner_result = run_assessment_fn(**winner_kwargs)
        winner_run_dir = str(winner_result.run_dir)
        winner_answer_metrics = dict(
            winner_result.summary.get("l6_answer_quality_metrics", {}) or {}
        )

    baseline_metrics = family_metrics.get(family.baseline_variant, {})
    return {
        "family": family.name,
        "artifact_dir": family.artifact_dir,
        "retrieval_run_dir": str(retrieval_result.run_dir),
        "retrieval_metrics_by_variant": family_metrics,
        "winner_variant": winner_name,
        "winner_metrics": winner_metrics,
        "baseline_variant": family.baseline_variant,
        "baseline_metrics": baseline_metrics,
        "winner_answer_eval_run_dir": winner_run_dir,
        "winner_answer_eval_metrics": winner_answer_metrics,
        "answer_eval_re_ranked": False,
    }


def run_feature_ablation_studies(
    *,
    config_path: str = REFERENCE_CONFIG,
    variant_name: str = REFERENCE_VARIANT,
    dataset_path: str | None = None,
    dataset_split: str | None = None,
    include_answer_eval_for_winner: bool = True,
    run_assessment_fn=run_assessment,
) -> dict[str, Any]:
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
            )
        )
    summary = {
        "config_path": config_path,
        "reference_variant": variant_name,
        "dataset_path": experiment.get("dataset", {}).get("path"),
        "dataset_split": experiment.get("dataset", {}).get("split"),
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
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
        "",
    ]
    for study in summary.get("studies", []):
        winner = study.get("winner_metrics", {})
        baseline = study.get("baseline_metrics", {})
        answer_metrics = study.get("winner_answer_eval_metrics") or {}
        lines.extend(
            [
                f"## {study['family'].title()}",
                "",
                f"- Retrieval run: `{study['retrieval_run_dir']}`",
                f"- Winner: `{study['winner_variant']}`",
                f"- Baseline: `{study['baseline_variant']}`",
                f"- Delta NDCG@K: `{_delta(winner, baseline, 'ndcg_at_k')}`",
                f"- Delta MRR: `{_delta(winner, baseline, 'mrr')}`",
                f"- Delta exact chunk hit rate: `{_delta(winner, baseline, 'exact_chunk_hit_rate')}`",
                f"- Delta evidence hit rate: `{_delta(winner, baseline, 'evidence_hit_rate')}`",
                f"- Delta latency p50 ms: `{_delta(winner, baseline, 'latency_p50_ms')}`",
            ]
        )
        if answer_metrics:
            lines.append(
                f"- Winner answer-eval run: `{study.get('winner_answer_eval_run_dir')}`"
            )
            lines.append(
                f"- Winner answer-eval status: `{answer_metrics.get('status', 'unknown')}`"
            )
            lines.append(
                "- Retrieval winner stayed winner after answer eval: "
                "`not re-ranked across all variants; winner-only answer eval by design`"
            )
        else:
            lines.append("- Winner answer-eval run: `not run`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_feature_ablation_outputs(summary: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    markdown_path = output_root / "feature_ablation_summary.md"
    json_path = output_root / "feature_ablation_summary.json"
    markdown_path.write_text(render_feature_ablation_summary(summary), encoding="utf-8")
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return markdown_path, json_path
