"""Embedding helpers for the vector store using Qwen models."""

import time
from typing import List

from openai import OpenAI

from src.config import settings

EMBEDDING_MODEL = settings.embedding_model


def get_embedding_client() -> OpenAI:
    """Get a configured OpenAI client for Qwen embeddings.

    Returns:
        OpenAI client configured for Dashscope API
    """
    return OpenAI(api_key=settings.dashscope_api_key, base_url=settings.qwen_base_url)


def embed_texts_with_stats(
    texts: List[str], batch_size: int = 10, model: str | None = None
) -> tuple[List[List[float]], dict]:
    """Generate embeddings for a list of texts using Qwen.

    Args:
        texts: List of text strings to embed
        batch_size: Number of texts to process per API call

    Returns:
        List of embedding vectors (each is a list of floats)
    """
    if not texts:
        return [], {
            "text_count": 0,
            "batch_count": 0,
            "batch_size": batch_size,
            "embedding_model": model or EMBEDDING_MODEL,
            "elapsed_ms": 0,
            "failure_count": 0,
        }

    client = get_embedding_client()
    all_embeddings: List[List[float]] = []
    start_time = time.time()
    model_name = model or EMBEDDING_MODEL

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=model_name, input=batch, dimensions=768)
        all_embeddings.extend([e.embedding for e in response.data])

    return all_embeddings, {
        "text_count": len(texts),
        "batch_count": (len(texts) + batch_size - 1) // batch_size,
        "batch_size": batch_size,
        "embedding_model": model_name,
        "elapsed_ms": int((time.time() - start_time) * 1000),
        "failure_count": 0,
    }


def embed_texts(
    texts: List[str], batch_size: int = 10, model: str | None = None
) -> List[List[float]]:
    embeddings, _ = embed_texts_with_stats(texts, batch_size=batch_size, model=model)
    return embeddings
