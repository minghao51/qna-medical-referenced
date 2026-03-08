"""Embedding helpers for the vector store using Qwen models."""

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


def embed_texts(texts: List[str], batch_size: int = 10) -> List[List[float]]:
    """Generate embeddings for a list of texts using Qwen.

    Args:
        texts: List of text strings to embed
        batch_size: Number of texts to process per API call

    Returns:
        List of embedding vectors (each is a list of floats)
    """
    if not texts:
        return []

    client = get_embedding_client()
    all_embeddings: List[List[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        all_embeddings.extend([e.embedding for e in response.data])

    return all_embeddings
