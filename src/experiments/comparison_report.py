"""Comparison report generation for feature addition experiments.

Generates reports comparing variants against baseline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.experiments.feature_addition_runner import ExperimentSummary
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
        f"- **Run Directory:** `{summary.baseline_result.run_dir}`",
        "",
    ]

    # Add baseline metrics
    primary_metric = summary.config.metrics.primary if summary.config.metrics else "ndcg@5"
    baseline_metrics = summary.baseline_result.metrics

    lines.extend([
        "### Metrics",
        "",
        "| Metric | Baseline |",
        "|--------|----------|",
    ])

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

    lines.extend([
        "",
        "## Variant Results",
        "",
    ])

    # Add variant comparisons
    for variant_result in summary.variant_results:
        lines.extend([
            f"### {variant_result.variant_name}",
            "",
            f"- **Run Directory:** `{variant_result.run_dir}`",
            "",
            "### Metrics vs Baseline",
            "",
            "| Metric | Baseline | Variant | Delta | % Change | Target Met |",
            "|--------|----------|---------|-------|----------|-----------|",
        ])

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

        lines.append("")

    # Add winner section
    winner_name, winner_result = summary.get_winner()
    lines.extend([
        "## Overall Results",
        "",
        f"**Winner:** {winner_name}",
        "",
    ])

    if winner_name != "baseline":
        winner_metrics = winner_result.metrics
        winner_value = resolve_metric_key(winner_metrics, primary_metric)
        baseline_value = resolve_metric_key(baseline_metrics, primary_metric)

        if winner_value is not None and baseline_value is not None and baseline_value != 0:
            improvement = ((winner_value - baseline_value) / baseline_value) * 100
            lines.append(
                f"**Improvement over baseline:** {improvement:.2f}%"
            )

    lines.extend([
        "",
        "## Recommendations",
        "",
    ])

    # Generate recommendations based on results
    any_target_met = any(
        summary.meets_target_improvement(v.variant_name)
        for v in summary.variant_results
    )

    if any_target_met:
        lines.extend([
            "✅ **One or more variants met the target improvement threshold.**",
            "",
            "Consider deploying the winning variant to production.",
        ])
    else:
        lines.extend([
            "❌ **No variants met the target improvement threshold.**",
            "",
            "Consider:",
            "- Tuning variant parameters",
            "- Combining successful features from multiple variants",
            "- Investigating why features didn't improve performance",
        ])

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
    winner_name, winner_result = summary.get_winner()

    return {
        "experiment_name": summary.experiment_name,
        "timestamp": summary.timestamp,
        "config": summary.config.to_dict(),
        "baseline": {
            "name": summary.baseline_result.variant_name,
            "run_dir": summary.baseline_result.run_dir,
            "metrics": summary.baseline_result.metrics,
        },
        "variants": [
            {
                "name": v.variant_name,
                "run_dir": v.run_dir,
                "metrics": v.metrics,
                "meets_target": summary.meets_target_improvement(v.variant_name),
            }
            for v in summary.variant_results
        ],
        "winner": {
            "name": winner_name,
            "run_dir": winner_result.run_dir,
            "metrics": winner_result.metrics,
        },
        "primary_metric": primary_metric,
        "target_improvement": summary.config.metrics.target_improvement if summary.config.metrics else 0.03,
        "any_target_met": any(
            summary.meets_target_improvement(v.variant_name)
            for v in summary.variant_results
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
