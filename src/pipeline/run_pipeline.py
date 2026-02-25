#!/usr/bin/env python3
"""Deprecated compatibility wrapper for the ingestion pipeline CLI."""

import warnings

from src.ingestion.pipeline import main, run_pipeline

__all__ = ["main", "run_pipeline"]

warnings.warn(
    "src.pipeline.run_pipeline is deprecated; use 'python -m src.cli.ingest' or src.ingestion.pipeline.",
    DeprecationWarning,
    stacklevel=2,
)


if __name__ == "__main__":
    main()
