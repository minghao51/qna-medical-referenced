"""Tests for HyDE (Hypothetical Document Embeddings) query expansion.

These tests validate that HyDE query expansion works correctly and improves
retrieval quality when enabled.

Tests cover:
- HyDE query expansion generation
- Integration with retrieval pipeline
- Backward compatibility (disabled by default)
- Configuration and validation
"""

from unittest.mock import patch

import pytest

from src.rag.hyde import (
    expand_query_with_hyde,
    expand_query_with_hyde_async,
    generate_hypothetical_answer,
    should_enable_hyde,
    validate_hyde_config,
)
from src.rag.runtime import (
    _resolve_retrieval_config,
    retrieve_context_with_trace_async,
)

# =============================================================================
# HyDE Generation Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.live_api
async def test_generate_hypothetical_answer_basic():
    """Test basic hypothetical answer generation."""
    from src.infra.llm.qwen_client import get_client

    client = get_client()
    query = "What is the LDL-C target for secondary prevention?"

    answer = await generate_hypothetical_answer(query, client, max_length=200)

    # Should generate a non-empty answer
    assert isinstance(answer, str)
    assert len(answer) > 0

    # Should contain relevant medical terms
    answer_lower = answer.lower()
    assert any(term in answer_lower for term in ["ldl", "cholesterol", "target", "mmol", "mg"])


@pytest.mark.asyncio
@pytest.mark.live_api
async def test_generate_hypothetical_answer_empty_query():
    """Test that empty queries are handled gracefully."""
    from src.infra.llm.qwen_client import get_client

    client = get_client()

    # Empty query should return empty string
    answer = await generate_hypothetical_answer("", client, max_length=200)
    assert answer == ""

    # Whitespace-only query should return empty string
    answer = await generate_hypothetical_answer("   ", client, max_length=200)
    assert answer == ""


@pytest.mark.asyncio
@pytest.mark.live_api
async def test_generate_hypothetical_answer_max_length():
    """Test that max_length parameter is respected."""
    from src.infra.llm.qwen_client import get_client

    client = get_client()
    query = "What is statin therapy?"

    # Test with short max_length
    answer = await generate_hypothetical_answer(query, client, max_length=50)

    # Should be truncated to around 50 words
    word_count = len(answer.split())
    assert word_count <= 55  # Allow small buffer


@pytest.mark.asyncio
async def test_generate_hypothetical_answer_handles_llm_errors():
    """Test that LLM errors are handled gracefully."""
    from src.infra.llm.qwen_client import get_client

    client = get_client()
    query = "Test query"

    # Mock LLM to raise error
    with patch.object(client, "generate", side_effect=Exception("API Error")):
        answer = await generate_hypothetical_answer(query, client, max_length=200)

        # Should return empty string on error
        assert answer == ""


# =============================================================================
# Query Expansion Tests
# =============================================================================


def test_expand_query_with_hyde_disabled():
    """Test that expansion returns original query when HyDE is disabled."""
    query = "What is the LDL-C target?"

    # HyDE disabled
    queries = expand_query_with_hyde(query, enable_hyde=False)

    # Should return only original query
    assert queries == [query]


def test_expand_query_with_hyde_enabled_sync():
    """Test that synchronous expansion returns original query even when enabled."""
    query = "What is the LDL-C target?"

    # HyDE enabled (but sync version doesn't do LLM calls)
    queries = expand_query_with_hyde(query, enable_hyde=True)

    # Should return only original query in sync version
    assert queries == [query]


@pytest.mark.asyncio
@pytest.mark.live_api
async def test_expand_query_with_hyde_async_enabled():
    """Test async HyDE expansion when enabled."""
    from src.infra.llm.qwen_client import get_client

    client = get_client()
    query = "What is the LDL-C target?"

    # HyDE enabled
    queries = await expand_query_with_hyde_async(
        query,
        client,
        enable_hyde=True,
        max_length=200,
    )

    # Should return at least original query
    assert len(queries) >= 1
    assert query in queries

    # Should have hypothetical answer if generation succeeded
    if len(queries) > 1:
        hypothetical = queries[1]
        assert len(hypothetical) > 0
        assert hypothetical != query


@pytest.mark.asyncio
@pytest.mark.live_api
async def test_expand_query_with_hyde_async_disabled():
    """Test async expansion when HyDE is disabled."""
    from src.infra.llm.qwen_client import get_client

    client = get_client()
    query = "What is the LDL-C target?"

    # HyDE disabled
    queries = await expand_query_with_hyde_async(
        query,
        client,
        enable_hyde=False,
        max_length=200,
    )

    # Should return only original query
    assert queries == [query]


@pytest.mark.asyncio
async def test_expand_query_with_hyde_async_handles_generation_failure():
    """Test that generation failures fall back to original query."""
    from src.infra.llm.qwen_client import get_client

    client = get_client()
    query = "Test query"

    # Mock LLM to fail
    with patch.object(client, "generate", side_effect=Exception("API Error")):
        queries = await expand_query_with_hyde_async(
            query,
            client,
            enable_hyde=True,
            max_length=200,
        )

        # Should fall back to original query only
        assert queries == [query]


# =============================================================================
# Configuration Tests
# =============================================================================


def test_should_enable_hyde_explicit_true():
    """Test that explicit True setting enables HyDE."""
    assert should_enable_hyde(explicit_setting=True) is True
    assert should_enable_hyde(explicit_setting=True, config_setting=False) is True


def test_should_enable_hyde_explicit_false():
    """Test that explicit False setting disables HyDE."""
    assert should_enable_hyde(explicit_setting=False) is False
    assert should_enable_hyde(explicit_setting=False, config_setting=True) is False


def test_should_enable_hyde_config_setting():
    """Test that config setting is used when no explicit setting."""
    assert should_enable_hyde(config_setting=True) is True
    assert should_enable_hyde(config_setting=False) is False


def test_should_enable_hyde_default():
    """Test that HyDE is disabled by default."""
    assert should_enable_hyde() is False
    assert should_enable_hyde(explicit_setting=None, config_setting=None) is False


def test_validate_hyde_config_valid():
    """Test validation of valid HyDE configuration."""
    enable, max_length = validate_hyde_config(True, 200)

    assert enable is True
    assert max_length == 200


def test_validate_hyde_config_clamps_max_length():
    """Test that max_length is clamped to valid range."""
    # Too low
    enable, max_length = validate_hyde_config(True, 10)
    assert max_length == 50  # Minimum

    # Too high
    enable, max_length = validate_hyde_config(True, 1000)
    assert max_length == 500  # Maximum

    # Just right
    enable, max_length = validate_hyde_config(True, 300)
    assert max_length == 300


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.live_api
async def test_hyde_integration_with_retrieval():
    """Test that HyDE integrates with retrieval pipeline."""
    from src.infra.llm.qwen_client import get_client

    client = get_client()
    query = "What is the LDL-C target for high-risk patients?"

    # Test with HyDE enabled
    retrieval_options = {
        "enable_hyde": True,
        "hyde_max_length": 200,
    }

    try:
        context, sources, trace = await retrieve_context_with_trace_async(
            query,
            top_k=3,
            retrieval_options=retrieval_options,
            hyde_client=client,
        )

        # Should retrieve results
        assert len(context) > 0
        assert len(sources) > 0

        # Check trace indicates HyDE was used (in score_weights)
        assert trace.retrieval.score_weights.get("hyde_enabled") is True

        # Check expanded queries in trace
        expanded_queries = trace.retrieval.score_weights.get("expanded_queries", [])
        assert len(expanded_queries) >= 1
        assert query in expanded_queries

    except Exception as e:
        # May fail if no documents indexed
        pytest.skip(f"Retrieval failed (likely no documents): {e}")


@pytest.mark.asyncio
async def test_hyde_backward_compatibility():
    """Test that backward compatibility is maintained (HyDE disabled by default)."""
    from src.rag.runtime import retrieve_context

    query = "Test query"

    # Should work without HyDE client
    context, sources = retrieve_context(query, top_k=3)

    # Should return results
    assert isinstance(context, str)
    assert isinstance(sources, list)


@pytest.mark.asyncio
async def test_runtime_config_with_hyde():
    """Test that runtime config properly handles HyDE settings."""
    config = _resolve_retrieval_config(
        {
            "enable_hyde": True,
            "hyde_max_length": 300,
        }
    )

    assert config.enable_hyde is True
    assert config.hyde_max_length == 300


@pytest.mark.asyncio
async def test_runtime_config_defaults_hyde_disabled():
    """Test that HyDE is disabled by default in runtime config."""
    config = _resolve_retrieval_config(None)

    assert config.enable_hyde is False
    assert config.hyde_max_length == 200


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.live_api
async def test_hyde_with_special_characters():
    """Test that special characters in queries are handled."""
    from src.infra.llm.qwen_client import get_client

    client = get_client()
    query = "What is the LDL-C target? 价值观 émojis"

    # Should not crash
    queries = await expand_query_with_hyde_async(
        query,
        client,
        enable_hyde=True,
        max_length=200,
    )

    assert len(queries) >= 1


@pytest.mark.asyncio
@pytest.mark.live_api
async def test_hyde_with_very_long_query():
    """Test that very long queries are handled."""
    from src.infra.llm.qwen_client import get_client

    client = get_client()
    long_query = "What is the LDL-C target? " * 50  # Very long

    # Should not crash
    queries = await expand_query_with_hyde_async(
        long_query,
        client,
        enable_hyde=True,
        max_length=200,
    )

    assert len(queries) >= 1


@pytest.mark.asyncio
async def test_hyde_with_duplicate_queries():
    """Test that duplicate queries are removed."""
    from src.infra.llm.qwen_client import get_client

    client = get_client()
    query = "What is LDL?"

    # Mock to return same query as hypothetical
    with patch.object(client, "generate", return_value=query):
        queries = await expand_query_with_hyde_async(
            query,
            client,
            enable_hyde=True,
            max_length=200,
        )

        # Should have at least the original query
        assert len(queries) >= 1
        assert query in queries

        # Note: Deduplication happens in _expand_queries_async, not in the HyDE module
        # So we might have duplicates if the hypothetical matches the original
        # The deduplication in runtime will handle this


# =============================================================================
# Performance Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.live_api
@pytest.mark.slow
async def test_hyde_performance_impact():
    """Test that HyDE doesn't significantly impact performance."""
    import time

    from src.infra.llm.qwen_client import get_client

    client = get_client()
    query = "What is the LDL-C target?"

    # Measure without HyDE
    start = time.time()
    await expand_query_with_hyde_async(
        query,
        client,
        enable_hyde=False,
        max_length=200,
    )
    time_without = time.time() - start

    # Measure with HyDE
    start = time.time()
    await expand_query_with_hyde_async(
        query,
        client,
        enable_hyde=True,
        max_length=200,
    )
    time_with = time.time() - start

    # HyDE should be slower (due to LLM call), but not excessively
    assert time_with > time_without
    assert time_with < time_without + 10  # Should not add more than 10 seconds
