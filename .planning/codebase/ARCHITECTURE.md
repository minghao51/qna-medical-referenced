# ARCHITECTURE.md - Patterns, Layers, Data Flow

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (SvelteKit)                 │
│                     http://localhost:5174                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/JSON
┌──────────────────────────▼──────────────────────────────────┐
│                    Backend (FastAPI)                         │
│                     http://localhost:8000                    │
├─────────────────────────────────────────────────────────────┤
│  Middleware: RequestID → RateLimit → APIKey                 │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   /chat      │  │  /history    │  │  /health         │   │
│  │   POST       │  │  GET/DELETE  │  │  GET             │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────┘   │
│         │                 │                                  │
│  ┌──────▼─────────────────▼───────┐                         │
│  │     RAG Pipeline (L6)          │                         │
│  │  ┌─────────────────────────┐   │                         │
│  │  │ Vector Store (L5)       │   │                         │
│  │  │ - Semantic Search       │   │                         │
│  │  │ - TF-IDF Keyword Index  │   │                         │
│  │  └───────────┬─────────────┘   │                         │
│  └──────────────┼─────────────────┘                         │
│                 │                                            │
│  ┌──────────────▼─────────────────┐                         │
│  │     LLM Client (Gemini)        │                         │
│  └───────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  Gemini API   │  │ Vector Store  │  │ Chat History  │
│  (Generation) │  │ (JSON files)  │  │ (JSON file)   │
└───────────────┘  └───────────────┘  └───────────────┘
```

## Design Patterns

### 1. Pipeline Pattern (L0-L6)
Data processing follows a sequential pipeline:
- **L0**: Download HTML from web sources
- **L1**: Convert HTML to Markdown
- **L2**: Load PDF documents
- **L3**: Chunk documents (800 chars, 150 overlap)
- **L4**: Load CSV reference ranges
- **L5**: Generate embeddings + build TF-IDF index
- **L6**: Initialize RAG pipeline

### 2. Hybrid Search
Vector store combines:
- **Semantic Search** (60%): Gemini embeddings + cosine similarity
- **Keyword Search** (20%): TF-IDF with NLTK stemming
- **Source Boost** (20%): PDF sources boosted over CSV

### 3. Singleton Pattern
- `get_client()` in `src/llm/client.py`
- `get_vector_store()` in `src/pipeline/L5_vector_store.py`

### 4. Middleware Chain
FastAPI middleware applied in order:
1. RequestIDMiddleware - adds request ID for tracing
2. RateLimitMiddleware - enforces rate limits
3. APIKeyMiddleware - validates API keys

## Layer Responsibilities

| Layer | Location | Responsibility |
|-------|----------|----------------|
| API Routes | `src/main.py` | HTTP endpoints, request/response |
| Middleware | `src/middleware/` | Auth, rate limiting, request ID |
| LLM Client | `src/llm/client.py` | Gemini API integration |
| Pipeline | `src/pipeline/` | Data processing (L0-L6) |
| Vector Store | `src/pipeline/L5_vector_store.py` | Hybrid search |
| Storage | `src/storage/chat_store.py` | Chat history persistence |
| Config | `src/config/settings.py` | Environment configuration |

## Data Flow

### Chat Request Flow
1. Request arrives at `/chat` endpoint
2. Middleware validates API key and rate limit
3. Session history loaded from JSON file
4. Query sent to RAG pipeline
5. Vector store performs hybrid search (semantic + keyword)
6. Top-K documents retrieved as context
7. Gemini LLM generates response with context
8. Response + sources saved to chat history
9. Response returned to client

### Pipeline Initialization Flow
1. Server starts (`src/main.py`)
2. `initialize_vector_store()` called at startup
3. PDF documents loaded (L2)
4. Documents chunked (L3)
5. Reference ranges loaded (L4)
6. All documents embedded and indexed (L5)
7. RAG ready for queries (L6)
