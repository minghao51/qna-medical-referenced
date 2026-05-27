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
    client: QwenClient,
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

        logger.debug("Generated hypothetical answer for query: %s...", query[:50])
        return str(hypothetical)

    except Exception as e:
        logger.error("Failed to generate hypothetical answer for query '%s': %s", query, e)
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
    client: QwenClient,
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


HYPE_QUESTION_PROMPT_TEMPLATE = """Given this medical document chunk, generate {count} question(s) that this chunk would answer.
Focus on specific medical terminology, clinical values, and guideline recommendations.

Document chunk:
{chunk}

Generate {count} question(s), each on its own line. Be specific and use medical terminology."""


async def generate_hypothetical_questions(
    chunk: str,
    client: QwenClient,
    count: int = 2,
) -> list[str]:
    """Generate hypothetical questions that a chunk could answer.

    This is used for HyPE (Hypothetical Prompt Embedding) — generating
    questions at index time that chunks could answer, stored in metadata
    for zero-LLM-cost query expansion at retrieval time.

    Args:
        chunk: The document chunk text
        client: QwenClient instance for LLM generation
        count: Number of questions to generate (1-2)

    Returns:
        List of question strings that the chunk could answer
    """
    if not chunk or not chunk.strip():
        logger.warning("Cannot generate hypothetical questions for empty chunk")
        return []

    count = max(1, min(2, int(count)))
    prompt = HYPE_QUESTION_PROMPT_TEMPLATE.format(count=count, chunk=chunk.strip())

    try:
        response = client.generate(prompt=prompt, context="")
        questions = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("-"):
                line = line.lstrip("0123456789. )").strip()
            if line and len(line) > 10:
                questions.append(line)
        result = questions[:count]
        logger.debug(
            "Generated %d hypothetical questions for chunk: %s...", len(result), chunk[:50]
        )
        return result
    except Exception as e:
        logger.error("Failed to generate hypothetical questions: %s", e)
        return []
