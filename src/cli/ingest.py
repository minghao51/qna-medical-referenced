#!/usr/bin/env python3
"""Canonical ingestion pipeline CLI entrypoint using Hamilton DAG."""

from __future__ import annotations

import argparse
import asyncio
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
    """Run the full offline corpus refresh pipeline."""
    print("=" * 70)
    print("RAG DATA PIPELINE")
    print("=" * 70)
    print()

    total_start = time.time()

    from src.config import settings
    from src.rag.runtime import initialize_runtime_index

    print("[1/5] Downloading content...")
    if not skip_download:
        from src.ingestion.steps.convert_html import main as html_to_md_main
        from src.ingestion.steps.download_pdfs import main as download_pdfs_main
        from src.ingestion.steps.download_web import main as download_web_main

        asyncio.run(download_web_main())
        asyncio.run(download_pdfs_main())
        html_to_md_main(force=force_html_convert)
    print()

    print("[2/5] Loading documents...")
    from src.ingestion.steps.load_markdown import get_markdown_documents
    from src.ingestion.steps.load_pdfs import get_documents

    pdf_docs = get_documents()
    markdown_docs = get_markdown_documents()
    print(f"  Loaded {len(pdf_docs)} PDF documents, {len(markdown_docs)} Markdown docs")
    print()

    print("[3/5] Chunking documents...")
    from src.ingestion.steps.chunk_text import chunk_documents

    chunks = chunk_documents(pdf_docs)
    markdown_chunks = chunk_documents(markdown_docs)
    chunks.extend(markdown_chunks)
    print(f"  Created {len(chunks)} chunks")
    print()

    if enable_hype:
        print("[4/5] Generating HyPE questions...")
        from src.infra.llm.qwen_client import get_client
        from src.ingestion.steps.hype import generate_hype_questions_for_chunks

        hype_client = get_client()
        hype_questions = asyncio.run(
            generate_hype_questions_for_chunks(
                chunks=chunks,
                client=hype_client,
                sample_rate=settings.hyde.hype_sample_rate,
                max_chunks=settings.hyde.hype_max_chunks,
                questions_per_chunk=settings.hyde.hype_questions_per_chunk,
            )
        )
        for doc in chunks:
            if doc["id"] in hype_questions:
                doc.setdefault("metadata", {})["hypothetical_questions"] = hype_questions[doc["id"]]
        print(f"  HyPE questions generated for {len(hype_questions)} chunks")
        print()

    if enable_keyword_extraction or enable_chunk_summaries:
        print("[4/5] Enriching chunks...")
        from src.infra.llm.qwen_client import get_client
        from src.ingestion.steps.enrich_chunks import apply_enrichment_to_chunks, enrich_chunks

        enrich_client = get_client()
        enrichment_results = asyncio.run(
            enrich_chunks(
                chunks=chunks,
                client=enrich_client,
                enable_keywords=enable_keyword_extraction,
                enable_summaries=enable_chunk_summaries,
                sample_rate=settings.enrichment.keyword_extraction_sample_rate,
                max_chunks=settings.enrichment.keyword_extraction_max_chunks,
            )
        )
        enriched_count = apply_enrichment_to_chunks(
            chunks,
            enrichment_results,
            enable_keywords=enable_keyword_extraction,
            enable_summaries=enable_chunk_summaries,
        )
        print(f"  Enriched {enriched_count} chunks")
        print()

    print("[4/5] Loading reference data...")
    from src.ingestion.steps.load_reference_data import ReferenceDataLoader

    ref_loader = ReferenceDataLoader()
    ref_docs = ref_loader.load_reference_ranges_as_docs()
    print(f"  Loaded {len(ref_docs)} reference documents")
    print()

    print("[5/5] Embedding and storing vectors...")
    from src.ingestion.indexing.vector_store import get_vector_store

    all_docs = chunks + ref_docs
    print(f"  Total documents to embed: {len(all_docs)}")
    vector_store = get_vector_store()
    if force_rebuild:
        print("  Force rebuild - clearing vector store...")
        vector_store.clear()
    add_stats = vector_store.add_documents(all_docs)
    print(
        f"  Vector store: attempted={add_stats['attempted']} "
        f"inserted={add_stats['inserted']} "
        f"skipped_duplicate_id={add_stats['skipped_duplicate_id']}"
    )
    print()

    initialize_runtime_index(rebuild=False)

    total_time = time.time() - total_start

    print("=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print(f"  Total time: {total_time:.2f}s")
    print("=" * 70)


def run_hamilton_pipeline(
    skip_download: bool = False,
    force_rebuild: bool = False,
    enable_hype: bool = False,
    enable_keyword_extraction: bool = False,
    enable_chunk_summaries: bool = False,
    parallel_cores: int = 1,
) -> None:
    """Run using Hamilton DAG for parallel execution."""
    print("=" * 70)
    print("RAG DATA PIPELINE (Hamilton DAG)")
    print("=" * 70)
    print()

    total_start = time.time()

    from src.ingestion.pipeline import build_ingestion_pipeline

    project_root = Path.cwd()

    dr = build_ingestion_pipeline(
        project_root=project_root,
        enable_hype=enable_hype,
        enable_keyword_extraction=enable_keyword_extraction,
        enable_chunk_summaries=enable_chunk_summaries,
        force_rebuild=force_rebuild,
        parallel_cores=parallel_cores,
    )

    if not skip_download:
        print("[1/3] Downloading content (Bronze layer)...")
        dr.execute(final_vars=["download_web_content", "download_pdf_files"])
        print()

    print("[2/3] Parsing and chunking (Silver→Gold layer)...")
    dr.execute(final_vars=["write_gold_chunks"])
    print()

    if enable_hype or enable_keyword_extraction or enable_chunk_summaries:
        print("[3/3] Enriching chunks (Gold layer)...")
        dr.execute(final_vars=["write_enriched_chunks"])
    else:
        print("[3/3] Embedding and storing vectors (Platinum layer)...")
        dr.execute(final_vars=["embed_chunks"])
    print()

    from src.rag.runtime import initialize_runtime_index

    initialize_runtime_index(rebuild=False)

    total_time = time.time() - total_start

    print("=" * 70)
    print("PIPELINE COMPLETE (Hamilton)")
    print("=" * 70)
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

    if args.parallel > 1:
        run_hamilton_pipeline(
            skip_download=args.skip_download,
            force_rebuild=args.force,
            enable_hype=args.enable_hype,
            enable_keyword_extraction=args.enable_keyword_extraction,
            enable_chunk_summaries=args.enable_chunk_summaries,
            parallel_cores=args.parallel,
        )
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
