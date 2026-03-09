#!/usr/bin/env python3
"""Offline pipeline orchestration for ingestion and runtime index refresh.

This module coordinates the end-to-end refresh flow across ingestion steps,
indexing, and final RAG runtime initialization. The underlying step
implementations remain in ``src.ingestion``.

Usage:
    python -m src.usecases.pipeline           # Run full pipeline
    python -m src.usecases.pipeline --force   # Force rebuild of vector store
    python -m src.usecases.pipeline --skip-download  # Skip L0 download
"""

import argparse
import asyncio
import time


def run_pipeline(
    skip_download: bool = False, force_rebuild: bool = False, force_html_convert: bool = False
) -> None:
    """Run the full offline corpus refresh pipeline in sequence."""
    print("=" * 70)
    print("RAG DATA PIPELINE")
    print("=" * 70)
    print()

    total_start = time.time()

    print("=" * 70)
    print("STEP SUMMARY")
    print("=" * 70)
    print(f"L0: Download web content     {'[SKIPPED]' if skip_download else '[RUNNING]'}")
    print(f"L0b: Download PDFs           {'[SKIPPED]' if skip_download else '[RUNNING]'}")
    print(f"L1: HTML -> Markdown         {'[RUNNING]' if not skip_download else '[SKIPPED]'}")
    print("L2: Load PDF documents       [RUNNING]")
    print("L3: Chunk documents          [RUNNING]")
    print("L4: Load reference data      [RUNNING]")
    print(f"L5: Embed & store vectors    {'[FORCE REBUILD]' if force_rebuild else '[RUNNING]'}")
    print("L6: Initialize RAG           [RUNNING]")
    print("=" * 70)
    print()

    from src.ingestion.indexing.vector_store import get_vector_store
    from src.ingestion.steps.chunk_text import chunk_documents
    from src.ingestion.steps.convert_html import main as html_to_md_main
    from src.ingestion.steps.download_pdfs import main as download_pdfs_main
    from src.ingestion.steps.download_web import main as download_main
    from src.ingestion.steps.load_markdown import get_markdown_documents
    from src.ingestion.steps.load_pdfs import get_documents
    from src.ingestion.steps.load_reference_data import ReferenceDataLoader
    from src.rag.runtime import initialize_runtime_index

    step_count = 0
    total_steps = 8 if not skip_download else 6

    if not skip_download:
        print(f"[{step_count + 1}/{total_steps}] L0: Downloading web content...")
        asyncio.run(download_main())
        print()
        step_count += 1

    if not skip_download:
        print(f"[{step_count + 1}/{total_steps}] L0b: Downloading PDFs...")
        asyncio.run(download_pdfs_main())
        print()
        step_count += 1

    if not skip_download:
        print(f"[{step_count + 1}/{total_steps}] L1: Converting HTML to Markdown...")
        html_to_md_main(force=force_html_convert)
        print()
        step_count += 1

    print(f"[{step_count + 1}/{total_steps}] L2: Loading PDF documents...")
    pdf_docs = get_documents()
    print(f"  Loaded {len(pdf_docs)} PDF documents")
    print()
    step_count += 1

    print(f"[{step_count + 1}/{total_steps}] L3: Chunking documents...")
    chunks = chunk_documents(pdf_docs)
    print(f"  Created {len(chunks)} chunks")
    print()
    step_count += 1

    markdown_docs = get_markdown_documents()
    markdown_chunks = chunk_documents(markdown_docs)
    print(f"  Loaded {len(markdown_docs)} Markdown docs and created {len(markdown_chunks)} chunks")
    chunks.extend(markdown_chunks)
    print()

    print(f"[{step_count + 1}/{total_steps}] L4: Loading reference data...")
    ref_loader = ReferenceDataLoader()
    ref_docs = ref_loader.load_reference_ranges_as_docs()
    print(f"  Loaded {len(ref_docs)} reference documents")
    print()
    step_count += 1

    print(f"[{step_count + 1}/{total_steps}] L5: Embedding and storing vectors...")
    all_docs = chunks + ref_docs
    print(f"  Total documents to embed: {len(all_docs)}")
    vector_store = get_vector_store()
    if force_rebuild:
        print("  Force rebuild enabled - clearing vector store...")
        vector_store.clear()
    add_stats = vector_store.add_documents(all_docs)
    print(
        "  Vector store add stats: "
        f"attempted={add_stats['attempted']} inserted={add_stats['inserted']} "
        f"skipped_duplicate_id={add_stats['skipped_duplicate_id']} "
        f"skipped_duplicate_content={add_stats['skipped_duplicate_content']}"
    )
    print()
    step_count += 1

    print(f"[{step_count + 1}/{total_steps}] L6: Initializing RAG pipeline...")
    initialize_runtime_index(rebuild=False)
    print()
    step_count += 1

    total_time = time.time() - total_start

    print("=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print(f"  PDF documents processed: {len(pdf_docs)}")
    print(f"  Chunks created (PDF + Markdown): {len(chunks)}")
    print(f"  Reference docs loaded: {len(ref_docs)}")
    print(f"  Total vectors indexed: {len(all_docs)}")
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
    args = parser.parse_args()

    run_pipeline(
        skip_download=args.skip_download,
        force_rebuild=args.force,
        force_html_convert=args.force_html,
    )


if __name__ == "__main__":
    main()
