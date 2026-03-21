"""L1 HTML/Markdown quality checks."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from src.config import DATA_RAW_DIR
from src.evals.checks.shared import count_false, safe_mean, safe_median
from src.ingestion.artifacts import load_source_artifact


def _float_metric(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def assess_l1_html_markdown_quality(data_raw_dir: Path | None = None) -> dict[str, Any]:
    data_dir = Path(data_raw_dir or DATA_RAW_DIR)
    html_files = sorted(data_dir.glob("*.html"))
    records: list[dict[str, Any]] = []
    retention_ratios: list[float] = []
    empty_md = 0
    boilerplate_terms = ["cookie", "privacy", "menu", "navigation", "subscribe", "footer"]

    for html_path in html_files:
        md_path = html_path.with_suffix(".md")
        html_raw = html_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html_raw, "html.parser")
        html_visible = soup.get_text("\n", strip=True)
        html_chars = len(html_visible)
        md_text = md_path.read_text(encoding="utf-8", errors="ignore") if md_path.exists() else ""
        artifact = load_source_artifact("html", html_path.stem) or {}
        artifact_meta = artifact.get("metadata", {})
        structured_blocks = artifact.get("structured_blocks", [])
        md_chars = len(md_text.strip())
        retention = (md_chars / html_chars) if html_chars > 0 else 0.0
        retention_ratios.append(retention)
        if md_chars < 40:
            empty_md += 1
        lowered = md_text.lower()
        boilerplate_hits = sum(lowered.count(term) for term in boilerplate_terms)
        records.append(
            {
                "file": html_path.name,
                "md_exists": md_path.exists(),
                "html_visible_chars": html_chars,
                "md_chars": md_chars,
                "retention_ratio": retention,
                "markdown_heading_count": len(
                    re.findall(r"^#{1,6}\s", md_text, flags=re.MULTILINE)
                ),
                "markdown_list_lines": len(re.findall(r"^\s*[-*]\s", md_text, flags=re.MULTILINE)),
                "markdown_link_count": md_text.count("]("),
                "boilerplate_hits": boilerplate_hits,
                "boilerplate_suspicion": (boilerplate_hits / max(1, md_chars)),
                "content_density": artifact_meta.get("text_density", 0.0),
                "page_type": artifact_meta.get("page_type"),
                "heading_preservation_rate": (
                    len(re.findall(r"^#{1,6}\s", md_text, flags=re.MULTILINE))
                    / max(
                        1,
                        sum(
                            1 for block in structured_blocks if block.get("block_type") == "heading"
                        ),
                    )
                ),
                "table_preservation_rate": (
                    md_text.count("| --- |")
                    / max(
                        1,
                        sum(1 for block in structured_blocks if block.get("block_type") == "table"),
                    )
                ),
                "html_extractor_strategy": artifact_meta.get(
                    "html_extractor_strategy", "trafilatura_bs"
                ),
                "selected_extractor": artifact_meta.get("selected_extractor", "trafilatura"),
                "cascade_depth": artifact_meta.get("cascade_depth", 1),
            }
        )

    cascade_depths = [int(r.get("cascade_depth", 1)) for r in records]
    aggregate = {
        "pairs_evaluated": len(records),
        "markdown_missing_rate": (count_false(records, "md_exists") / len(records))
        if records
        else 0.0,
        "markdown_empty_rate": (empty_md / len(records)) if records else 0.0,
        "retention_ratio_median": safe_median(retention_ratios),
        "retention_ratio_mean": safe_mean(retention_ratios),
        "low_retention_rate": (sum(1 for r in retention_ratios if r < 0.05) / len(retention_ratios))
        if retention_ratios
        else 0.0,
        "content_density_mean": safe_mean(
            [_float_metric(r.get("content_density", 0.0)) for r in records]
        ),
        "boilerplate_ratio_mean": safe_mean(
            [_float_metric(r.get("boilerplate_suspicion", 0.0)) for r in records]
        ),
        "heading_preservation_rate_mean": safe_mean(
            [_float_metric(r.get("heading_preservation_rate", 0.0)) for r in records]
        ),
        "table_preservation_rate_mean": safe_mean(
            [_float_metric(r.get("table_preservation_rate", 0.0)) for r in records]
        ),
        "page_classification_distribution": dict(
            Counter(str(r.get("page_type", "unknown")) for r in records)
        ),
        "html_extractor_strategy": dict(
            Counter(str(r.get("html_extractor_strategy", "trafilatura_bs")) for r in records)
        ),
        "selected_extractor_distribution": dict(
            Counter(str(r.get("selected_extractor", "unknown")) for r in records)
        ),
        "cascade_depth_mean": safe_mean([float(d) for d in cascade_depths]),
        "cascade_depth_distribution": dict(Counter(cascade_depths)),
    }
    findings = []
    if _float_metric(aggregate.get("markdown_empty_rate")) > 0.1:
        findings.append(
            {"severity": "warning", "message": "High empty markdown rate", "stage": "L1"}
        )
    return {"aggregate": aggregate, "records": records, "findings": findings}
