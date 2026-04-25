from src.ingestion.indexing import embedding


class _DummyEmbeddingItem:
    def __init__(self, value):
        self.embedding = value


class _DummyEmbeddingsAPI:
    def __init__(self):
        self.calls = []

    def create(self, *, model, input, dimensions):
        self.calls.append({"model": model, "input": list(input), "dimensions": dimensions})
        return type(
            "Response",
            (),
            {
                "data": [
                    _DummyEmbeddingItem([float(idx), float(len(text))])
                    for idx, text in enumerate(input, start=1)
                ]
            },
        )()


class _DummyClient:
    def __init__(self):
        self.embeddings = _DummyEmbeddingsAPI()


def test_embed_texts_uses_cache(monkeypatch):
    client = _DummyClient()
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: client)

    with embedding._embedding_cache_lock:
        embedding._embedding_cache.clear()

    first_embeddings, first_stats = embedding.embed_texts_with_stats(
        ["alpha", "beta"],
        batch_size=2,
        model="test-model",
    )
    second_embeddings, second_stats = embedding.embed_texts_with_stats(
        ["alpha", "beta"],
        batch_size=2,
        model="test-model",
    )

    assert first_embeddings == second_embeddings
    assert len(client.embeddings.calls) == 1
    assert first_stats["cache_hit_count"] == 0
    assert first_stats["cache_miss_count"] == 2
    assert second_stats["cache_hit_count"] == 2
    assert second_stats["cache_miss_count"] == 0


def test_embed_texts_only_requests_uncached_texts(monkeypatch):
    client = _DummyClient()
    monkeypatch.setattr(embedding, "get_embedding_client", lambda: client)

    with embedding._embedding_cache_lock:
        embedding._embedding_cache.clear()

    embedding.embed_texts_with_stats(["alpha"], batch_size=1, model="test-model")
    embeddings, stats = embedding.embed_texts_with_stats(
        ["alpha", "gamma"],
        batch_size=2,
        model="test-model",
    )

    assert len(client.embeddings.calls) == 2
    assert client.embeddings.calls[1]["input"] == ["gamma"]
    assert len(embeddings) == 2
    assert stats["cache_hit_count"] == 1
    assert stats["cache_miss_count"] == 1
