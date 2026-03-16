"""Reporting helpers for evaluation runs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def git_head() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def sha256_file(path: str | Path | None) -> str | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


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
        lines.append(f"- {stage.upper()}: {json.dumps(agg, ensure_ascii=False)}")
    lines.extend(
        [
            "",
            "## Retrieval Metrics (L6)",
            f"- {json.dumps(retrieval_metrics, ensure_ascii=False)}",
            "",
            "## L6 Answer Quality",
            f"- {json.dumps(l6_answer_quality_metrics, ensure_ascii=False)}",
            "",
            "## Threshold Failures",
        ]
    )
    if failed_thresholds:
        for failure in failed_thresholds:
            lines.append(
                f"- {failure['metric']}: value={failure['value']} "
                f"threshold_{failure['threshold_op']}={failure['threshold_value']}"
            )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"
