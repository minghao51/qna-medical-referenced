# Architecture

## Project Structure

```
src/
├── main.py              # FastAPI app entry point
├── config/
│   └── settings.py      # Configuration management
├── ingest/
│   └── __init__.py      # PDF loading
├── processors/
│   └── chunker.py       # Text chunking
├── vectorstore/
│   └── store.py         # Hybrid search (semantic + keyword)
├── rag/
│   └── retriever.py     # RAG pipeline
├── llm/
│   └── client.py        # Gemini LLM client
└── middleware/
    ├── auth.py          # API key validation
    ├── rate_limit.py    # Rate limiting
    └── request_id.py   # Request ID tracking
```

## Pipeline

```
User Query → RAG Retriever → Hybrid Search → LLM → Response
                                    ↓
                              ┌──────┴──────┐
                              ↓             ↓
                        Semantic      TF-IDF Keyword
                        (embeddings)  (index + stemming)
```

## Components

### 1. PDFLoader (`src/ingest/__init__.py`)
- Loads PDFs from `data/raw/`
- Extracts text per page
- Output: `{"id": "...", "source": "...", "pages": [{"page": 1, "content": "..."}]}`

### 2. TextChunker (`src/processors/chunker.py`)
- Chunks text into 800-char segments with 150-char overlap
- Priority: paragraph break → line break → sentence end
- Output: `{"id": "...", "content": "...", "source": "...", "page": N}`

### 3. VectorStore (`src/vectorstore/store.py`)
- **Semantic search**: Gemini embeddings (3072-dim)
- **Keyword search**: TF-IDF with stemming (Snowball) and stop words
- **Hybrid scoring**: 60% semantic + 20% keyword + 20% source boost
- Persists to JSON at `data/vectors/medical_docs.json`

### 4. ReferenceDataLoader (`src/rag/retriever.py`)
- Loads lab reference ranges from CSV
- Combines with PDF chunks for indexing

### 5. GeminiClient (`src/llm/client.py`)
- Wraps Gemini API with retry logic
- Generates responses with RAG context

### 6. Middleware
- **APIKeyMiddleware**: Validates `X-API-Key` header
- **RateLimitMiddleware**: 60 req/min per IP
- **RequestIDMiddleware**: Adds request ID to logs
