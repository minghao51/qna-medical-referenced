# Architecture

## Pattern

**Layered RAG Architecture** with clear separation between ingestion, processing, storage, and presentation layers.

## Layers

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **API** | `src/main.py` | FastAPI app, endpoints, middleware |
| **Config** | `src/config/settings.py` | Settings management |
| **LLM** | `src/llm/` | Gemini API integration |
| **RAG** | `src/rag/` | Retrieval orchestration |
| **Vector Store** | `src/vectorstore/` | Embedding storage, hybrid search |
| **Processors** | `src/processors/` | Text chunking |
| **Ingest** | `src/ingest/` | PDF loading |

## Data Flow

```
User Query → FastAPI /chat → retrieve_context() → similarity_search()
                                                        ↓
                                              ┌─────────┴─────────┐
                                              ↓                   ↓
                                        Semantic            Keyword TF-IDF
                                        (embeddings)        (stemming)
                                              ↓                   ↓
                                              └─────────┬─────────┘
                                                        ↓
                                               Combined scores
                                                        ↓
                                               Top-k results
                                                        ↓
                                              GeminiClient.generate()
                                                        ↓
                                              Response + Sources
```

## Initialization Flow

```
App Startup → initialize_vector_store()
                    ↓
        ┌───────────┴───────────┐
        ↓                       ↓
    PDFLoader              ReferenceDataLoader
        ↓                       ↓
    TextChunker            CSV → docs
        ↓                       ↓
    VectorStore.add_documents()
        ↓
    Embed + Index → JSON
```

## Key Interfaces

| Module | Interface | Purpose |
|--------|-----------|---------|
| `src/ingest` | `get_documents()` | Load all PDFs |
| `src/processors` | `chunk_documents()` | Chunk into 800-char segments |
| `src/vectorstore` | `get_vector_store()` | Singleton accessor |
| `src/vectorstore` | `similarity_search()` | Hybrid search |
| `src/rag` | `retrieve_context()` | Returns (context, sources) |
| `src/llm` | `get_client()` | Gemini client |

## Document Schema

```python
# Raw document (PDFLoader)
{"id": str, "source": str, "pages": [{"page": int, "content": str}]}

# Chunked document
{"id": str, "source": str, "page": int, "content": str}

# Vector store (JSON)
{"ids": [], "contents": [], "embeddings": [], "metadatas": [], "content_hashes": []}
```

## API Endpoints

| Endpoint | Method | Handler |
|----------|--------|---------|
| `/` | GET | root() |
| `/health` | GET | health_check() |
| `/chat` | POST | chat(ChatRequest) |

## Middleware

| Middleware | Purpose |
|------------|---------|
| APIKeyMiddleware | Validates X-API-Key |
| RateLimitMiddleware | 60 req/min per IP |
| RequestIDMiddleware | Adds request ID to logs |

## Configuration

- Environment: `.env` file
- Settings: `src/config/settings.py`
- Embedding model: `gemini-embedding-001`
- Generation model: `gemini-2.0-flash`
- Chunk size: 800 chars, 150 overlap
- Top-k: 5

## Hybrid Search Weights

| Component | Weight |
|-----------|--------|
| Semantic (embeddings) | 60% |
| Keyword (TF-IDF) | 20% |
| Source boost | 20% |

## Extension Points

1. **New data sources**: Add loaders in `src/ingest/`
2. **Different embedding**: Modify `VectorStore._embed()`
3. **Tune weights**: Adjust in `similarity_search()`
4. **Add conversation history**: Extend ChatRequest
