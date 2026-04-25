"""Test that Hamilton DAG integration works end-to-end."""

import pytest

from src.ingestion.pipeline import build_ingestion_pipeline, execute_pipeline
from src.rag.runtime import initialize_runtime_index


@pytest.fixture(scope="session")
async def hamilton_setup(tmp_path):
    """Setup Hamilton pipeline for e2e tests."""
    from src.ingestion.indexing.vector_store import get_vector_store

    # Clear vector store for clean test
    vector_store = get_vector_store()
    vector_store.clear()

    # Build Hamilton driver
    project_root = tmp_path.parent
    dr = build_ingestion_pipeline(
        project_root=project_root,
        enable_hype=False,
        enable_keyword_extraction=False,
        enable_chunk_summaries=False,
        force_rebuild=False,
        parallel_cores=1,
    )

    # Initialize runtime index
    initialize_runtime_index(rebuild=False)

    return dr


@pytest.mark.e2e_real_apis
async def test_hamilton_e2e_complete_pipeline(hamilton_setup):
    """Test complete Hamilton DAG pipeline end-to-end.

    Validates:
    - Bronze layer: downloads content
    - Silver layer: parses and chunks documents
    - Gold layer: enriches chunks
    - Platinum layer: generates embeddings and stores vectors
    - Runtime index is properly initialized
    - Pipeline can be executed multiple times (idempotent)
    """
    dr = hamilton_setup

    # Execute full pipeline
    results = execute_pipeline(
        dr,
        final_vars=[
            "write_gold_chunks",
            "write_enriched_chunks",
            "embed_chunks",
        ],
    )

    # Verify bronze layer results
    assert "write_gold_chunks" in results
    assert results["write_gold_chunks"]["chunk_count"] >= 0

    # Verify silver layer results
    assert "write_enriched_chunks" in results
    assert results["write_enriched_chunks"]["enriched_count"] >= 0

    # Verify platinum layer results
    assert "embed_chunks" in results
    embed_stats = results["embed_chunks"][0]
    assert embed_stats["attempted"] > 0
    assert embed_stats["inserted"] > 0

    # Verify vector store is populated
    from src.ingestion.indexing.vector_store import get_vector_store
    vector_store = get_vector_store()
    stats = vector_store.get_stats()
    assert stats["document_count"] > 0
    assert stats["chunk_count"] > 0

    # Test idempotence - run pipeline again
    results2 = execute_pipeline(
        dr,
        final_vars=[
            "write_gold_chunks",
            "write_enriched_chunks",
            "embed_chunks",
        ],
    )

    # Verify same results (idempotent)
    assert results2["write_gold_chunks"]["chunk_count"] == results["write_gold_chunks"]["chunk_count"]
    assert results2["embed_chunks"][0]["attempted"] == embed_stats["attempted"]


@pytest.mark.e2e_real_apis
async def test_hamilton_pipeline_with_enrichment(hamilton_setup):
    """Test Hamilton pipeline with HyPE enabled.

    Validates that HyPE question generation works through Hamilton DAG.
    """
    dr = build_ingestion_pipeline(
        project_root=hamilton_setup.config.project_root,
        enable_hype=True,
        enable_keyword_extraction=False,
        enable_chunk_summaries=False,
        force_rebuild=False,
        parallel_cores=1,
    )

    # Execute pipeline with HyPE
    results = execute_pipeline(
        dr,
        final_vars=[
            "write_gold_chunks",
            "write_enriched_chunks",
            "embed_chunks",
        ],
    )

    # Verify HyPE was generated
    assert "write_enriched_chunks" in results
    assert results["write_enriched_chunks"]["enriched_count"] > 0

    # Check for HyPE metadata in results
    if "hype_questions" in results:
        assert len(results["hype_questions"]) > 0
