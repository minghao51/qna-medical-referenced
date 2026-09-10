"""HyPE (Hypothetical Prompt Embedding) question generation for indexing.

Moved from ``src/rag/hyde.py`` in Phase 3 (roadmap P3.1) so that the
ingestion package stops importing from ``rag``: index-time hypothetical
question generation is an LLM prompting concern and belongs beside the
LLM clients. Query-time HyDE (hypothetical document expansion) stays in
``src/rag/hyde.py``.

Reference:
    HyPE shifts HyDE-style computation from query time to index time,
    generating "what questions does this chunk answer?" at ingestion
    rather than "what answer would this query get?" at retrieval.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infra.llm.qwen_client import QwenClient

logger = logging.getLogger(__name__)


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
