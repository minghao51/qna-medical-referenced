# Architecture

**Analysis Date:** 2026-04-06

## Pattern Overview

**Overall:** Layered Architecture with Clean Architecture influences (onion architecture)

**Key Characteristics:**
- FastAPI application factory pattern for testability
- Dependency Injection container (`ServiceContainer`) managing infra services
- Clear separation between offline ingestion pipeline and online RAG runtime
- Use case layer orchestrates infrastructure services
- Modular route handlers with middleware stack
- Configuration driven via Pydantic BaseSettings from environment variables

## Layers

**CLI Layer (`src/cli/`):**
- Purpose: Entry points for running the application
- Location: `src/cli/`
- Contains: Server startup (`serve.py`, `serve_production.py`), pipeline runner (`ingest.py`), evaluation pipeline (`eval_pipeline.py`)
- Depends on: `src.app.factory`, `src.usecases.pipeline`
- Used by: External invocation (uvicorn, python -m)

**API/Route Layer (`src/app/routes/`):**
- Purpose: HTTP request handling and response formatting
- Location: `src/app/routes/`
- Contains: Chat, health, history, evaluation routers
- Depends on: `src.usecases`, `src.app.schemas`, `src.app.middleware`
- Used by: HTTP clients (frontend SvelteKit app, API consumers)

**Use Case Layer (`src/usecases/`):**
- Purpose: Business logic orchestration
- Location: `src/usecases/`
- Contains: Chat orchestration (`chat.py`), offline pipeline runner (`pipeline.py`)
- Depends on: `src.infra` (LLM client, storage), `src.rag` (retrieval)
- Used by: Route handlers, CLI commands

**RAG Runtime Layer (`src/rag/`):**
- Purpose: Retrieval-augmented generation at query time
- Location: `src/rag/`
- Contains: Runtime index init, retrieval with trace, HyDE expansion, reranking, formatting
- Depends on: `src.ingestion.indexing` (vector store), `src.config.settings`
- Used by: Use case layer (chat)

**Infrastructure Layer (`src/infra/`):**
- Purpose: External service adapters and DI container
- Location: `src/infra/`
- Contains: LLM client (Qwen/Dashscope), storage (file-based chat history), DI container
- Depends on: `src.config.settings`, external APIs (OpenAI-compatible, ChromaDB)
- Used by: Use case layer, DI container

**Ingestion Layer (`src/ingestion/`):**
- Purpose: Offline data pipeline for building the knowledge base
- Location: `src/ingestion/`
- Contains: Steps (download, convert, chunk, load), indexing (vector store, embedding, keyword index, search)
- Depends on: PDF parsers, HTML extractors, ChromaDB
- Used by: Pipeline use case, RAG runtime (at startup)

**Evaluation Layer (`src/evals/`):**
- Purpose: RAG quality assessment and metrics
- Location: `src/evals/`
- Contains: DeepEval integration, metrics, dataset builder, synthetic data generation, pipeline assessment
- Depends on: `src.rag`, `src.infra.llm`, DeepEval library
- Used by: Evaluation routes, CLI eval pipeline

**Configuration Layer (`src/config/`):**
- Purpose: Centralized settings management
- Location: `src/config/`
- Contains: Pydantic Settings class, path utilities
- Depends on: Environment variables, `.env` file
- Used by: All layers

## Data Flow

**Chat Request Flow:**
1. HTTP POST `/chat` arrives at `src/app/routes/chat.py`
2. Route handler calls `src/usecases/chat.py:process_chat_message()` or `stream_chat_message()`
3. Use case retrieves conversation history from `ChatHistoryStore`
4. Use case calls `src/rag/runtime.py:retrieve_context()` or `retrieve_context_with_trace()`
5. RAG runtime expands query (tokenization, acronyms, optional HyDE/HyPE)
6. Vector store performs similarity search (semantic, BM25, or hybrid RRF)
7. Optional reranking via cross-encoder and/or MMR diversification
8. Retrieved context formatted and returned to use case
9. Use case calls LLM client (`src/infra/llm/qwen_client.py`) to generate response
10. Response + sources saved to history store
11. Response returned to route handler, then to client

**Ingestion Pipeline Flow:**
1. CLI invokes `src/cli/ingest.py` or `python -m src.usecases.pipeline`
2. Pipeline orchestrator runs steps sequentially:
   - L0: Download web content + PDFs
   - L1: Convert HTML to Markdown
   - L2: Load PDF documents
   - L3: Chunk documents (with optional HyPE question generation)
   - L4: Load reference data
   - L5: Embed and store vectors in ChromaDB
   - L6: Initialize RAG runtime index
3. Each step reads from `data/` directory and writes intermediate artifacts

**Application Startup Flow:**
1. `src/app/factory.py:create_app()` called
2. Security configuration validated
3. FastAPI app created with lifespan manager
4. Middleware stack configured (CORS → RateLimit → APIKey → RequestID)
5. Routes registered (health, chat, history, evaluation)
6. On startup (lifespan): DI container initialized, LLM client created, vector index loaded, production profile applied if configured

**State Management:**
- Configuration: Singleton `Settings` instance from `src/config/settings.py`
- Services: `ServiceContainer` in `src/infra/di.py` with lazy initialization
- Vector store: Persisted to `data/chroma/` via ChromaDB
- Chat history: File-based storage (`FileChatHistoryStore`)
- Production profiles: Applied at startup via `src/rag/production_profile.py`

## Key Abstractions

**ServiceContainer:**
- Purpose: Dependency injection container for infra services
- Examples: `src/infra/di.py`
- Pattern: Lazy-initialized singleton with reset capability for testing

**ChatHistoryStore (Interface):**
- Purpose: Abstract chat history persistence
- Examples: `src/infra/storage/interfaces.py`, `src/infra/storage/file_chat_history_store.py`
- Pattern: Interface + implementation for testability

**VectorStoreFactory:**
- Purpose: Factory for creating vector store instances
- Examples: `src/ingestion/indexing/vector_store.py`
- Pattern: Factory pattern with configuration-driven instantiation

**Pipeline Steps:**
- Purpose: Modular ingestion pipeline stages
- Examples: `src/ingestion/steps/` (download_web, convert_html, chunk_text, etc.)
- Pattern: Step functions composed by pipeline orchestrator

**PipelineTrace:**
- Purpose: Structured tracing of RAG pipeline execution
- Examples: `src/rag/trace_models.py`
- Pattern: Dataclass-based trace with timing information per stage

## Entry Points

**Web API Server:**
- Location: `src/cli/serve.py`
- Triggers: `python -m src.cli.serve` or `uvicorn src.app.factory:app`
- Responsibilities: Starts FastAPI dev server on port 8000 with hot reload

**Production Server:**
- Location: `src/cli/serve_production.py`
- Triggers: `python -m src.cli.serve_production`
- Responsibilities: Starts production uvicorn server

**Ingestion Pipeline:**
- Location: `src/cli/ingest.py`
- Triggers: `python -m src.cli.ingest` or `python -m src.usecases.pipeline`
- Responsibilities: Runs full offline data pipeline

**Evaluation Pipeline:**
- Location: `src/cli/eval_pipeline.py`
- Triggers: `python -m src.cli.eval_pipeline`
- Responsibilities: Runs RAG evaluation with DeepEval metrics

**Application Factory:**
- Location: `src/app/factory.py:create_app()`
- Triggers: Imported by CLI serve commands, Docker entrypoint
- Responsibilities: Creates and configures FastAPI app with all middleware, routes, and exception handlers

## Error Handling

**Strategy:** Centralized exception handlers registered in factory

**Patterns:**
- Custom `AppError` base class with `app_error_handler` in `src/app/exceptions.py`
- `UpstreamServiceError` raised for LLM API failures in use case layer
- HTTP exception handler for FastAPI `HTTPException`
- Unhandled exception handler catches all remaining exceptions
- Stream errors yield error event before raising `UpstreamServiceError`

## Cross-Cutting Concerns

**Logging:** Python standard logging, configured via `src/app/logging.py`, level from settings

**Validation:** Pydantic models for settings (`src/config/settings.py`) and request/response schemas (`src/app/schemas/`)

**Authentication:** API key middleware (`src/app/middleware/auth.py`) with optional API keys from settings; anonymous session tracking via cookies

**Rate Limiting:** Per-client rate limiting middleware (`src/app/middleware/rate_limit.py`), configurable per-minute limits with separate quota for anonymous chat

**Request Tracing:** RequestID middleware (`src/app/middleware/request_id.py`) adds X-Request-ID header for distributed tracing

---

*Architecture analysis: 2026-04-06*
