"""HyDE (Hypothetical Document Embeddings) query expansion.

This module implements the HyDE technique for improving retrieval quality by:
1. Generating a hypothetical answer to the user's query
2. Using both the original query and hypothetical answer for retrieval
3. Aggregating results from both query variants

HyDE is particularly useful for:
- Queries that are ambiguous or lack specific medical terminology
- Improving recall for complex medical questions
- Bridging the semantic gap between user queries and medical documents

Reference:
    "Precise Zero-Shot Dense Retrieval without Relevance Labels"
    https://arxiv.org/abs/2212.10596

Example:
    >>> from src.rag.hyde import expand_query_with_hyde
    >>> queries = expand_query_with_hyde("What is LDL cholesterol?")
    >>> # Returns: ["What is LDL cholesterol?", "LDL cholesterol stands for..."]
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infra.llm.qwen_client import QwenClient

logger = logging.getLogger(__name__)


# Default configuration
HYPOTHETICAL_ANSWER_MAX_LENGTH = 200
HYPOTHETICAL_ANSWER_PROMPT_TEMPLATE = """Answer this medical question concisely (maximum {max_length} words):

Question: {query}

Provide a factual, medical answer that would appear in a clinical guideline.
Be specific and include relevant medical terminology."""


async def generate_hypothetical_answer(
    query: str,
    client: "QwenClient",
    max_length: int = HYPOTHETICAL_ANSWER_MAX_LENGTH,
) -> str:
    """Generate a hypothetical answer to use for query expansion.

    This function uses the LLM to generate a concise, factual answer that
    captures the medical intent behind the query. This hypothetical answer
    is then used alongside the original query for retrieval.

    Args:
        query: The user's original query
        client: QwenClient instance for LLM generation
        max_length: Maximum word count for the hypothetical answer

    Returns:
        A hypothetical answer string (may be empty if generation fails)

    Example:
        >>> client = get_client()
        >>> hypothetical = await generate_hypothetical_answer(
        ...     "What is the LDL-C target?",
        ...     client
        ... )
        >>> print(hypothetical)
        "The LDL-C target for secondary prevention is <1.8 mmol/L..."
    """
    if not query or not query.strip():
        logger.warning("Cannot generate hypothetical answer for empty query")
        return ""

    prompt = HYPOTHETICAL_ANSWER_PROMPT_TEMPLATE.format(max_length=max_length, query=query.strip())

    try:
        hypothetical = client.generate(
            prompt=prompt,
            context="",  # No context for hypothetical answer generation
        )

        # Clean up the response
        hypothetical = hypothetical.strip()

        # Truncate if too long
        words = hypothetical.split()
        if len(words) > max_length:
            hypothetical = " ".join(words[:max_length])

        logger.debug(f"Generated hypothetical answer for query: {query[:50]}...")
        return str(hypothetical)

    except Exception as e:
        logger.error(f"Failed to generate hypothetical answer for query '{query}': {e}")
        return ""


def expand_query_with_hyde(
    query: str,
    enable_hyde: bool = True,
) -> list[str]:
    """Expand query using HyDE if enabled.

    This is the synchronous interface for query expansion. For async
    expansion with LLM generation, use expand_query_with_hyde_async instead.

    Args:
        query: The user's original query
        enable_hyde: Whether to enable HyDE expansion

    Returns:
        List of query variants (original query + hypothetical if enabled)

    Example:
        >>> queries = expand_query_with_hyde("What is statin therapy?")
        >>> print(queries)
        ["What is statin therapy?"]
    """
    query = str(query or "").strip()
    if not query:
        return []

    if not enable_hyde:
        return [query]

    # Synchronous version just returns original query
    # Use expand_query_with_hyde_async for full HyDE functionality
    return [query]


async def expand_query_with_hyde_async(
    query: str,
    client: "QwenClient",
    enable_hyde: bool = True,
    max_length: int = HYPOTHETICAL_ANSWER_MAX_LENGTH,
) -> list[str]:
    """Expand query using HyDE with async LLM generation.

    This function generates a hypothetical answer and returns both the
    original query and the hypothetical answer for retrieval.

    Args:
        query: The user's original query
        client: QwenClient instance for LLM generation
        enable_hyde: Whether to enable HyDE expansion
        max_length: Maximum word count for the hypothetical answer

    Returns:
        List of query variants (original + hypothetical if enabled)

    Example:
        >>> client = get_client()
        >>> queries = await expand_query_with_hyde_async(
        ...     "What is the LDL-C target?",
        ...     client
        ... )
        >>> print(queries)
        [
            "What is the LDL-C target?",
            "The LDL-C target for high-risk patients is <1.8 mmol/L..."
        ]
    """
    query = str(query or "").strip()
    if not query:
        return []

    if not enable_hyde:
        return [query]

    # Generate hypothetical answer
    hypothetical = await generate_hypothetical_answer(query, client, max_length)

    # Return original + hypothetical if generation succeeded
    if hypothetical:
        return [query, hypothetical]

    # Fall back to original query only
    logger.warning("HyDE generation failed, using original query only")
    return [query]


def should_enable_hyde(
    explicit_setting: bool | None = None,
    config_setting: bool | None = None,
) -> bool:
    """Determine whether HyDE should be enabled.

    This function checks multiple sources for HyDE configuration:
    1. Explicit setting (function parameter)
    2. Configuration setting (from config file)
    3. Default (disabled)

    Args:
        explicit_setting: Explicit enable/disable from function call
        config_setting: Setting from configuration file

    Returns:
        True if HyDE should be enabled, False otherwise

    Example:
        >>> should_enable_hyde(explicit_setting=True)
        True
        >>> should_enable_hyde(explicit_setting=False)
        False
        >>> should_enable_hyde(explicit_setting=None, config_setting=True)
        True
    """
    # Explicit setting takes precedence
    if explicit_setting is not None:
        return explicit_setting

    # Check configuration setting
    if config_setting is not None:
        return config_setting

    # Default: disabled
    return False


def validate_hyde_config(
    enable_hyde: bool,
    max_length: int,
) -> tuple[bool, int]:
    """Validate HyDE configuration parameters.

    Args:
        enable_hyde: Whether HyDE is enabled
        max_length: Maximum length for hypothetical answers

    Returns:
        Tuple of (validated_enable_hyde, validated_max_length)

    Example:
        >>> validate_hyde_config(True, 500)
        (True, 500)
        >>> validate_hyde_config(True, -10)
        (True, 200)  # max_length clamped to minimum
    """
    # Validate max_length
    min_length = 50
    max_allowed_length = 500
    validated_max_length = max(min_length, min(max_length, max_allowed_length))

    if max_length != validated_max_length:
        logger.warning(
            f"HyDE max_length {max_length} out of range [{min_length}, {max_allowed_length}], "
            f"clamped to {validated_max_length}"
        )

    return enable_hyde, validated_max_length
