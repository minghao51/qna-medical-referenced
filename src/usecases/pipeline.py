#!/usr/bin/env python3
"""Backward-compatible pipeline entrypoint.

This module keeps the historical ``src.usecases.pipeline`` CLI path while
delegating execution to the canonical implementation in ``src.cli.ingest``.
"""

from __future__ import annotations

from src.cli.ingest import main as _ingest_main
from src.cli.ingest import run_pipeline

__all__ = ["run_pipeline"]

if __name__ == "__main__":
    _ingest_main()
