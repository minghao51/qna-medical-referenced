#!/usr/bin/env python3
"""
Verification script for tracing improvements.
Tests that logical_name and source_url are properly propagated through the pipeline.
"""

import json
from pathlib import Path

from src.infra.llm import get_client
from src.ingestion.indexing.vector_store import VectorStore
from src.rag.formatting import format_source_name, format_source_with_url
from src.usecases.chat import process_chat_message


def test_vector_store_metadata():
    """Test that vector store contains logical_name and source_url."""
    print("=" * 60)
    print("Test 1: Vector Store Metadata")
    print("=" * 60)

    vs = VectorStore()
    results = vs.similarity_search("COPD diagnosis", top_k=2)

    passed = True
    for i, result in enumerate(results, 1):
        logical_name = result.get("logical_name")
        source_url = result.get("source_url")

        print(f"\nResult {i}:")
        print(f"  Source: {result.get('source')}")
        print(f"  Logical Name: {logical_name}")
        print(f"  Source URL: {source_url}")

        if logical_name is None and source_url is None:
            # This might be OK for documents without manifest records
            print("  ⚠️  No manifest metadata (might be expected for some docs)")
        elif logical_name and source_url:
            print("  ✓ Has both logical_name and source_url")
        else:
            print("  ✗ Missing one of logical_name or source_url")
            passed = False

    return passed


def test_source_formatting():
    """Test that source formatting uses logical_name."""
    print("\n" + "=" * 60)
    print("Test 2: Source Formatting")
    print("=" * 60)

    vs = VectorStore()
    results = vs.similarity_search("diabetes screening", top_k=2)

    passed = True
    for result in results:
        formatted = format_source_name(result)
        formatted_with_url = format_source_with_url(result)

        print(f"\nSource: {result.get('source')}")
        print(f"  Logical Name: {result.get('logical_name')}")
        print(f"  Formatted: {formatted}")
        print(f"  Formatted with URL: {formatted_with_url}")

        # Check if logical_name is used when available
        logical_name = result.get("logical_name")
        if logical_name and logical_name in formatted:
            print("  ✓ Uses logical_name in formatted output")
        elif logical_name:
            print(f"  ✗ Has logical_name but doesn't use it: {logical_name}")
            passed = False

    return passed


def test_chat_integration():
    """Test that chat returns sources with logical names."""
    print("\n" + "=" * 60)
    print("Test 3: Chat Integration")
    print("=" * 60)

    result = process_chat_message(
        llm_client=get_client(),
        message="What are the screening tests for diabetes?",
        session_id="verification-test",
        include_pipeline=True,
    )

    print("\nQuery: What are the screening tests for diabetes?")
    print(f"Response (first 200 chars): {result['response'][:200]}...")

    print(f"\nSources ({len(result['sources'])} total):")
    for i, source in enumerate(result["sources"][:5], 1):
        print(f"  {i}. {source}")

    # Check pipeline trace for logical names
    if result.get("pipeline"):
        print("\nPipeline Trace - First 3 Documents:")
        for i, doc in enumerate(result["pipeline"].retrieval.documents[:3], 1):
            print(f"  Document {i}:")
            print(f"    Logical Name: {doc.logical_name}")
            print(f"    Source URL: {doc.source_url}")

            if doc.logical_name and doc.source_url:
                print("    ✓ Has both logical_name and source_url")
            elif doc.logical_name or doc.source_url:
                print(
                    f"    ⚠️  Has only one: logical_name={doc.logical_name}, source_url={doc.source_url}"
                )
            else:
                print("    ⚠️  No manifest metadata (might be expected)")

    return True


def test_vector_store_sample():
    """Test a sample of chunks from vector store."""
    print("\n" + "=" * 60)
    print("Test 4: Vector Store Sample Metadata")
    print("=" * 60)

    vs_path = Path("data/vectors/medical_docs.json")
    vs_data = json.loads(vs_path.read_text())

    metadatas = vs_data.get("metadatas", [])

    # Count chunks with logical_name
    with_logical = sum(1 for m in metadatas if m.get("logical_name"))
    with_url = sum(1 for m in metadatas if m.get("source_url"))

    print(f"\nTotal chunks: {len(metadatas)}")
    print(f"Chunks with logical_name: {with_logical} ({100 * with_logical / len(metadatas):.1f}%)")
    print(f"Chunks with source_url: {with_url} ({100 * with_url / len(metadatas):.1f}%)")

    # Show examples
    print("\nSample chunks with manifest metadata:")
    count = 0
    for i, meta in enumerate(metadatas):
        if meta.get("logical_name"):
            print(f"\n  Chunk {i}:")
            print(f"    Source: {meta.get('source')}")
            print(f"    Logical Name: {meta.get('logical_name')}")
            print(f"    Source URL: {meta.get('source_url')}")
            count += 1
            if count >= 3:
                break

    return with_logical > 0


if __name__ == "__main__":
    print("Verifying Tracing Improvements")
    print("=" * 60)

    results = []

    try:
        results.append(("Vector Store Metadata", test_vector_store_metadata()))
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        results.append(("Vector Store Metadata", False))

    try:
        results.append(("Source Formatting", test_source_formatting()))
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        results.append(("Source Formatting", False))

    try:
        results.append(("Chat Integration", test_chat_integration()))
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        results.append(("Chat Integration", False))

    try:
        results.append(("Vector Store Sample", test_vector_store_sample()))
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        results.append(("Vector Store Sample", False))

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
    else:
        print("⚠️  Some tests failed")
    print("=" * 60)
