# Architecture

## Architectural Pattern

The application follows a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
│                    (FastAPI Routes)                          │
│  /chat, /evaluation, /health, /history                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Middleware Layer                          │
│  CORS → RateLimit → APIKey → RequestID                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Application Layer                         │
│  (Use Cases & Business Logic)                                │
│  - Chat orchestration                                        │
│  - Evaluation pipelines                                      │
│  - Session management                                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Domain Layer                              │
│  (RAG & Evaluation Core)                                     │
│  - Retrieval runtime                                         │
│  - HyDE query expansion                                      │
│  - Assessment orchestrator                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Infrastructure Layer                      │
│  - LLM clients (Qwen)                                        │
│  - Vector stores                                             │
│  - File storage (chat history)                               │
│  - Ingestion pipeline                                        │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Web Application Layer

**Entry Point**: `src/app/factory.py`
- Application factory pattern
- Middleware registration
- Lifecycle management (startup/shutdown)
- Route registration

**Routes** (`src/app/routes/`):
- `chat.py` - Main chat endpoint with streaming RAG
- `evaluation.py` - Evaluation and benchmarking endpoints
- `health.py` - Health check endpoint
- `history.py` - Chat history management

**Middleware** (`src/app/middleware/`):
- `auth.py` - API key validation
- `rate_limit.py` - Request throttling
- `request_id.py` - Request tracing

### 2. Use Case Layer

**Chat Orchestration** (`src/usecases/chat.py`):
- Streams chat responses with RAG
- Manages conversation history
- Coordinates retrieval and generation
- Handles pipeline metadata

**Evaluation Pipeline** (`src/evals/`):
- `assessment/` - Answer and retrieval evaluation
- `metrics/` - Custom medical domain metrics
- `synthetic/` - Test case generation
- `dataset_builder.py` - Evaluation dataset construction

### 3. RAG Engine

**Retrieval Runtime** (`src/rag/runtime.py`):
- Hybrid search (dense + sparse)
- MMR (Maximal Marginal Relevance) diversification
- RRF (Reciprocal Rank Fusion) ranking
- Query expansion via HyDE

**HyDE** (`src/rag/hyde.py`):
- Hypothetical document generation
- Query expansion for better retrieval
- Multi-document expansion strategies

**Configuration**:
- Runtime settings loaded from config
- Dynamic chunking strategies
- Retrieval diversity tuning

### 4. Ingestion Pipeline

**Pipeline Steps** (`src/ingestion/steps/`):
1. **Download**: PDFs and web content
2. **Convert**: HTML → Markdown
3. **Chunk**: Structured/semantic text chunking
4. **Embed**: Generate vector embeddings
5. **Index**: Store in vector database

**Chunking Strategies** (`src/ingestion/steps/chunking/`):
- Structured chunking (section-aware)
- Semantic chunking (topic-based)
- Configuration-driven selection

**Text Processing** (`src/ingestion/indexing/`):
- `text_utils.py` - Tokenization and acronyms
- `vector_store.py` - Vector database operations
- `embedding.py` - Embedding generation

### 5. Infrastructure Layer

**LLM Integration** (`src/infra/llm/`):
- `qwen_client.py` - Dashscope API client
- Async generation with streaming
- Error handling and retries

**Storage** (`src/infra/storage/`):
- `file_chat_history_store.py` - JSON-based chat history
- Session persistence

**Configuration** (`src/config/`):
- `settings.py` - Pydantic-based settings
- Environment variable loading
- Validation on import

## Data Flow

### Chat Request Flow

```
User Request
    ↓
[CORS Middleware]
    ↓
[RateLimit Middleware]
    ↓
[APIKey Middleware]
    ↓
[RequestID Middleware]
    ↓
Chat Route (/chat)
    ↓
Chat Use Case (stream_chat_message)
    ↓
RAG Runtime (retrieve)
    ├─→ HyDE Query Expansion
    ├─→ Vector Store Search
    └─→ MMR Re-ranking
    ↓
LLM Client (generate)
    ↓
Streaming Response
```

### Ingestion Pipeline Flow

```
Source Data (PDF/Web)
    ↓
Download Step
    ↓
Convert Step (HTML→MD)
    ↓
Chunk Step (structured/semantic)
    ↓
Embed Step (vector generation)
    ↓
Index Step (vector store)
    ↓
Searchable Knowledge Base
```

### Evaluation Flow

```
Evaluation Request
    ↓
Dataset Builder
    ├─→ Load test cases
    └─→ Generate synthetic cases
    ↓
Assessment Orchestrator
    ├─→ Run RAG pipeline
    ├─→ Evaluate answer quality
    └─→ Calculate metrics
    ↓
WandB Tracking
    ↓
Evaluation Report
```

## Key Design Patterns

### 1. Application Factory Pattern
- **Location**: `src/app/factory.py`
- **Purpose**: Centralized app creation and configuration
- **Benefits**: Testability, dependency injection

### 2. Middleware Chain Pattern
- **Location**: `src/app/middleware/`
- **Purpose**: Cross-cutting concerns (auth, rate limiting)
- **Order**: CORS → RateLimit → APIKey → RequestID

### 3. Repository Pattern
- **Location**: `src/infra/storage/`
- **Purpose**: Abstract storage implementations
- **Example**: `FileChatHistoryStore` interface

### 4. Strategy Pattern
- **Location**: `src/ingestion/steps/chunking/`
- **Purpose**: Pluggable chunking strategies
- **Benefits**: Runtime configuration

### 5. Builder Pattern
- **Location**: `src/evals/dataset_builder.py`
- **Purpose**: Construct complex evaluation datasets
- **Benefits**: Fluent configuration

## Concurrency & Async

### Async/Await Usage
- FastAPI endpoints are async
- LLM client uses async streaming
- HTTP operations via httpx (async)
- Database operations use SQLite (synchronous with locks)

### Thread Safety
- Rate limiter uses SQLite with connection locks
- Vector store initialization is thread-safe
- Chat history store uses file locking

## Error Handling

### Exception Hierarchy
```
Exception
    └─→ AppError (base application exception)
        ├─→ InvalidInputError (400)
        ├─→ UpstreamServiceError (502)
        ├─→ ArtifactNotFoundError (404)
        └─→ StorageError (500)
```

### Error Handlers
- `app_error_handler` - Custom application errors
- `http_exception_handler` - FastAPI HTTP exceptions
- `unhandled_exception_handler` - Catch-all for unexpected errors

### Response Format
All errors return JSON with:
```json
{
  "detail": "Error message",
  "error": {
    "code": "error_code",
    "status_code": 400,
    "request_id": "uuid"
  }
}
```

## Configuration Management

### Settings Hierarchy
1. Environment variables (highest priority)
2. `.env` file
3. Pydantic defaults

### Runtime Configuration
- Vector store settings loaded dynamically
- Chunking strategies configurable
- Retrieval parameters tunable at runtime

## Testing Strategy

### Test Layers
1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Pipeline and flow testing
3. **E2E Tests**: Full stack with real APIs
4. **Evaluation Tests**: RAG quality assessment

### Test Fixtures
- `conftest.py` - Shared fixtures
- Mock LLM clients
- Temporary file storage
- Test data factories

## Deployment Architecture

### Docker Multi-Stage Build
1. **Builder Stage**: Install dependencies
2. **Runtime Stage**: Minimal production image
3. **Development**: Hot-reload with volume mounts

### Service Dependencies
- Backend: Python 3.13 runtime
- Frontend: Node.js build → Static files
- Health checks on startup
- Resource limits (CPU, memory)
