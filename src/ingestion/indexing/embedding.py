"""Embedding helpers for the vector store using Qwen models."""

import time
from collections import OrderedDict
from threading import Lock
from typing import List

from openai import OpenAI

from src.config import settings

EMBEDDING_MODEL = settings.llm.embedding_model
_EMBEDDING_CACHE_MAX_ENTRIES = 512
_embedding_cache: OrderedDict[tuple[str, str], List[float]] = OrderedDict()
_embedding_cache_lock = Lock()


def get_embedding_client() -> OpenAI:
    """Get a configured OpenAI client for Qwen embeddings.

    Returns:
        OpenAI client configured for Dashscope API
    """
    return OpenAI(api_key=settings.dashscope_api_key, base_url=settings.qwen_base_url)


def _cache_get(model_name: str, text: str) -> List[float] | None:
    key = (model_name, text)
    with _embedding_cache_lock:
        value = _embedding_cache.get(key)
        if value is None:
            return None
        _embedding_cache.move_to_end(key)
        return list(value)


def _cache_put(model_name: str, text: str, embedding: List[float]) -> None:
    key = (model_name, text)
    with _embedding_cache_lock:
        _embedding_cache[key] = list(embedding)
        _embedding_cache.move_to_end(key)
        while len(_embedding_cache) > _EMBEDDING_CACHE_MAX_ENTRIES:
            _embedding_cache.popitem(last=False)


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

    start_time = time.time()
    model_name = model or EMBEDDING_MODEL
    all_embeddings: List[List[float] | None] = [None] * len(texts)
    uncached_items: list[tuple[int, str]] = []
    cache_hits = 0

    for idx, text in enumerate(texts):
        cached = _cache_get(model_name, text)
        if cached is not None:
            all_embeddings[idx] = cached
            cache_hits += 1
        else:
            uncached_items.append((idx, text))

    if uncached_items:
        client = get_embedding_client()
        for i in range(0, len(uncached_items), batch_size):
            batch_items = uncached_items[i : i + batch_size]
            batch = [text for _, text in batch_items]
            response = client.embeddings.create(model=model_name, input=batch, dimensions=768)
            for (idx, text), item in zip(batch_items, response.data, strict=True):
                embedding = item.embedding
                all_embeddings[idx] = embedding
                _cache_put(model_name, text, embedding)

    resolved_embeddings = [embedding for embedding in all_embeddings if embedding is not None]
    if len(resolved_embeddings) != len(texts):
        raise RuntimeError("Embedding generation returned incomplete results")

    return resolved_embeddings, {
        "text_count": len(texts),
        "batch_count": (len(uncached_items) + batch_size - 1) // batch_size if uncached_items else 0,
        "batch_size": batch_size,
        "embedding_model": model_name,
        "elapsed_ms": int((time.time() - start_time) * 1000),
        "failure_count": 0,
        "cache_hit_count": cache_hits,
        "cache_miss_count": len(uncached_items),
    }


def embed_texts(
    texts: List[str], batch_size: int = 10, model: str | None = None
) -> List[List[float]]:
    embeddings, _ = embed_texts_with_stats(texts, batch_size=batch_size, model=model)
    return embeddings
