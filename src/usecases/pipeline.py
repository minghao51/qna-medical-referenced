#!/usr/bin/env python3
"""Backward-compatible pipeline entrypoint.

This module keeps the historical ``src.usecases.pipeline`` CLI path while
delegating execution to the canonical implementation in ``src.cli.ingest``.
"""

from __future__ import annotations

import argparse

from src.cli.ingest import run_pipeline as run_ingest_pipeline


def run_pipeline(
    skip_download: bool = False,
    force_rebuild: bool = False,
    force_html_convert: bool = False,
    enable_hype: bool = False,
    enable_keyword_extraction: bool = False,
    enable_chunk_summaries: bool = False,
) -> None:
    """Run the canonical ingestion pipeline."""
    run_ingest_pipeline(
        skip_download=skip_download,
        force_rebuild=force_rebuild,
        force_html_convert=force_html_convert,
        enable_hype=enable_hype,
        enable_keyword_extraction=enable_keyword_extraction,
        enable_chunk_summaries=enable_chunk_summaries,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RAG data pipeline")
    parser.add_argument("--skip-download", action="store_true", help="Skip L0 web content download")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild of vector store (clear and re-embed all)",
    )
    parser.add_argument(
        "--force-html",
        action="store_true",
        help="Force re-convert HTML to Markdown (overwrite existing)",
    )
    parser.add_argument(
        "--enable-hype",
        action="store_true",
        help="Enable HyPE question generation at ingestion time",
    )
    parser.add_argument(
        "--enable-keyword-extraction",
        action="store_true",
        help="Enable LLM-based medical entity keyword extraction at ingestion time",
    )
    parser.add_argument(
        "--enable-chunk-summaries",
        action="store_true",
        help="Enable LLM-based chunk summarization at ingestion time",
    )
    args = parser.parse_args()

    run_pipeline(
        skip_download=args.skip_download,
        force_rebuild=args.force,
        force_html_convert=args.force_html,
        enable_hype=args.enable_hype,
        enable_keyword_extraction=args.enable_keyword_extraction,
        enable_chunk_summaries=args.enable_chunk_summaries,
    )


if __name__ == "__main__":
    main()
