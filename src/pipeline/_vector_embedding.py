"""Embedding helpers for the vector store."""

from typing import List

EMBEDDING_MODEL = "gemini-embedding-001"


def embed_texts(client, texts: List[str], batch_size: int = 10) -> List[List[float]]:
    if not texts:
        return []

    all_embeddings: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=batch,
        )
        all_embeddings.extend([embedding.values for embedding in result.embeddings])
    return all_embeddings

