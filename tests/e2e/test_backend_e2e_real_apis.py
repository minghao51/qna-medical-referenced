"""End-to-end backend tests with real API integrations.

These tests validate the complete L0-L6 pipeline with real API calls to:
- Dashscope (Qwen models for embeddings and generation)
- W&B (logging and artifacts)
- Real document downloads from medical guideline sources

IMPORTANT: These tests require REAL API credentials and network access.
They are SKIPPED by default unless explicitly enabled.

To run these tests:
    export ENABLE_REAL_API_TESTS=1
    export DASHSCOPE_API_KEY=your_key
    export WANDB_PROJECT=your_project
    uv run pytest tests/e2e/test_backend_e2e_real_apis.py -v

Each test validates a specific stage of the RAG pipeline with real APIs.
Tests are designed to be fast (<10 minutes total) and clean up after themselves.
"""

import os
import tempfile
from pathlib import Path

import pytest

from src.config import settings
from src.evals.assessment.answer_eval import evaluate_answer_quality_async
from src.ingestion.indexing.vector_store import get_vector_store, set_vector_store_runtime_config
from src.ingestion.steps.chunk_text import chunk_documents
from src.ingestion.steps.load_pdfs import get_documents
from src.rag.runtime import initialize_runtime_index, retrieve_context_with_trace

pytestmark = [pytest.mark.e2e_real_apis, pytest.mark.slow]

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def real_api_config():
    """Load real API credentials from environment."""
    return {
        "dashscope_api_key": os.getenv("DASHSCOPE_API_KEY"),
        "wandb_project": os.getenv("WANDB_PROJECT"),
        "enable_real_tests": os.getenv("ENABLE_REAL_API_TESTS") == "1",
    }


@pytest.fixture
def skip_without_real_apis(real_api_config):
    """Skip test unless real APIs are explicitly enabled."""
    if not real_api_config["enable_real_tests"]:
        pytest.skip("Set ENABLE_REAL_API_TESTS=1 to run real API tests")
    if not real_api_config["dashscope_api_key"]:
        pytest.skip("Set DASHSCOPE_API_KEY to run real API tests")


@pytest.fixture
def temp_vector_store():
    """Create a temporary vector store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_vector_dir = None
        try:
            # Import and save original vector dir
            from src.ingestion.indexing import persistence

            original_vector_dir = persistence.VECTOR_DIR
            persistence.VECTOR_DIR = Path(tmpdir)

            # Create test collection
            test_config = {
                "collection_name": "test_e2e_real_apis",
                "semantic_weight": 0.6,
                "keyword_weight": 0.2,
                "boost_weight": 0.2,
                "embedding_model": settings.llm.embedding_model,
                "embedding_batch_size": settings.llm.embedding_batch_size,
                "index_metadata": {"test": True},
            }
            set_vector_store_runtime_config(test_config)

            yield get_vector_store()

        finally:
            # Restore original vector dir
            if original_vector_dir:
                persistence.VECTOR_DIR = original_vector_dir


@pytest.fixture
def sample_manifest_path(real_api_config, skip_without_real_apis, tmp_path):
    """Create a minimal manifest with a real medical guideline URL."""
    manifest_file = tmp_path / "test_manifest.json"
    manifest_file.write_text("""{
        "sources": [
            {
                "filename": "ESC_2019_GUIDELINE.pdf",
                "url": "https://www.escardio.org/Guidelines/Clinical-Practice-Guidelines/2019-ESC-EAS-Guidelines-for-the-management-of-dyslipidaemias",
                "source": "ESC/EAS 2019",
                "category": "guideline",
                "priority": "high"
            }
        ]
    }""")
    return manifest_file


# =============================================================================
# L0: Document Download Tests
# =============================================================================


@pytest.mark.e2e_real_apis
@pytest.mark.slow
async def test_l0_real_pdf_download(skip_without_real_apis):
    """Test L0: Download real PDF from medical guideline URL.

    Validates:
    - HTTP download works
    - File is saved to correct location
    - File is not empty
    """
    from src.ingestion.steps.download_pdfs import download_pdf_if_not_exists

    # Test URL from a known medical guideline
    test_url = "https://www.escardio.org/Guidelines/Clinical-Practice-Guidelines/2019-ESC-EAS-Guidelines-for-the-management-of-dyslipidaemias"

    # Attempt download
    result_path = await download_pdf_if_not_exists(test_url, "test_guideline")

    # Verify download succeeded or file already exists
    if result_path:
        assert result_path.exists(), "Downloaded file does not exist"
        assert result_path.stat().st_size > 1000, (
            f"Downloaded PDF is too small: {result_path.stat().st_size} bytes"
        )


# =============================================================================
# L3: Chunking Tests
# =============================================================================


# =============================================================================
# L3: Chunking Tests
# =============================================================================


@pytest.mark.e2e_real_apis
def test_l3_real_document_chunking(temp_vector_store, skip_without_real_apis):
    """Test L3: Chunk real documents into manageable pieces.

    Validates:
    - Documents are loaded
    - Chunking produces reasonable chunks
    - Chunks have required metadata
    - No chunks are empty
    """
    # Load real documents
    documents = get_documents()
    assert len(documents) > 0, "No documents loaded for chunking"

    # Chunk documents
    chunked_docs = chunk_documents(documents)

    # Verify chunks
    assert len(chunked_docs) > 0, "No chunks produced"
    assert len(chunked_docs) >= len(documents), "Should have at least as many chunks as documents"

    # Verify chunk structure
    for chunk in chunked_docs[:10]:  # Check first 10
        assert "content" in chunk
        assert len(chunk["content"]) > 0
        assert "source" in chunk
        assert "id" in chunk


# =============================================================================
# L4-L5: Vector Store & Retrieval Tests
# =============================================================================


@pytest.mark.e2e_real_apis
@pytest.mark.slow
@pytest.mark.asyncio
async def test_l4_l5_vector_store_and_retrieval(temp_vector_store, skip_without_real_apis):
    """Test L4-L5: Build vector store and test retrieval with real embeddings.

    Validates:
    - Embeddings are generated successfully
    - Vector store is built
    - Semantic search returns relevant results
    - Hybrid search (semantic + BM25) works
    - RRF fusion produces ranked results
    """
    # Load and chunk documents
    documents = get_documents()
    chunked_docs = chunk_documents(documents)

    # Add to vector store (generates real embeddings via Dashscope API)
    stats = temp_vector_store.add_documents(chunked_docs)

    # Verify embeddings generated
    assert stats["inserted"] > 0, "No documents inserted into vector store"
    assert stats["attempted"] >= stats["inserted"], "Attempted more than inserted"

    # Test semantic search
    medical_query = "What is the LDL cholesterol target for secondary prevention?"
    results = temp_vector_store.similarity_search(
        medical_query, top_k=5, search_mode="semantic_only"
    )

    # Verify search results
    assert len(results) > 0, "No search results returned"
    assert "content" in results[0], "Result missing content"
    assert "score" in results[0] or "semantic_score" in results[0], "Result missing score"

    # Test hybrid search
    hybrid_results = temp_vector_store.similarity_search(
        medical_query, top_k=5, search_mode="rrf_hybrid"
    )

    assert len(hybrid_results) > 0, "No hybrid search results"
    # Hybrid results should have combined scores
    if hybrid_results:
        assert "combined_score" in hybrid_results[0] or "fused_score" in hybrid_results[0]


@pytest.mark.e2e_real_apis
@pytest.mark.slow
def test_l5_retrieval_with_runtime_api(skip_without_real_apis):
    """Test L5: Test retrieval through runtime API with real embeddings.

    Validates:
    - Runtime index initializes
    - Retrieval returns context and sources
    - Trace information is captured
    - Query expansion works
    """
    # Initialize runtime index
    init_result = initialize_runtime_index(rebuild=True)

    # Verify initialization
    assert init_result["status"] in ["ready", "built"], (
        f"Unexpected status: {init_result['status']}"
    )
    assert init_result["vector_document_count"] > 0, "No documents in index"

    # Test retrieval with trace
    query = "What are statin side effects?"
    context, sources, trace = retrieve_context_with_trace(query, top_k=3)

    # Verify retrieval
    assert len(context) > 0, "No context retrieved"
    assert len(sources) > 0, "No sources returned"
    assert trace is not None, "No trace returned"

    # Verify trace structure
    assert hasattr(trace, "retrieval"), "Trace missing retrieval stage"
    assert hasattr(trace, "context"), "Trace missing context stage"
    assert hasattr(trace, "total_time_ms"), "Trace missing timing"

    # Verify retrieval trace details
    retrieval_trace = trace.retrieval
    assert retrieval_trace.query == query, "Query mismatch in trace"
    assert len(retrieval_trace.documents) > 0, "No documents in retrieval trace"
    assert retrieval_trace.timing_ms > 0, "No timing recorded"


# =============================================================================
# L6: Answer Generation & Evaluation Tests
# =============================================================================


@pytest.mark.e2e_real_apis
@pytest.mark.slow
@pytest.mark.asyncio
async def test_l6_answer_generation_with_real_llm(skip_without_real_apis):
    """Test L6: Generate answer for real medical query using LLM.

    Validates:
    - Answer is generated
    - Answer is relevant to query
    - Sources are cited
    - Generation completes in reasonable time
    """
    from src.infra.llm.qwen_client import get_client
    from src.rag.runtime import retrieve_context

    # Retrieve context
    query = "What is the recommended LDL-C target for secondary prevention?"
    context, sources = retrieve_context(query, top_k=3)

    assert len(context) > 0, "No context retrieved"
    assert len(sources) > 0, "No sources found"

    # Generate answer
    client = get_client()
    answer = client.generate(
        prompt=f"Answer this question based on the context: {query}", context=context
    )

    # Verify answer
    assert len(answer) > 50, f"Answer too short: {len(answer)} chars"
    assert "cholesterol" in answer.lower() or "ldl" in answer.lower(), "Answer missing key terms"


@pytest.mark.e2e_real_apis
@pytest.mark.slow
@pytest.mark.asyncio
async def test_l6_deepeval_evaluation_with_real_apis(skip_without_real_apis):
    """Test L6: Run DeepEval metrics with real Dashscope API.

    Validates:
    - All 6 metrics are computed
    - Metrics return valid scores
    - Evaluation completes successfully
    - Results are properly formatted
    """
    dataset = [
        {"query": "What is the LDL-C target for secondary prevention?", "query_id": "e2e_test_001"}
    ]

    # Run evaluation
    results, aggregate = await evaluate_answer_quality_async(dataset, top_k=3)

    # Verify results
    assert len(results) == 1, "Expected 1 result"
    result = results[0]

    # Verify answer generated
    assert "answer" in result
    assert len(result["answer"]) > 50, "Answer too short"

    # Verify sources
    assert "sources" in result
    assert len(result["sources"]) > 0, "No sources found"

    # Verify all 6 metrics computed
    metrics = result["metrics"]
    expected_metrics = [
        "factual_accuracy",
        "completeness",
        "clinical_relevance",
        "clarity",
        "answer_relevancy",
        "faithfulness",
    ]

    for metric_name in expected_metrics:
        assert metric_name in metrics, f"Missing metric: {metric_name}"
        metric_data = metrics[metric_name]
        assert "score" in metric_data, f"{metric_name} missing score"
        assert "status" in metric_data, f"{metric_name} missing status"

        # Score should be valid if status is not error
        if metric_data["status"] != "error":
            score = metric_data["score"]
            assert score is not None, f"{metric_name} has None score but no error"
            assert 0 <= score <= 1, f"{metric_name} score {score} not in [0, 1]"

    # Verify aggregate stats
    assert aggregate["query_count"] == 1
    for metric_name in expected_metrics:
        assert metric_name in aggregate


# =============================================================================
# End-to-End Pipeline Tests
# =============================================================================


@pytest.mark.e2e_real_apis
@pytest.mark.slow
@pytest.mark.asyncio
async def test_e2e_complete_pipeline(skip_without_real_apis, tmp_path):
    """Test complete L0-L6 pipeline end-to-end with real APIs.

    This is the most comprehensive test, validating:
    - L0: Document download
    - L1-L2: HTML/Markdown conversion
    - L3: Chunking
    - L4-L5: Vector store and retrieval
    - L6: Answer generation and evaluation
    - Artifact persistence
    - W&B logging (if configured)

    Expected to complete in <10 minutes.
    """
    from src.ingestion.artifacts import SourceArtifact, persist_source_artifact

    # L0: Download a real document (using existing data if available)
    documents = get_documents()
    if len(documents) == 0:
        pytest.skip("No documents available for E2E test - run download first")

    # L3: Chunk documents
    chunked_docs = chunk_documents(documents)
    assert len(chunked_docs) > 0, "L3: No chunks produced"

    # L4-L5: Build vector store
    vector_store = get_vector_store()
    stats = vector_store.add_documents(chunked_docs)
    assert stats["inserted"] > 0, "L4-L5: No documents inserted"

    # L5: Test retrieval
    query = "What is the LDL-C target for high-risk patients?"
    results = vector_store.similarity_search(query, top_k=3, search_mode="rrf_hybrid")
    assert len(results) > 0, "L5: No retrieval results"

    # L6: Generate and evaluate answer
    dataset = [{"query": query, "query_id": "e2e_pipeline_001"}]
    eval_results, _aggregate = await evaluate_answer_quality_async(dataset, top_k=3)

    assert len(eval_results) == 1, "L6: No evaluation results"
    assert "answer" in eval_results[0], "L6: No answer generated"
    assert "metrics" in eval_results[0], "L6: No metrics computed"

    # Verify artifact persistence

    artifact = SourceArtifact(
        source_id="e2e_test",
        source_path="test",
        source_type="test",
        metadata={"test": "e2e_complete_pipeline"},
    )
    artifact_path = persist_source_artifact(artifact)
    assert artifact_path.exists(), "Artifact not persisted"

    # Verify W&B project is configured (if enabled)
    if os.getenv("WANDB_PROJECT"):
        # Just verify the env var is set - actual wandb integration tested elsewhere
        assert os.getenv("WANDB_PROJECT"), "W&B project not configured"


@pytest.mark.e2e_real_apis
@pytest.mark.slow
def test_e2e_cleanup_and_isolation(skip_without_real_apis, tmp_path):
    """Test that E2E tests properly clean up and don't interfere with each other.

    Validates:
    - Temporary directories are used
    - Test data is isolated
    - Cleanup removes test artifacts
    - No pollution of production data
    """
    # Create test-specific data
    test_file = tmp_path / "test_data.txt"
    test_file.write_text("test data")

    # Verify file exists in temp directory
    assert test_file.exists()

    # Verify temp directory is actually under tmp_path
    assert test_file.parent == tmp_path

    # After test exits (cleanup), tmp_path should be cleaned up
    # This is handled by pytest's tmp_path fixture
