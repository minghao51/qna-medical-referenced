# Architecture

## Pattern

**Layered Domain-Driven Design** with a FastAPI backend and SvelteKit frontend, following a pipeline-oriented architecture for RAG (Retrieval-Augmented Generation).

The system is split into two deployable units:
- **Backend** (`src/`): Python 3.12 FastAPI application — handles ingestion, vector indexing, retrieval, and LLM-powered chat
- **Frontend** (`frontend/`): SvelteKit 5 SPA — provides the user-facing chat interface and evaluation dashboards

## Layers and Responsibilities

### 1. Presentation Layer (`src/app/`)

HTTP interface built on FastAPI. Contains routes, middleware, schemas, and error handling.

| Component | Location | Role |
|-----------|----------|------|
| Routes | `src/app/routes/` | REST API endpoint definitions (chat, health, history, evaluation) |
| Middleware | `src/app/middleware/` | Cross-cutting concerns: auth (`APIKeyMiddleware`), rate limiting (`RateLimitMiddleware`), request tracing (`RequestIDMiddleware`) |
| Schemas | `src/app/schemas/` | Pydantic request/response models |
| Exceptions | `src/app/exceptions.py` | Domain exceptions (`AppError`, `UpstreamServiceError`, etc.) with FastAPI error handlers |
| Security | `src/app/security.py` | API key validation (bcrypt), `AuthContext`, deployment security checks |
| Session | `src/app/session.py` | Anonymous chat session management via cookies |

**Middleware execution order** (outermost to innermost):
1. `RequestIDMiddleware` — adds `X-Request-ID` header
2. `APIKeyMiddleware` — validates `X-API-Key` header
3. `RateLimitMiddleware` — sliding-window rate limiting via SQLite
4. `CORSMiddleware` — cross-origin request handling

### 2. Use Case Layer (`src/usecases/`)

Orchestration logic that coordinates domain operations. Each use case represents a user-facing workflow.

| Use Case | File | Flow |
|----------|------|------|
| Chat | `src/usecases/chat.py` | Retrieve history → RAG retrieval → LLM generation → persist history → return response (sync + streaming) |
| Pipeline | `src/usecases/pipeline.py` | CLI-driven sequential pipeline: download → convert → load → chunk → enrich → embed → index |

### 3. RAG Layer (`src/rag/`)

The retrieval-augmented generation engine. This is the core domain logic.

| Module | Responsibility |
|--------|---------------|
| `runtime.py` | Central orchestrator for retrieval: query expansion, candidate retrieval, reranking, diversification, context assembly. ~1400 lines — the largest single module |
| `formatting.py` | Formats retrieved chunks into context strings and `ChatSource` citations |
| `hyde.py` | HyDE (Hypothetical Document Embeddings) — generates hypothetical answers to improve retrieval |
| `reranker.py` | Cross-encoder reranking using sentence-transformers |
| `medical_expansion.py` | Medical term expansion provider (currently noop, designed for ontology integration) |
| `production_profile.py` | Applies tuned retrieval profiles from ablation studies |
| `trace_models.py` | Pydantic models for pipeline tracing (`PipelineTrace`, `RetrievedDocument`, etc.) |
| `query_understanding/` | Query type classification and retrieval parameter routing |

### 4. Ingestion Layer (`src/ingestion/`)

Offline data processing pipeline that transforms raw documents into searchable vectors.

**Pipeline stages** (executed sequentially):

| Stage | Step File | Description |
|-------|-----------|-------------|
| L0 | `steps/download_web.py` | Download HTML content from configured URLs |
| L0b | `steps/download_pdfs.py` | Download PDF documents |
| L1 | `steps/convert_html.py` | Convert HTML to Markdown (trafilatura/BS4) |
| L2 | `steps/load_pdfs.py`, `steps/load_markdown.py` | Load and parse documents into structured format |
| L3 | `steps/chunk_text.py` → `steps/chunking/` | Chunk documents (structured, medical-semantic, or simple strategies) |
| L3b | `steps/hype.py` | Generate HyPE (Hypothetical Prompt Embedding) questions |
| L3c | `steps/enrich_chunks.py` | LLM-based keyword extraction and summarization |
| L4 | `steps/load_reference_data.py` | Load medical reference ranges |
| L5 | `indexing/` | Embed and store in ChromaDB |

**Indexing subsystem** (`src/ingestion/indexing/`):

| Module | Role |
|--------|------|
| `chroma_store.py` | ChromaDB-backed vector store with hybrid search (semantic + BM25 + RRF fusion) |
| `embedding.py` | Text embedding via Qwen/OpenAI-compatible API |
| `keyword_index.py` | BM25 keyword search with medical entity boosting |
| `search.py` | Cosine similarity, rank fusion, MMR diversification algorithms |
| `text_utils.py` | Tokenization, acronym expansion, content hashing |
| `vector_store.py` | Backward-compatibility shim re-exporting `ChromaVectorStore` |

### 5. Infrastructure Layer (`src/infra/`)

Technical infrastructure and cross-cutting concerns.

| Module | Role |
|--------|------|
| `di.py` | `ServiceContainer` — simple DI container with lazy initialization for vector store, LLM client, retrieval config |
| `llm/qwen_client.py` | Qwen/DashScope OpenAI-compatible LLM client (sync + async streaming) |
| `llm/litellm_client.py` | LiteLLM client for multi-provider support (OpenRouter, etc.) |
| `storage/interfaces.py` | `ChatHistoryStore` Protocol (interface) for storage abstraction |
| `storage/chat_history_store.py` | Abstract base for chat history |
| `storage/file_chat_history_store.py` | JSON file-backed chat history implementation |

### 6. Evaluation Layer (`src/evals/`)

Assessment and quality measurement framework.

| Module | Role |
|--------|------|
| `assessment/orchestrator.py` | End-to-end evaluation orchestration |
| `assessment/answer_eval.py` | LLM-as-judge answer quality evaluation |
| `assessment/retrieval_eval.py` | Retrieval quality metrics |
| `assessment/thresholds.py` | Quality threshold management |
| `assessment/l6_contract.py` | L6 contract validation |
| `dataset_builder.py` | Build evaluation datasets |
| `synthetic/generator.py` | Synthetic Q&A pair generation |
| `metrics/medical.py` | Domain-specific medical metrics |
| `checks/` | Leveled quality checks (L0–L5) for each pipeline stage |
| `schemas.py` | Evaluation data models |
| `artifacts.py` | Evaluation artifact management |

### 7. Experiment Layer (`src/experiments/`)

Ablation study and experiment management.

| Module | Role |
|--------|------|
| `config.py` | Experiment configuration loading (YAML) |
| `experiment_config.py` | Experiment config models |
| `feature_ablation_runner.py` | Feature ablation study execution |
| `feature_addition_runner.py` | Feature addition experiments |
| `wandb_tracking.py` | Weights & Biases integration for experiment tracking |
| `wandb_history.py` | W&B run history querying |
| `comparison_report.py` | Cross-experiment comparison reports |

### 8. Configuration Layer (`src/config/`)

Centralized settings management using Pydantic BaseSettings.

| Module | Role |
|--------|------|
| `settings.py` | `Settings` class — all configuration from env vars with defaults (~590 lines). Manages LLM, retrieval, rate limiting, ingestion, and evaluation settings |
| `context.py` | `RuntimeState` — thread-safe mutable runtime state singleton for feature flags and runtime configuration |
| `paths.py` | Canonical filesystem paths derived from settings |
| `__init__.py` | Re-exports `settings` and path constants |

### 9. Services Layer (`src/services/`)

Service abstraction layer (partially adopted).

| Module | Role |
|--------|------|
| `base_service.py` | `BaseService` with logging |
| `vector_store_service.py` | Vector store access abstraction |
| `rag_service.py` | RAG retrieval orchestration service |
| `evaluation_service.py` | Evaluation orchestration service |

**Note:** This layer exists but is not consistently used. The main chat flow still calls `src/rag/runtime.py` and `src/usecases/chat.py` directly rather than through services. The DI container (`src/infra/di.py`) manages service lifecycle.

## Data Flow Through the System

### Request Lifecycle (Chat)

```
User → Frontend (SvelteKit)
  → POST /chat (SSE streaming)
    → RequestIDMiddleware (attach X-Request-ID)
    → APIKeyMiddleware (validate X-API-Key if configured)
    → RateLimitMiddleware (sliding-window check via SQLite)
    → CORSMiddleware
    → chat route handler
      → ensure_chat_session (set/refresh anonymous session cookie)
      → stream_chat_message()
        → retrieve history from FileChatHistoryStore
        → retrieve_context() / retrieve_context_with_trace_async()
          → query expansion (lexical + medical + HyDE + HyPE)
          → vector store hybrid search (ChromaDB: semantic + BM25 + RRF fusion)
          → cross-encoder reranking (optional)
          → MMR diversification
          → context assembly
        → LLM client.generate_stream() (Qwen or LiteLLM)
        → yield SSE events (content tokens, then final metadata with sources)
        → persist messages to history
  ← SSE stream → Frontend renders tokens
```

### Ingestion Pipeline Flow

```
CLI: python -m src.cli.ingest
  → src/usecases/pipeline.py: run_pipeline()
    → L0: download_web.py → data/raw/*.html
    → L0b: download_pdfs.py → data/raw/*.pdf
    → L1: convert_html.py → data/processed/*.md
    → L2: load_pdfs.py + load_markdown.py → List[Document]
    → L3: chunk_text.py → chunking/ (structured/medical-semantic/simple)
       → List[Chunk] with metadata
    → L3b: hype.py (optional) → generate hypothetical questions
    → L3c: enrich_chunks.py (optional) → extract keywords, summarize
    → L4: load_reference_data.py → reference range docs
    → L5: chroma_store.py → embed via Qwen + store in ChromaDB
         + build BM25 keyword index
    → L6: initialize_runtime_index() → mark index ready
```

### Evaluation Flow

```
CLI: python -m src.cli.eval_pipeline
  → src/evals/assessment/orchestrator.py
    → Load/generate evaluation dataset
    → For each test case:
      → Run RAG retrieval + generation
      → Apply LLM-as-judge metrics (via DeepEval)
      → Collect pipeline trace
    → Compute aggregate metrics
    → Compare against thresholds
    → Generate report
    → Optionally log to W&B
```

## Key Abstractions

1. **`ChatHistoryStore` (Protocol)** — `src/infra/storage/interfaces.py:8` — Interface for chat history persistence. Implemented by `FileChatHistoryStore`.

2. **`ServiceContainer`** — `src/infra/di.py:29` — DI container managing lazy-initialized services (vector store, LLM client, configs). Global singleton via `get_container()`.

3. **`RuntimeState`** — `src/config/context.py:11` — Thread-safe mutable runtime state with property-based access. Manages feature flags and runtime configuration overrides.

4. **`RetrievalDiversityConfig`** — `src/rag/runtime.py:99` — Configuration dataclass controlling retrieval behavior (search mode, reranking, diversification, HyDE, HyPE, etc.).

5. **`PipelineTrace`** — `src/rag/trace_models.py` — Pydantic model capturing end-to-end pipeline metrics (retrieval timing, scores, reranking info, generation timing).

6. **`ChromaVectorStore`** — `src/ingestion/indexing/chroma_store.py` — Core vector store with hybrid search, BM25 + semantic + RRF fusion.

7. **`BaseService`** — `src/services/base_service.py:9` — Service base class with logging. Subclassed by `RAGService`, `VectorStoreService`, `EvaluationService`.

## Entry Points

| Entry Point | Command | Purpose |
|-------------|---------|---------|
| Dev server | `python -m src.cli.serve` | Uvicorn with hot-reload on `:8000` |
| Production server | `python -m src.cli.serve_production` | Uvicorn, single worker, concurrency-limited |
| Ingestion | `python -m src.cli.ingest` | Full offline data pipeline |
| Eval pipeline | `python -m src.cli.eval_pipeline` | Evaluation orchestrator CLI |
| Docker | `docker-compose up` | Backend (`:8000`) + Frontend (`:5173`) + test profile |
| Frontend dev | `cd frontend && npm run dev` | SvelteKit dev server on `:5173` |

## Module Boundaries

```
src/
├── app/          ← HTTP layer (routes, middleware, schemas) — depends on usecases/, config/
├── cli/          ← CLI entry points — thin wrappers calling usecases/ or uvicorn
├── config/       ← Settings, paths, runtime state — no business logic dependencies
├── evals/        ← Evaluation framework — depends on rag/, infra/, config/
├── experiments/  ← Ablation/experiment management — depends on evals/, config/
├── infra/        ← Infrastructure (DI, LLM clients, storage) — depends on config/
├── ingestion/    ← Data pipeline (download, convert, chunk, index) — depends on infra/, config/
├── rag/          ← Retrieval engine — depends on ingestion/, infra/, config/
├── services/     ← Service abstractions — depends on rag/, ingestion/, config/
└── usecases/     ← Use case orchestration — depends on rag/, infra/, app/
```

**Dependency direction:** `cli/` → `usecases/` → `rag/` → `ingestion/` → `infra/` → `config/`. The `app/` layer calls into `usecases/`. `config/` is the deepest layer with no business logic dependencies.

**Cross-boundary rules:**
- `config/` never imports from other `src/` modules (except `settings.py` has no src imports)
- `infra/` only depends on `config/`
- `ingestion/` depends on `infra/` and `config/`
- `rag/` depends on `ingestion/`, `infra/`, and `config/`
- `app/` depends on `usecases/`, `infra/`, `rag/`, and `config/`
- `services/` is an emerging abstraction layer that wraps `rag/` and `ingestion/`
