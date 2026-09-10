# Architecture

> **Active refactor:** `docs/plans/20260910-structural-refactor-roadmap.md` (Phases 0–3).
> Known violations marked below are scheduled there; this file is updated in the same PR as each change.

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
| Routes | `src/app/routes/` | REST API endpoint definitions (chat, health, history, evaluation, config, experiments, documents — 7 routers mounted in `factory.py`) |
| Middleware | `src/app/middleware/` | Cross-cutting concerns: auth (`APIKeyMiddleware`), rate limiting (`RateLimitMiddleware`), request tracing (`RequestIDMiddleware`) |
| Schemas | `src/app/schemas/` | Pydantic request/response models |
| Exceptions | `src/app/exceptions.py` | Domain exceptions (`AppError`, `UpstreamServiceError`, etc.) with FastAPI error handlers |
| Security | `src/app/security.py` | API key validation (bcrypt + SHA256 legacy), `AuthContext`, deployment security checks |
| Session | `src/app/session.py` | Anonymous chat session management via cookies |

**Middleware execution order** (outermost to innermost):
1. `CORSMiddleware` — cross-origin request handling
2. `RateLimitMiddleware` — sliding-window rate limiting via SQLite
3. `APIKeyMiddleware` — validates `X-API-Key` header
4. `RequestIDMiddleware` — adds `X-Request-ID` header

### 2. Use Case Layer (`src/usecases/`)

Orchestration logic that coordinates domain operations. Each use case represents a user-facing workflow.

| Use Case | File | Flow |
|----------|------|------|
| Chat | `src/usecases/chat.py` | Retrieve history → RAG retrieval → LLM generation → persist history → return response (sync + streaming) |

The historical `usecases/pipeline.py` compat shim was deleted in Phase 1; the ingestion entrypoint is `src/cli/ingest.py` (→ `src/ingestion/pipeline.py`).

### 3. RAG Layer (`src/rag/`)

The retrieval-augmented generation engine. This is the core domain logic — **recently refactored from a single god module into focused sub-modules**.

| Module | Responsibility | Size |
|--------|---------------|------|
| `runtime.py` | Central orchestrator: coordinates retrieval pipeline stages | ~500 lines |
| `index.py` | Index initialization, vector store setup, experiment config application | ~360 lines |
| `config.py` | `RetrievalDiversityConfig` dataclass + config resolution + validation | ~105 lines |
| `diversification.py` | MMR reranking + result deduplication (`mmr_rerank`, `diversify_results`) | ~130 lines |
| `query_expansion.py` | Lexical/medical query expansion, HyDE async wrapper | ~125 lines |
| `retrieval.py` | Candidate retrieval from vector store + result merging | ~115 lines |
| `formatting.py` | Formats retrieved chunks into context strings and `ChatSource` citations | ~90 lines |
| `hyde.py` | HyDE (Hypothetical Document Embeddings) query-time expansion; index-time HyPE question generation moved to `infra/llm/hypothetical_questions.py` (P3.1) | ~180 lines |
| `reranker.py` | Cross-encoder reranking using sentence-transformers | ~155 lines |
| `medical_expansion.py` | Medical term expansion provider (currently noop) | ~60 lines |
| `production_profile.py` | Applies tuned retrieval profiles from ablation studies | ~115 lines |
| `trace_models.py` | Pydantic models for pipeline tracing (`PipelineTrace`, `RetrievedDocument`, etc.) | ~110 lines |
| `query_understanding/` | Query type classification and retrieval parameter routing | ~590 lines total |

### 4. Ingestion Layer (`src/ingestion/`)

Offline data processing pipeline that transforms raw documents into searchable vectors.

**Pipeline stages** (executed sequentially):

| Stage | Step File | Description |
|-------|-----------|-------------|
| L0 | `steps/download_web.py` | Download HTML content from configured URLs |
| L0b | `steps/download_pdfs.py` | Download PDF documents |
| L1 | `steps/convert_html.py` | Convert HTML to Markdown (trafilatura/BS4) |
| L2 | `steps/load_pdfs.py`, `steps/load_markdown.py` | Load and parse documents into structured format |
| L3 | `steps/chunking/` | Chunk documents (structured, medical-semantic, or simple strategies) |
| L3b | `steps/hypothetical_questions.py` | Generate HyPE (Hypothetical Prompt Embedding) questions |
| L3c | `steps/enrich_chunks.py` | LLM-based keyword extraction and summarization |
| L4 | `steps/load_reference_data.py` | Load medical reference ranges |
| L5 | `indexing/` | Embed and store in ChromaDB |

**Indexing subsystem** (`src/ingestion/indexing/`):

| Module | Role |
|--------|------|
| `chroma_store.py` | ChromaDB-backed vector store with hybrid search (semantic + BM25 + RRF fusion) — ~1010 lines |
| `embedding.py` | Text embedding via Qwen/OpenAI-compatible API |
| `keyword_index.py` | BM25 keyword search with medical entity boosting |
| `search.py` | Cosine similarity, rank fusion, MMR diversification algorithms |
| `text_utils.py` | Tokenization, acronym expansion, content hashing |
| `migrate.py` | Migration utilities |

**Hamilton DAG tier** (`src/ingestion/nodes/`): thin DAG nodes (`download.py`, `parse.py`, `chunk.py`, `enrich.py`, `reference.py`, `embedding.py` — one per canonical stage, see `docs/architecture/pipeline-stages.md`) that delegate to the `steps/` implementations above. Renamed from digit-prefixed `components/` in Phase 1; normal imports, public `NODE_MODULES` list.

### 5. Infrastructure Layer (`src/infra/`)

Technical infrastructure and cross-cutting concerns.

| Module | Role |
|--------|------|
| `llm/qwen_client.py` | Qwen/DashScope OpenAI-compatible LLM client (sync + async streaming) |
| `llm/litellm_client.py` | LiteLLM client for multi-provider support (OpenRouter, etc.) |
| `llm/hypothetical_questions.py` | HyPE index-time hypothetical question generation (moved from `rag/hyde.py` in P3.1) |
| `storage/interfaces.py` | `ChatHistoryStore` Protocol (interface) for storage abstraction |
| `storage/chat_history_store.py` | Abstract base for chat history |
| `storage/file_chat_history_store.py` | JSON file-backed chat history implementation with per-session message truncation |

### 6. Evaluation Layer (`src/evals/`)

Assessment and quality measurement framework.

| Module | Role |
|--------|------|
| `assessment/orchestrator.py` | End-to-end evaluation orchestration — ~645 lines |
| `assessment/answer_eval.py` | LLM-as-judge answer quality evaluation |
| `assessment/retrieval_eval.py` | Retrieval quality metrics — ~765 lines |
| `assessment/thresholds.py` | Quality threshold management |
| `assessment/reporting.py` | Report generation |
| `assessment/l6_contract.py` | L6 contract validation |
| `dataset_builder.py` | Build evaluation datasets |
| `synthetic/generator.py` | Synthetic Q&A pair generation |
| `metrics/medical.py` | Domain-specific medical metrics |
| `checks/` | Leveled quality checks (L0–L5) for each pipeline stage |
| `schemas.py` | Evaluation data models |
| `artifacts.py` | Evaluation artifact management |
| `deepeval_models.py` | DeepEval integration models |
| `pipeline_assessment.py` | Pipeline-level assessment |
| `step_checks.py` | Per-step quality checks |

### 7. Experiment Layer (`src/experiments/`)

Ablation study and experiment management.

| Module | Role |
|--------|------|
| `addition_config.py` | Feature-addition experiment schema (variants vs baseline) |
| `config.py` | Experiment configuration loading (YAML) |
| `feature_ablation_runner.py` | Feature ablation study execution |
| `feature_addition_runner.py` | Feature addition experiments |
| `wandb_tracking.py` | Weights & Biases integration for experiment tracking |
| `wandb_history.py` | W&B run history querying |
| `comparison_report.py` | Cross-experiment comparison reports |
| `metric_utils.py` | Metric computation helpers |
| `run_addition.py` | Addition experiment runner |

### 8. Configuration Layer (`src/config/`)

Centralized settings management using Pydantic `BaseSettings` with YAML + env var sources.

| Module | Role |
|--------|------|
| `settings.py` | `Settings` class with nested Pydantic models (AppConfig, ApiConfig, LLMConfig, StorageConfig, RetrievalConfig, HyDEConfig, HypeConfig, EnrichmentConfig, RetryConfig, DeepEvalConfig, WandbConfig, ProductionConfig) — loads from `config/settings.yaml` + env vars with `APP__` prefix. Deprecated `hyde.hype_*` keys are migrated onto `settings.hype` with a warning (roadmap P3.6) |
| `context.py` | `RuntimeState` — thread-safe mutable runtime state singleton for feature flags and runtime configuration |
| `paths.py` | Canonical filesystem paths derived from settings |
| `__init__.py` | Re-exports `settings` and path constants |

**Config sources** (priority order):
1. Direct `__init__` kwargs
2. Environment variables with `APP__` prefix (e.g., `APP__API__CORS_ALLOWED_ORIGINS`)
3. `.env` file (via dotenvx)
4. `config/settings.yaml` (defaults)

### 9. (removed) Services Layer

The `src/services/` layer was folded into `evals/` in Phase 1: `EvaluationService` (artifact
reading for the evaluation route) lives at `src/evals/artifact_service.py`; `BaseService` was
deleted. The main chat flow calls `src/rag/runtime.py` and `src/usecases/chat.py` directly.

## Data Flow Through the System

### Request Lifecycle (Chat)

```
User → Frontend (SvelteKit)
  → POST /chat (SSE streaming)
    → CORSMiddleware
    → RateLimitMiddleware (sliding-window check via SQLite)
    → APIKeyMiddleware (validate X-API-Key if configured)
    → RequestIDMiddleware (attach X-Request-ID)
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
  → src/ingestion/pipeline.py: build_ingestion_pipeline() (Hamilton DAG, single driver)
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

1. **`ChatHistoryStore` (Protocol)** — `src/infra/storage/interfaces.py:8` — Interface for chat history persistence. Implemented by `FileChatHistoryStore` with per-session message truncation.

2. **Composition root (app lifespan)** — `src/app/factory.py::lifespan` — the only server-side place that constructs concrete dependencies (`LLMClient`, `FileChatHistoryStore`, `ChromaVectorStore` via the factory singleton); stashes them on `app.state`. Routes receive them through the accessors in `src/app/dependencies.py` (roadmap P3.1; replaced the deleted `infra/di.py` `ServiceContainer`).

3. **`RuntimeState`** — `src/config/context.py:11` — Thread-safe mutable runtime state with property-based access. Manages feature flags and runtime configuration overrides.

4. **`RetrievalDiversityConfig`** — `src/rag/config.py:14` — Dataclass controlling retrieval behavior (search mode, reranking, diversification, HyDE, HyPE, etc.).

5. **`PipelineTrace`** — `src/rag/trace_models.py` — Pydantic model capturing end-to-end pipeline metrics (retrieval timing, scores, reranking info, generation timing).

6. **`ChromaVectorStore`** — `src/ingestion/indexing/chroma_store.py` — Core vector store with hybrid search, BM25 + semantic + RRF fusion (~1010 lines).

7. **`EvaluationService`** — `src/evals/artifact_service.py` — loads and shapes evaluation artifacts for the evaluation route.

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
├── config/       ← Settings (YAML + env vars), paths, runtime state — no business logic dependencies
├── core/         ← Shared kernel: source_metadata, layer-agnostic exceptions — depends on nothing
├── evals/        ← Evaluation framework — depends on rag/, infra/, config/
├── experiments/  ← Ablation/experiment management — depends on evals/, config/
├── infra/        ← Infrastructure (DI, LLM clients, storage) — depends on config/
├── ingestion/    ← Data pipeline (download, convert, chunk, index) — depends on infra/, config/
├── rag/          ← Retrieval engine — depends on ingestion/, infra/, config/
└── usecases/     ← Use case orchestration (chat only) — depends on rag/, infra/, core/
```

**Dependency direction:** `cli/` → `usecases/` → `rag/` → `ingestion/` → `infra/` → `config/`. The `app/` layer calls into `usecases/`. `config/` is the deepest layer with no business logic dependencies.

**Cross-boundary rules:**
- `config/` never imports from other `src/` modules
- `infra/` depends only on `config/` and `core/` (layer-agnostic exceptions moved to `core/exceptions.py` in Phase 1; `app/exceptions.py` re-exports them)
- `ingestion/` depends on `infra/` and `config/`
- `rag/` depends on `ingestion/`, `infra/`, and `config/`
- `app/` depends on `usecases/`, `infra/`, `rag/`, and `config/`
- `services/` was folded into `evals/` in Phase 1 (`EvaluationService` → `evals/artifact_service.py`); the layer no longer exists
