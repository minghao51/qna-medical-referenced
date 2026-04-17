#!/usr/bin/env python3
"""CLI entry point for running feature addition experiments."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for direct execution
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.experiments.comparison_report import write_comparison_reports
from src.experiments.feature_addition_runner import load_and_run_experiment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Main CLI entry point.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = argparse.ArgumentParser(
        description="Run feature addition experiments for medical Q&A retrieval",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "experiment_config",
        type=str,
        help="Path to experiment YAML config file",
    )
    parser.add_argument(
        "--base-experiment",
        type=str,
        default=None,
        help="Path to base experiment YAML (if not using default)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="experiments/outputs",
        help="Directory to write comparison reports",
    )
    parser.add_argument(
        "--dataset-path",
        type=str,
        default=None,
        help="Override dataset path",
    )
    parser.add_argument(
        "--dataset-split",
        type=str,
        default=None,
        help="Override dataset split",
    )

    args = parser.parse_args()

    # Validate experiment config exists
    experiment_path = Path(args.experiment_config)
    if not experiment_path.exists():
        logger.error(f"Experiment config not found: {experiment_path}")
        return 1

    try:
        # Load and run experiment
        logger.info(f"Loading experiment config from: {experiment_path}")
        summary = load_and_run_experiment(
            experiment_yaml=experiment_path,
            base_experiment_path=args.base_experiment,
        )

        # Write comparison reports
        output_dir = Path(args.output_dir)
        markdown_path, json_path = write_comparison_reports(summary, output_dir)

        logger.info(f"Experiment completed successfully!")
        logger.info(f"Markdown report: {markdown_path}")
        logger.info(f"JSON report: {json_path}")

        # Print summary
        winner_name, _ = summary.get_winner()
        logger.info(f"Winner: {winner_name}")

        any_target_met = any(
            summary.meets_target_improvement(v.variant_name)
            for v in summary.variant_results
        )
        if any_target_met:
            logger.info("✅ Target improvement met by one or more variants!")
        else:
            logger.info("❌ No variants met the target improvement threshold.")

        return 0

    except Exception as e:
        logger.exception(f"Experiment failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
