#!/usr/bin/env python3
"""Canonical ingestion pipeline CLI entrypoint using Hamilton DAG."""

from __future__ import annotations

import argparse
import time
from pathlib import Path


def run_pipeline(
    skip_download: bool = False,
    force_rebuild: bool = False,
    force_html_convert: bool = False,
    enable_hype: bool = False,
    enable_keyword_extraction: bool = False,
    enable_chunk_summaries: bool = False,
    parallel_cores: int = 1,
) -> None:
    """Run the full offline corpus refresh pipeline via the Hamilton DAG."""
    print("=" * 70)
    print("RAG DATA PIPELINE (Hamilton DAG)")
    print("=" * 70)
    print()

    total_start = time.time()

    from src.ingestion.pipeline import IngestionRunConfig, run_ingestion

    project_root = Path.cwd()

    config = IngestionRunConfig(
        project_root=project_root,
        skip_download=skip_download,
        force_rebuild=force_rebuild,
        force_html_convert=force_html_convert,
        enable_hype=enable_hype,
        enable_keyword_extraction=enable_keyword_extraction,
        enable_chunk_summaries=enable_chunk_summaries,
        parallel_cores=parallel_cores,
    )

    stages = "download → parse → chunk" if not skip_download else "parse existing → chunk"
    enrichment_enabled = enable_hype or enable_keyword_extraction or enable_chunk_summaries
    if enrichment_enabled:
        stages += " → enrich"
    stages += " → embed → index"
    print(f"Executing DAG: {stages}")

    result = run_ingestion(config)
    print()

    from src.rag import initialize_runtime_index

    initialize_runtime_index(rebuild=False)

    total_time = time.time() - total_start

    print("=" * 70)
    print("PIPELINE COMPLETE (Hamilton)")
    print("=" * 70)
    print(f"  Documents: pdf={result.pdf_document_count} markdown={result.markdown_document_count}")
    print(
        f"  Chunks: {result.chunk_count} indexed={result.inserted}"
        f" duplicates={result.skipped_duplicate_content}"
    )
    print(f"  Total time: {total_time:.2f}s")
    print("=" * 70)


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
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of cores for parallel execution (default: 1)",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Generate DAG visualization",
    )
    args = parser.parse_args()

    if args.visualize:
        from src.ingestion.pipeline import build_ingestion_pipeline, visualize_pipeline

        project_root = Path.cwd()
        dr = build_ingestion_pipeline(project_root=project_root)
        visualize_pipeline(dr, output_path=project_root / "dag.png")
        print("DAG visualization saved to dag.png")
        return

    run_pipeline(
        skip_download=args.skip_download,
        force_rebuild=args.force,
        force_html_convert=args.force_html,
        enable_hype=args.enable_hype,
        enable_keyword_extraction=args.enable_keyword_extraction,
        enable_chunk_summaries=args.enable_chunk_summaries,
        parallel_cores=args.parallel,
    )


if __name__ == "__main__":
    main()
