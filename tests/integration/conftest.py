import hashlib
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"

FAKE_EMBEDDING_DIM = 8


def _ensure_nltk_stopwords_available() -> None:
    """Ensure the NLTK 'stopwords' corpus resolves without network access.

    src/ingestion/indexing/text_utils.py loads English stopwords at import
    time. On machines without ``nltk.download('stopwords')`` (e.g. CI
    runners), fall back to the vendored copy under
    tests/integration/fixtures/nltk_data. Must run before any module that
    imports src.ingestion.indexing (i.e. at conftest import time).
    """
    try:
        from nltk.corpus import stopwords

        stopwords.words("english")
        return
    except LookupError:
        pass

    import nltk.data

    nltk.data.path.append(str(FIXTURES_DIR / "nltk_data"))
    from nltk.corpus import stopwords as vendored_stopwords

    vendored_stopwords.words("english")  # fail fast if the vendored copy is broken


_ensure_nltk_stopwords_available()


def _fake_embedding(text: str) -> list[float]:
    """Deterministic unit vector derived from a stable hash of the text."""
    digest = hashlib.sha256(text.lower().encode("utf-8")).digest()
    raw = [byte / 255.0 for byte in digest[:FAKE_EMBEDDING_DIM]]
    norm = math.sqrt(sum(v * v for v in raw)) or 1.0
    return [v / norm for v in raw]


@pytest.fixture
def fake_chroma_embeddings(monkeypatch, tmp_path):
    """Replace the Qwen embedding API with deterministic offline vectors.

    Patches the embedding functions at the chroma_store module boundary (the
    only place ChromaVectorStore calls them) and isolates ChromaDB
    persistence under tmp_path (also forcing the embedded client even if the
    host is configured for a Chroma server). ChromaDB itself still runs for
    real, so store semantics are genuinely exercised without any API key or
    network.
    """
    import src.ingestion.indexing.chroma_store as chroma_store
    from src.config import settings

    def fake_embed_texts(texts, batch_size=10, model=None):
        return [_fake_embedding(text) for text in texts]

    def fake_embed_texts_with_stats(texts, batch_size=10, model=None):
        vectors = fake_embed_texts(texts, batch_size, model)
        stats = {
            "provider": "offline-stub",
            "model": model or "offline-stub",
            "batch_size": batch_size,
            "count": len(texts),
        }
        return vectors, stats

    monkeypatch.setattr(chroma_store, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(chroma_store, "embed_texts_with_stats", fake_embed_texts_with_stats)
    monkeypatch.setattr(settings.storage, "chroma_server_host", "")
    monkeypatch.setattr(settings.storage, "chroma_persist_directory", str(tmp_path / "chroma"))
    return fake_embed_texts


@pytest.fixture
def app_client(monkeypatch, tmp_path):
    """Create a TestClient with mocked deps for integration tests."""
    from src.app.factory import create_app

    monkeypatch.setattr("src.app.factory.validate_security_configuration", lambda: None)
    monkeypatch.setattr("src.app.factory.initialize_runtime_index_async", lambda: None)
    app = create_app()
    return TestClient(app)
