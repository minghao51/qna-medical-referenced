#!/usr/bin/env python3
"""Run feature-focused ablation studies from the best known pipeline variant."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make direct script execution behave like the other repo runners.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.experiments.feature_ablation_runner import (
    REFERENCE_CONFIG,
    REFERENCE_VARIANT,
    run_feature_ablation_studies,
    write_feature_ablation_outputs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run feature-focused ablation studies")
    parser.add_argument("--config", default=REFERENCE_CONFIG)
    parser.add_argument("--variant", default=REFERENCE_VARIANT)
    parser.add_argument(
        "--dataset-path",
        default=None,
        help="Optional dataset fixture override for the ablation workflow",
    )
    parser.add_argument(
        "--dataset-split",
        default=None,
        help="Optional dataset split override; pass an empty string to use the full fixture",
    )
    parser.add_argument(
        "--skip-winner-answer-eval",
        action="store_true",
        help="Run retrieval-only studies without the answer-eval reruns for winners",
    )
    parser.add_argument(
        "--summary-dir",
        default="data/evals_feature_ablation_summary",
        help="Directory for the final JSON + Markdown summary bundle",
    )
    args = parser.parse_args()

    summary = run_feature_ablation_studies(
        config_path=args.config,
        variant_name=args.variant,
        dataset_path=args.dataset_path,
        dataset_split=args.dataset_split,
        include_answer_eval_for_winner=not args.skip_winner_answer_eval,
    )
    markdown_path, json_path = write_feature_ablation_outputs(summary, Path(args.summary_dir))
    print(f"Wrote feature ablation summary: {markdown_path}")
    print(f"Wrote feature ablation JSON: {json_path}")


if __name__ == "__main__":
    main()
