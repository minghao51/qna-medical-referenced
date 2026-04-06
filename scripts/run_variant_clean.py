#!/usr/bin/env python3
"""Run a single ablation variant with guaranteed clean state.

This script ensures complete isolation between variants by:
1. Resetting all global state (ChromaDB factory, HTML config, chunking config)
2. Deleting the ChromaDB collection on disk
3. Deleting cached .md files and artifacts
4. Forcing HTML re-conversion with the correct strategy
5. Running the assessment with rebuild_policy=always

Usage:
    uv run python scripts/run_variant_clean.py --variant html_html2md
    uv run python scripts/run_variant_clean.py --variant chunk_chonkie_semantic_512
    uv run python scripts/run_variant_clean.py --config experiments/v1/comprehensive_ablation.yaml --variant baseline
"""

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATA_RAW_DIR, DATA_PROCESSED_DIR, CHROMA_PERSIST_DIRECTORY, settings
from src.experiments.config import resolve_experiment_runs, build_run_assessment_kwargs
from src.evals import run_assessment

logger = logging.getLogger(__name__)


def clean_chroma_collection(collection_name: str) -> None:
    """Delete a specific ChromaDB collection from disk."""
    import chromadb

    client = chromadb.PersistentClient(
        path=str(CHROMA_PERSIST_DIRECTORY),
        settings=chromadb.config.Settings(allow_reset=True),
    )
    try:
        client.delete_collection(collection_name)
        print(f"  Deleted ChromaDB collection: {collection_name}")
    except Exception:
        pass  # Collection doesn't exist


def clean_html_artifacts() -> None:
    """Delete cached .md files and HTML processing artifacts."""
    # Delete .md files in data/raw
    md_count = 0
    for md_file in DATA_RAW_DIR.glob("*.md"):
        md_file.unlink()
        md_count += 1
    print(f"  Deleted {md_count} .md files from {DATA_RAW_DIR}")

    # Delete HTML artifacts in data/processed/html
    html_artifact_dir = DATA_PROCESSED_DIR / "html"
    if html_artifact_dir.exists():
        shutil.rmtree(html_artifact_dir)
        print(f"  Deleted HTML artifacts from {html_artifact_dir}")


def reset_global_state() -> None:
    """Reset all global state modules to defaults."""
    # Reset ChromaDB factory singleton
    from src.ingestion.indexing.chroma_store import ChromaVectorStoreFactory
    ChromaVectorStoreFactory.reset()

    # Reset HTML processor config
    from src.ingestion.steps.convert_html import _html_config, HTMLProcessorConfig
    _html_config.__dict__ = HTMLProcessorConfig().__dict__

    # Reset chunking config
    from src.ingestion.steps.chunking.config import (
        SOURCE_CHUNK_CONFIGS_OVERRIDE,
        STRUCTURED_CHUNKING_ENABLED,
        AUTO_SELECT_STRATEGY,
    )
    import src.ingestion.steps.chunking.config as chunking_config
    chunking_config.SOURCE_CHUNK_CONFIGS_OVERRIDE = None
    chunking_config.STRUCTURED_CHUNKING_ENABLED = True
    chunking_config.AUTO_SELECT_STRATEGY = False

    # Reset runtime globals
    import src.rag.runtime as runtime
    runtime._vector_store_initialized = False
    runtime._vector_store_initialized_signature = None

    # Reset load_markdown globals
    import src.ingestion.steps.load_markdown as load_md
    load_md.INDEX_ONLY_CLASSIFIED_PAGES = True

    # Reset load_pdfs globals
    import src.ingestion.steps.load_pdfs as load_pdfs
    load_pdfs.PDF_EXTRACTOR_STRATEGY = "pypdf_pdfplumber"
    load_pdfs.PDF_TABLE_EXTRACTOR = "heuristic"

    print("  Reset all global state")


def run_variant_clean(
    config_path: str,
    variant_name: str,
    artifact_dir: str = "data/evals_comprehensive_ablation",
    include_answer_eval: bool = True,
) -> None:
    """Run a single variant with guaranteed clean state."""
    print(f"\n{'='*60}")
    print(f"Running variant: {variant_name}")
    print(f"{'='*60}")

    # Load experiment config
    runs = resolve_experiment_runs(config_path, variant=variant_name)
    if not runs:
        print(f"ERROR: Variant '{variant_name}' not found in {config_path}")
        sys.exit(1)

    spec = runs[-1]  # Get the variant spec
    experiment_config = spec

    # Get collection name from config
    embedding_index = experiment_config.get("embedding_index", {})
    collection_name = embedding_index.get("collection_name", settings.collection_name)

    print(f"\n1. Cleaning state...")
    print(f"   Collection: {collection_name}")

    # Step 1: Reset global state FIRST (before any imports touch it)
    reset_global_state()

    # Step 2: Clean ChromaDB collection
    clean_chroma_collection(collection_name)

    # Step 3: Clean HTML artifacts and .md files
    clean_html_artifacts()

    print(f"\n2. Configuring runtime...")

    # Step 4: Configure runtime for experiment
    from src.rag.runtime import configure_runtime_for_experiment
    configure_runtime_for_experiment(experiment_config)

    # Verify strategy was set
    from src.ingestion.steps.convert_html import _html_config
    print(f"   HTML strategy: {_html_config.extractor_strategy}")
    print(f"   PDF strategy: {experiment_config.get('ingestion', {}).get('pdf_extractor_strategy')}")

    print(f"\n3. Running assessment...")

    # Step 5: Build kwargs and run
    kwargs = build_run_assessment_kwargs(experiment_config)
    kwargs["artifact_dir"] = artifact_dir
    kwargs["include_answer_eval"] = include_answer_eval
    kwargs["force_rerun"] = True

    result = run_assessment(**kwargs)

    print(f"\n4. Results:")
    print(f"   Status: {result.status}")
    print(f"   Run dir: {result.run_dir}")

    # Print retrieval metrics
    retrieval = result.summary.get("retrieval_metrics", {})
    if retrieval:
        ndcg = retrieval.get("ndcg_at_k")
        mrr = retrieval.get("mrr")
        hit_rate = retrieval.get("hit_rate_at_k")
        print(f"   NDCG@K: {ndcg:.4f}" if isinstance(ndcg, (int, float)) else "   NDCG@K: N/A")
        print(f"   MRR: {mrr:.4f}" if isinstance(mrr, (int, float)) else "   MRR: N/A")
        print(f"   HR@K: {hit_rate:.4f}" if isinstance(hit_rate, (int, float)) else "   HR@K: N/A")

    # Print indexing stats
    idx_prep = result.summary.get("index_preparation", {})
    idx_stats = idx_prep.get("indexing_stats", {})
    if idx_stats:
        print(f"   Chunks: attempted={idx_stats.get('attempted')}, inserted={idx_stats.get('inserted')}, dup={idx_stats.get('skipped_duplicate_content')}")

    print(f"\n{'='*60}")
    print(f"Variant complete: {variant_name}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Run a single ablation variant with clean state")
    parser.add_argument("--config", default="experiments/v1/comprehensive_ablation.yaml")
    parser.add_argument("--variant", required=True, help="Variant name to run")
    parser.add_argument("--artifact-dir", default="data/evals_comprehensive_ablation")
    parser.add_argument("--include-answer-eval", action="store_true", default=True)
    parser.add_argument("--no-answer-eval", action="store_true", help="Disable answer evaluation")
    args = parser.parse_args()

    if args.no_answer_eval:
        args.include_answer_eval = False

    run_variant_clean(
        config_path=args.config,
        variant_name=args.variant,
        artifact_dir=args.artifact_dir,
        include_answer_eval=args.include_answer_eval,
    )


if __name__ == "__main__":
    main()
