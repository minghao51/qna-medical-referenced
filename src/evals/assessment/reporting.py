"""Reporting helpers for evaluation runs."""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def git_head() -> str | None:
    try:
        result = subprocess.run(  # nosec B603 B607
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception as e:
        logger.debug("Failed to get git HEAD: %s", e)
        return None


def sha256_file(path: str | Path | None) -> str | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def _format_dict_as_table(d: dict[str, Any], indent: str = "  ") -> list[str]:
    if not d:
        return [f"{indent}(empty)"]
    keys = list(d.keys())
    lines = [
        f"{indent}| Metric | Value |",
        f"{indent}|--------|-------|",
    ]
    for k in keys:
        v = d[k]
        if isinstance(v, dict):
            lines.append(f"{indent}| **{k}** | |")
            lines.extend(_format_dict_as_table(v, indent + "  "))
        elif isinstance(v, list):
            lines.append(f"{indent}| {k} | `{json.dumps(v, ensure_ascii=False)}` |")
        elif isinstance(v, float):
            lines.append(f"{indent}| {k} | {v:.4f} |")
        else:
            lines.append(f"{indent}| {k} | `{v}` |")
    return lines


def render_summary(
    *,
    step_metrics: dict[str, Any],
    retrieval_metrics: dict[str, Any],
    l6_answer_quality_metrics: dict[str, Any],
    dataset_stats: dict[str, Any],
    failed_thresholds: list[dict[str, Any]],
) -> str:
    lines = [
        "# Pipeline Quality Assessment Summary",
        "",
        "## Dataset",
        f"- Fixture records: {dataset_stats.get('fixture_records', 0)}",
        f"- Synthetic records: {dataset_stats.get('synthetic_records', 0)}",
        f"- Merged records: {dataset_stats.get('merged_records', 0)}",
        "",
        "## Step Metrics",
    ]
    for stage in ["l0", "l1", "l2", "l3", "l4", "l5"]:
        agg = step_metrics.get(stage, {}).get("aggregate", {})
        lines.append(f"### {stage.upper()}")
        lines.extend(_format_dict_as_table(agg))
        lines.append("")
    lines.extend(
        [
            "## Retrieval Metrics (L6)",
        ]
    )
    lines.extend(_format_dict_as_table(retrieval_metrics))
    lines.extend(
        [
            "",
            "## L6 Answer Quality",
        ]
    )
    lines.extend(_format_dict_as_table(l6_answer_quality_metrics))
    lines.extend(
        [
            "",
            "## Threshold Failures",
        ]
    )
    if failed_thresholds:
        lines.append("| Metric | Value | Threshold Op | Threshold Value |")
        lines.append("|--------|-------|-------------|-----------------|")
        for failure in failed_thresholds:
            lines.append(
                f"| {failure['metric']} | {failure['value']} "
                f"| {failure['threshold_op']} | {failure['threshold_value']} |"
            )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"
