# ARCHITECTURE.md - Patterns, Layers, Data Flow

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (SvelteKit)                 │
│                     http://localhost:5173                   │
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
│  │     Use Case (chat.py)         │                         │
│  │  ┌─────────────────────────┐   │                         │
│  │  │ RAG Runtime             │   │                         │
│  │  │ - retrieve_context()    │   │                         │
│  │  │ - Vector Store          │   │                         │
│  │  │ - Semantic Search       │   │                         │
│  │  │ - Keyword Index         │   │                         │
│  │  └───────────┬─────────────┘   │                         │
│  └──────────────┼─────────────────┘                         │
│                 │                                            │
│  ┌──────────────▼─────────────────┐                         │
│  │     LLM Client (Qwen)          │                         │
│  └───────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  Qwen API     │  │ Vector Store  │  │ Chat History  │
│  (Dashscope)  │  │ (JSON files)  │  │ (JSON file)   │
└───────────────┘  └───────────────┘  └───────────────┘
```

## Design Patterns

### 1. Separation of Concerns
The codebase is organized into clear layers with distinct responsibilities:

- **HTTP Layer** (`src/app/`): FastAPI routes, middleware, request/response schemas
- **Business Logic** (`src/usecases/`): Orchestration of workflows
- **Runtime Retrieval** (`src/rag/`): Query-time context retrieval
- **Offline Pipeline** (`src/ingestion/`): Data processing and indexing
- **Infrastructure** (`src/infra/`): External service adapters (LLM, storage)
- **Configuration** (`src/config/`): Settings and paths

### 2. Hybrid Search
Vector store combines multiple retrieval strategies:
- **Semantic Search** (60%): Qwen embeddings + cosine similarity
- **Keyword Search** (20%): TF-IDF with NLTK stemming
- **Source Boost** (20%): PDF sources boosted over CSV

### 3. Repository Pattern
- `chat_history_store.py` provides abstraction for chat persistence
- `vector_store.py` provides abstraction for vector operations
- Clear separation between interface and implementation

### 4. Middleware Chain
FastAPI middleware applied in order:
1. RequestIDMiddleware - adds request ID for tracing
2. RateLimitMiddleware - enforces rate limits
3. APIKeyMiddleware - validates API keys

### 5. Factory Pattern
- `factory.py` creates FastAPI app with proper lifespan management
- Centralizes app initialization and startup/shutdown hooks

## Layer Responsibilities

| Layer | Location | Responsibility |
|-------|----------|----------------|
| API Routes | `src/app/routes/` | HTTP endpoints, request/response handling |
| Middleware | `src/app/middleware/` | Auth, rate limiting, request ID |
| Schemas | `src/app/schemas/` | Pydantic models for validation |
| Use Cases | `src/usecases/` | Business logic orchestration |
| RAG Runtime | `src/rag/` | Query-time context retrieval |
| Ingestion Pipeline | `src/ingestion/` | Offline data processing and indexing |
| LLM Client | `src/infra/llm/qwen_client.py` | Qwen/Dashscope API integration |
| Storage | `src/infra/storage/` | Chat history persistence |
| Config | `src/config/settings.py` | Environment configuration |
| Paths | `src/config/paths.py` | Filesystem path configuration |

## Data Flow

### Chat Request Flow
1. Request arrives at `/chat` endpoint (`src/app/routes/chat.py`)
2. Middleware validates API key and rate limit
3. Use case orchestrates the flow (`src/usecases/chat.py`)
4. Session history loaded from JSON file
5. Query sent to RAG runtime (`src/rag/runtime.py`)
6. Vector store performs hybrid search (semantic + keyword)
7. Top-K documents retrieved as context
8. Qwen LLM generates response with context
9. Response + sources saved to chat history
10. Response returned to client with optional pipeline trace

### Offline Ingestion Flow
1. Pipeline runner invoked (`src/cli/ingest.py`)
2. Download web content (optional) (`src/ingestion/steps/download_web.py`)
3. Convert HTML to Markdown (`src/ingestion/steps/convert_html.py`)
4. Load PDF documents (`src/ingestion/steps/load_pdfs.py`)
5. Chunk documents with overlap (`src/ingestion/steps/chunk_text.py`)
6. Load CSV reference ranges (`src/ingestion/steps/load_reference_data.py`)
7. Generate embeddings and build index (`src/ingestion/indexing/vector_store.py`)
8. Persist vector store to disk (`src/ingestion/indexing/persistence.py`)
9. Runtime index availability confirmed (`src/rag/runtime.py`)

## Module Communication

### Synchronous vs Asynchronous
- **Synchronous**: LLM calls, vector store operations, file I/O
- **Async**: HTTP request handling (FastAPI async routes)

### Error Handling
- Errors propagate through use case layer
- HTTP responses use appropriate status codes
- Detailed error messages in development mode

## Configuration Management

### Settings (`src/config/settings.py`)
- Uses Pydantic BaseSettings for type-safe configuration
- Environment variables loaded with proper defaults
- Validation at startup

### Paths (`src/config/paths.py`)
- Centralizes filesystem path configuration
- OS-agnostic path handling
- Data directory organization

## Testing Strategy

### Backend Tests
- Unit tests for individual components
- Integration tests for API endpoints
- Evaluation tests for quality assessment

### Frontend Tests
- Playwright E2E tests for user flows
- Component testing for Svelte components

## Security Considerations

1. **API Key Authentication**: Optional API key validation via middleware
2. **Rate Limiting**: Per-IP rate limiting to prevent abuse
3. **Request Tracing**: Request ID middleware for debugging
4. **Environment Variables**: Sensitive data in `.env` file (not committed)

## Performance Optimizations

1. **Hybrid Search**: Combines semantic and keyword search for better relevance
2. **Lazy Loading**: Vector index loaded only at startup
3. **Caching**: Chat history cached in memory
4. **Chunk Overlap**: 150-character overlap for better context retrieval

## Scalability Considerations

1. **Stateless API**: Each request is independent
2. **File-based Storage**: Easy to migrate to database if needed
3. **Modular Design**: Easy to replace components (LLM provider, vector store)
4. **Docker Support**: Containerized deployment with docker-compose
