"""Comparison report generation for feature addition experiments.

Generates reports comparing variants against baseline.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from src.experiments.feature_addition_runner import ExperimentSummary, VariantResult
from src.experiments.metric_utils import resolve_metric_key


def _format_metric_value(value: float | None) -> str:
    """Format metric value for display.

    Args:
        value: Metric value

    Returns:
        Formatted string
    """
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _format_delta(baseline: float | None, variant: float | None) -> str:
    """Format delta between baseline and variant.

    Args:
        baseline: Baseline value
        variant: Variant value

    Returns:
        Formatted delta string with +/- prefix
    """
    if baseline is None or variant is None:
        return "N/A"

    delta = variant - baseline
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.4f}"


def _format_percent_delta(baseline: float | None, variant: float | None) -> str:
    """Format percent delta between baseline and variant.

    Args:
        baseline: Baseline value
        variant: Variant value

    Returns:
        Formatted percent delta string
    """
    if baseline is None or variant is None or baseline == 0:
        return "N/A"

    delta = ((variant - baseline) / baseline) * 100
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.2f}%"


def _case_fingerprint(row: dict[str, Any]) -> str | None:
    query = row.get("query")
    if not isinstance(query, str):
        return None
    identity = {
        "query": query,
        "query_id": row.get("query_id"),
        "dataset_origin": row.get("dataset_origin"),
        "label_confidence": row.get("label_confidence"),
        "expected_sources": row.get("expected_sources", []),
        "expected_keywords": row.get("expected_keywords", []),
        "evidence_phrase": row.get("evidence_phrase"),
        "expected_chunk_id": row.get("expected_chunk_id"),
        "answerable": row.get("answerable"),
    }
    canonical = json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_case_metrics(run_dir: str) -> dict[str, dict[str, Any]]:
    result_path = Path(run_dir) / "retrieval_results.jsonl"
    if not result_path.is_file():
        return {}
    cases: dict[str, dict[str, Any]] = {}
    for line in result_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        fingerprint = _case_fingerprint(row)
        metrics = row.get("metrics")
        if fingerprint and isinstance(metrics, dict) and fingerprint not in cases:
            cases[fingerprint] = metrics
    return cases


def _matched_case_comparison_paths(
    baseline_run_dir: str, variant_run_dir: str, metrics: list[str]
) -> dict[str, Any]:
    baseline_rows = _load_case_metrics(baseline_run_dir)
    variant_rows = _load_case_metrics(variant_run_dir)
    matched_keys = sorted(baseline_rows.keys() & variant_rows.keys())
    pairs: list[dict[str, Any]] = []
    for index, fingerprint in enumerate(matched_keys, start=1):
        values: dict[str, Any] = {}
        for metric in metrics:
            left = resolve_metric_key(baseline_rows[fingerprint], metric)
            right = resolve_metric_key(variant_rows[fingerprint], metric)
            if (
                isinstance(left, bool)
                or isinstance(right, bool)
                or not isinstance(left, (int, float))
                or not isinstance(right, (int, float))
                or not math.isfinite(float(left))
                or not math.isfinite(float(right))
            ):
                continue
            values[metric] = {
                "baseline": float(left),
                "variant": float(right),
                "delta": float(right) - float(left),
            }
        if values:
            # Use an ordinal rather than exporting a possibly identifying case ID.
            pairs.append({"case": index, "metrics": values})
    return {"sample_count": len(pairs), "cases": pairs}


def _matched_case_comparison(
    baseline: VariantResult, variant: VariantResult, metrics: list[str]
) -> dict[str, Any]:
    return _matched_case_comparison_paths(baseline.run_dir, variant.run_dir, metrics)


def generate_comparison_report(summary: ExperimentSummary) -> str:
    """Generate markdown comparison report.

    Args:
        summary: Experiment summary

    Returns:
        Markdown report string
    """
    lines = [
        f"# Feature Addition Experiment Report: {summary.experiment_name}",
        "",
        f"**Generated:** {summary.timestamp}",
        "",
        "## Configuration",
        "",
        f"- **Primary Metric:** {summary.config.metrics.primary if summary.config.metrics else 'ndcg@5'}",
        f"- **Target Improvement:** {summary.config.metrics.target_improvement * 100 if summary.config.metrics else 3:.1f}%",
        "",
        "## Baseline Results",
        "",
        "Exploratory matched comparisons only; no inferential, equivalence, or promotion claim.",
        "",
        f"- **Execution mode:** `{summary.baseline_result.execution_mode}`",
        f"- **Identity status:** `{summary.baseline_result.identity_status}`",
        f"- **Run Directory:** `{summary.baseline_result.run_dir}`",
        f"- **Sample count:** `{summary.baseline_result.sample_count}`",
        f"- **Execution order:** `{summary.baseline_result.execution_order}`",
        f"- **Execution metadata:** `{summary.baseline_result.execution_metadata}`",
        "",
    ]

    # Add baseline metrics
    primary_metric = summary.config.metrics.primary if summary.config.metrics else "ndcg@5"
    baseline_metrics = summary.baseline_result.metrics

    lines.extend(
        [
            "### Metrics",
            "",
            "| Metric | Baseline |",
            "|--------|----------|",
        ]
    )

    # Display key metrics
    key_metrics = [primary_metric]
    if summary.config.metrics and summary.config.metrics.secondary:
        key_metrics.extend(summary.config.metrics.secondary)

    # Add standard metrics if not already included
    for metric in ["mrr", "exact_chunk_hit_rate", "evidence_hit_rate", "latency_p50_ms"]:
        if metric not in key_metrics:
            key_metrics.append(metric)

    for metric in key_metrics:
        baseline_value = resolve_metric_key(baseline_metrics, metric)
        baseline_formatted = _format_metric_value(baseline_value)
        lines.append(f"| {metric} | {baseline_formatted} |")

    lines.extend(
        [
            "",
            "## Variant Results",
            "",
        ]
    )

    # Add variant comparisons
    for variant_result in summary.variant_results:
        lines.extend(
            [
                f"### {variant_result.variant_name}",
                "",
                f"- **Run Directory:** `{variant_result.run_dir}`",
                f"- **Identity status:** `{variant_result.identity_status}`",
                f"- **Sample count:** `{variant_result.sample_count}`",
                f"- **Execution order:** `{variant_result.execution_order}`",
                f"- **Execution metadata:** `{variant_result.execution_metadata}`",
                "",
                "### Metrics vs Baseline",
                "",
                "| Metric | Baseline | Variant | Delta | % Change | Target Met |",
                "|--------|----------|---------|-------|----------|-----------|",
            ]
        )

        for metric in key_metrics:
            baseline_value = resolve_metric_key(baseline_metrics, metric)
            variant_value = resolve_metric_key(variant_result.metrics, metric)

            baseline_formatted = _format_metric_value(baseline_value)
            variant_formatted = _format_metric_value(variant_value)
            delta = _format_delta(baseline_value, variant_value)
            percent_delta = _format_percent_delta(baseline_value, variant_value)

            # Check if target met (only for primary metric)
            if metric == primary_metric:
                target_met = summary.meets_target_improvement(variant_result.variant_name)
                target_status = "✅ Yes" if target_met else "❌ No"
            else:
                target_status = "N/A"

            lines.append(
                f"| {metric} | {baseline_formatted} | {variant_formatted} | {delta} | {percent_delta} | {target_status} |"
            )

        matched = _matched_case_comparison(summary.baseline_result, variant_result, key_metrics)
        lines.extend(
            [
                f"Matched per-case sample count: {matched['sample_count']}",
                "",
            ]
        )
        if matched["sample_count"]:
            lines.append("Per-case values are local to this report and descriptive only.")
            lines.append("")
        lines.append("")

    # An unverified index/source identity is diagnostic evidence, not a winner cohort.
    try:
        winner_name, winner_result = summary.get_winner()
    except ValueError:
        winner_name, winner_result = None, None
    lines.extend(
        [
            "## Overall Results",
            "",
            (
                f"**Descriptive leader (not promotion-eligible):** {winner_name}"
                if winner_name is not None
                else "**No eligible winner:** source/index identity or required measurements are unverified."
            ),
            "",
        ]
    )

    if winner_name not in {None, "baseline"} and winner_result is not None:
        winner_metrics = winner_result.metrics
        winner_value = resolve_metric_key(winner_metrics, primary_metric)
        baseline_value = resolve_metric_key(baseline_metrics, primary_metric)

        if winner_value is not None and baseline_value is not None and baseline_value != 0:
            improvement = ((winner_value - baseline_value) / baseline_value) * 100
            lines.append(f"**Improvement over baseline:** {improvement:.2f}%")

    lines.extend(
        [
            "",
            "## Recommendations",
            "",
        ]
    )

    # Generate recommendations based on results
    any_target_met = any(
        summary.meets_target_improvement(v.variant_name) for v in summary.variant_results
    )

    if any_target_met:
        lines.extend(
            [
                "✅ **One or more variants met the target improvement threshold.**",
                "",
                "This diagnostic comparison is not a deployment or promotion recommendation.",
            ]
        )
    else:
        lines.extend(
            [
                "No variant is promotion-eligible from this exploratory comparison.",
                "",
                "Consider:",
                "- Tuning variant parameters",
                "- Combining successful features from multiple variants",
                "- Investigating why features didn't improve performance",
            ]
        )

    lines.append("")

    return "\n".join(lines)


def generate_json_report(summary: ExperimentSummary) -> dict[str, Any]:
    """Generate JSON comparison report.

    Args:
        summary: Experiment summary

    Returns:
        Dictionary report suitable for JSON serialization
    """
    primary_metric = summary.config.metrics.primary if summary.config.metrics else "ndcg@5"
    try:
        winner_name, winner_result = summary.get_winner()
    except ValueError:
        winner_name, winner_result = None, None
    key_metrics = [primary_metric]
    if summary.config.metrics and summary.config.metrics.secondary:
        key_metrics.extend(summary.config.metrics.secondary)

    return {
        "experiment_name": summary.experiment_name,
        "timestamp": summary.timestamp,
        "config": summary.config.to_dict(),
        "baseline": {
            "name": summary.baseline_result.variant_name,
            "run_dir": summary.baseline_result.run_dir,
            "metrics": summary.baseline_result.metrics,
            "identity_status": summary.baseline_result.identity_status,
            "execution_order": summary.baseline_result.execution_order,
            "sample_count": summary.baseline_result.sample_count,
            "execution_metadata": summary.baseline_result.execution_metadata,
            "usage_summary": summary.baseline_result.usage_summary,
        },
        "variants": [
            {
                "name": v.variant_name,
                "run_dir": v.run_dir,
                "metrics": v.metrics,
                "identity_status": v.identity_status,
                "execution_order": v.execution_order,
                "sample_count": v.sample_count,
                "execution_mode": v.execution_mode,
                "execution_metadata": v.execution_metadata,
                "usage_summary": v.usage_summary,
                "matched_per_case": _matched_case_comparison(
                    summary.baseline_result, v, key_metrics
                ),
                "meets_target": summary.meets_target_improvement(v.variant_name),
            }
            for v in summary.variant_results
        ],
        "winner": (
            {
                "name": winner_name,
                "run_dir": winner_result.run_dir,
                "metrics": winner_result.metrics,
                "selection_kind": "descriptive_leader",
                "promotion_eligible": False,
            }
            if winner_result is not None
            else None
        ),
        "comparison_contract": {
            "mode": "exploratory_descriptive",
            "inferential_claims": False,
            "promotion_claims": False,
            "cold_start_ms": None,
            "warm_state": "not verified",
            "evaluator_overhead_ms": None,
            "execution_order": [
                summary.baseline_result.execution_order,
                *[variant.execution_order for variant in summary.variant_results],
            ],
            "sample_counts": {
                summary.baseline_result.variant_name: summary.baseline_result.sample_count,
                **{
                    variant.variant_name: variant.sample_count
                    for variant in summary.variant_results
                },
            },
        },
        "primary_metric": primary_metric,
        "target_improvement": summary.config.metrics.target_improvement
        if summary.config.metrics
        else 0.03,
        "any_target_met": any(
            summary.meets_target_improvement(v.variant_name) for v in summary.variant_results
        ),
    }


def write_comparison_reports(
    summary: ExperimentSummary,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Write comparison reports to files.

    Args:
        summary: Experiment summary
        output_dir: Directory to write reports

    Returns:
        Tuple of (markdown_path, json_path)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write markdown report
    markdown_path = output_dir / f"{summary.experiment_name}_report.md"
    markdown_report = generate_comparison_report(summary)
    markdown_path.write_text(markdown_report, encoding="utf-8")

    # Write JSON report
    json_path = output_dir / f"{summary.experiment_name}_report.json"
    json_report = generate_json_report(summary)
    json_path.write_text(json.dumps(json_report, indent=2), encoding="utf-8")

    return markdown_path, json_path
