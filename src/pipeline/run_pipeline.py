#!/usr/bin/env python3
"""
Run Pipeline DAG - Execute the full data pipeline in sequence.

L0: Download web content (if HTML files missing)
L1: Convert HTML to Markdown (if MD files missing)
L2: Load PDF documents
L3: Chunk documents
L4: Load reference data (CSV)
L5: Embed and store in vector store
L6: Initialize RAG (rebuild index if needed)

Usage:
    python -m src.pipeline.run_pipeline           # Run full pipeline
    python -m src.pipeline.run_pipeline --force   # Force rebuild of vector store
    python -m src.pipeline.run_pipeline --skip-download  # Skip L0 download
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def run_pipeline(
    skip_download: bool = False,
    force_rebuild: bool = False,
    force_html_convert: bool = False
):
    """Run the full data pipeline in sequence."""
    print("=" * 70)
    print("RAG DATA PIPELINE")
    print("=" * 70)
    print()

    total_start = time.time()

    print("=" * 70)
    print("STEP SUMMARY")
    print("=" * 70)
    print(f"L0: Download web content     {'[SKIPPED]' if skip_download else '[RUNNING]'}")
    print(f"L1: HTML → Markdown          {'[RUNNING]' if not skip_download else '[SKIPPED]'}")
    print(f"L2: Load PDF documents       [RUNNING]")
    print(f"L3: Chunk documents          [RUNNING]")
    print(f"L4: Load reference data     [RUNNING]")
    print(f"L5: Embed & store vectors   {'[FORCE REBUILD]' if force_rebuild else '[RUNNING]'}")
    print(f"L6: Initialize RAG          [RUNNING]")
    print("=" * 70)
    print()

    from src.pipeline.L0_download import main as download_main
    from src.pipeline.L1_html_to_md import main as html_to_md_main
    from src.pipeline.L2_pdf_loader import get_documents
    from src.pipeline.L3_chunker import chunk_documents
    from src.pipeline.L4_reference_loader import ReferenceDataLoader
    from src.pipeline.L5_vector_store import get_vector_store
    from src.pipeline.L6_rag_pipeline import initialize_vector_store

    step_count = 0
    total_steps = 7 if not skip_download else 6

    if not skip_download:
        print(f"[{step_count + 1}/{total_steps}] L0: Downloading web content...")
        asyncio.run(download_main())
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
    vector_store.add_documents(all_docs)
    print(f"  Stored {len(all_docs)} documents in vector store")
    print()
    step_count += 1

    print(f"[{step_count + 1}/{total_steps}] L6: Initializing RAG pipeline...")
    initialize_vector_store(rebuild=force_rebuild)
    print()
    step_count += 1

    total_time = time.time() - total_start

    print("=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print(f"  PDF documents processed: {len(pdf_docs)}")
    print(f"  Chunks created: {len(chunks)}")
    print(f"  Reference docs loaded: {len(ref_docs)}")
    print(f"  Total vectors indexed: {len(all_docs)}")
    print(f"  Total time: {total_time:.2f}s")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Run the RAG data pipeline")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip L0 web content download"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild of vector store (clear and re-embed all)"
    )
    parser.add_argument(
        "--force-html",
        action="store_true",
        help="Force re-convert HTML to Markdown (overwrite existing)"
    )
    args = parser.parse_args()

    run_pipeline(
        skip_download=args.skip_download,
        force_rebuild=args.force,
        force_html_convert=args.force_html
    )


if __name__ == "__main__":
    main()
