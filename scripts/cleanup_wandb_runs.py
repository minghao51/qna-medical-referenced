#!/usr/bin/env python3
"""Delete W&B runs via API.

Usage:
    # Dry run (default)
    python scripts/cleanup_wandb_runs.py --project qna-medical-referenced

    # Delete all runs
    python scripts/cleanup_wandb_runs.py --project qna-medical-referenced --delete-all

    # Keep last N runs
    python scripts/cleanup_wandb_runs.py --project qna-medical-referenced --keep-last 10

    # Delete before date
    python scripts/cleanup_wandb_runs.py --project qna-medical-referenced --before 2025-03-01
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

try:
    import importlib

    wandb = importlib.import_module("wandb")
except ImportError as exc:
    print(f"Error: {exc}", file=sys.stderr)
    print("Install wandb: uv add wandb", file=sys.stderr)
    sys.exit(1)

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete W&B runs via API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--project",
        required=True,
        help="W&B project name",
    )
    parser.add_argument(
        "--entity",
        help="W&B entity/team name (optional)",
    )
    parser.add_argument(
        "--delete-all",
        action="store_true",
        help="Delete all runs in project",
    )
    parser.add_argument(
        "--keep-last",
        type=int,
        metavar="N",
        help="Keep only N most recent runs",
    )
    parser.add_argument(
        "--before",
        type=str,
        metavar="DATE",
        help="Delete runs older than DATE (format: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be deleted without actually deleting (default: True)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually perform deletion (requires explicit flag)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments."""
    if args.no_dry_run and not (args.delete_all or args.keep_last or args.before):
        logger.error("Must specify --delete-all, --keep-last, or --before when using --no-dry-run")
        sys.exit(1)

    if args.before:
        try:
            datetime.strptime(args.before, "%Y-%m-%d")
        except ValueError:
            logger.error("Invalid date format for --before. Use YYYY-MM-DD")
            sys.exit(1)

    if args.delete_all and args.keep_last:
        logger.error("Cannot use both --delete-all and --keep-last")
        sys.exit(1)


def get_runs(project: str, entity: str | None) -> list:
    """Fetch all runs for the project."""
    api = wandb.Api()
    path = f"{entity}/{project}" if entity else project
    logger.info(f"Fetching runs from {path}")
    runs = list(api.runs(path))
    logger.info(f"Found {len(runs)} runs")
    return runs


def filter_runs_by_keep_last(runs: list, keep_last: int) -> list:
    """Filter runs to keep only N most recent."""
    # Sort by creation time (most recent first)
    sorted_runs = sorted(runs, key=lambda r: r.created_at, reverse=True)
    runs_to_delete = sorted_runs[keep_last:]
    logger.info(f"Keeping last {keep_last} runs, deleting {len(runs_to_delete)} runs")
    return runs_to_delete


def filter_runs_by_date(runs: list, before_date: str) -> list:
    """Filter runs to delete those older than specified date."""
    cutoff = datetime.strptime(before_date, "%Y-%m-%d")
    runs_to_delete = [
        r
        for r in runs
        if datetime.strptime(r.created_at.split(".")[0], "%Y-%m-%dT%H:%M:%S") < cutoff
    ]
    logger.info(f"Deleting {len(runs_to_delete)} runs created before {before_date}")
    return runs_to_delete


def delete_run(run, dry_run: bool) -> bool:
    """Delete a single run."""
    try:
        if dry_run:
            logger.info(f"[DRY RUN] Would delete: {run.name} ({run.id})")
            return True
        logger.info(f"Deleting: {run.name} ({run.id})")
        run.delete()
        return True
    except Exception as exc:
        logger.error(f"Failed to delete {run.id}: {exc}")
        return False


def main() -> int:
    args = parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Override dry-run if explicitly set
    dry_run = args.dry_run
    if args.no_dry_run:
        dry_run = False

    if dry_run:
        logger.info("DRY RUN MODE - No actual deletion will occur")
    else:
        logger.warning("LIVE DELETION MODE - This will permanently delete runs!")

    validate_args(args)

    # Fetch runs
    try:
        runs = get_runs(args.project, args.entity)
    except Exception as exc:
        logger.error(f"Failed to fetch runs: {exc}")
        return 1

    if not runs:
        logger.info("No runs found in project")
        return 0

    # Determine which runs to delete
    if args.delete_all:
        runs_to_delete = runs
        logger.info(f"Will delete all {len(runs)} runs")
    elif args.keep_last:
        runs_to_delete = filter_runs_by_keep_last(runs, args.keep_last)
    elif args.before:
        runs_to_delete = filter_runs_by_date(runs, args.before)
    else:
        # Default dry-run behavior: show what would be deleted
        runs_to_delete = runs
        logger.info(f"Would delete {len(runs)} runs (use --delete-all, --keep-last, or --before)")

    if not runs_to_delete:
        logger.info("No runs to delete")
        return 0

    # Confirm before actual deletion
    if not dry_run:
        response = input(f"Confirm deletion of {len(runs_to_delete)} runs? [yes/N]: ")
        if response.lower() != "yes":
            logger.info("Aborted by user")
            return 0

    # Delete runs
    logger.info(f"Deleting {len(runs_to_delete)} runs...")
    success_count = 0
    for run in runs_to_delete:
        if delete_run(run, dry_run):
            success_count += 1

    logger.info(
        f"Successfully {'processed' if dry_run else 'deleted'} {success_count}/{len(runs_to_delete)} runs"
    )

    if dry_run:
        logger.info("To actually delete, re-run with --no-dry-run")

    return 0


if __name__ == "__main__":
    sys.exit(main())
