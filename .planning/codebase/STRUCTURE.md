# Codebase Structure

**Analysis Date:** 2026-04-06

## Directory Layout

```
qna-medical-referenced/
├── src/                          # Python source code (backend)
│   ├── app/                      # FastAPI application layer
│   │   ├── middleware/           # HTTP middleware (auth, rate limit, request ID)
│   │   ├── routes/               # API route handlers
│   │   ├── schemas/              # Request/response Pydantic models
│   │   ├── factory.py            # Application factory (create_app)
│   │   ├── exceptions.py         # Custom error types and handlers
│   │   ├── security.py           # Security configuration validation
│   │   ├── session.py            # Session management
│   │   └── logging.py            # Logging configuration
│   ├── cli/                      # CLI entry points
│   │   ├── serve.py              # Dev server entry
│   │   ├── serve_production.py   # Production server entry
│   │   ├── ingest.py             # Ingestion pipeline CLI
│   │   └── eval_pipeline.py      # Evaluation pipeline CLI
│   ├── config/                   # Configuration management
│   │   ├── settings.py           # Pydantic Settings (env vars)
│   │   └── paths.py              # Path utilities
│   ├── evals/                    # Evaluation and metrics
│   │   ├── assessment/           # Pipeline quality assessment
│   │   ├── checks/               # Individual quality checks
│   │   ├── metrics/              # Evaluation metrics
│   │   ├── synthetic/            # Synthetic data generation
│   │   ├── dataset_builder.py    # Test dataset construction
│   │   ├── deepeval_models.py    # DeepEval model wrappers
│   │   └── schemas.py            # Evaluation data schemas
│   ├── experiments/              # Experiment definitions and manifests
│   ├── infra/                    # Infrastructure adapters
│   │   ├── llm/                  # LLM client (Qwen/Dashscope)
│   │   ├── storage/              # Chat history storage
│   │   └── di.py                 # Dependency injection container
│   ├── ingestion/                # Offline data pipeline
│   │   ├── indexing/             # Vector store, embedding, search
│   │   ├── steps/                # Pipeline step functions
│   │   │   └── chunking/         # Chunking strategies
│   │   └── artifacts.py          # Pipeline artifact management
│   ├── rag/                      # RAG runtime (query-time retrieval)
│   │   ├── runtime.py            # Core retrieval logic
│   │   ├── hyde.py               # HyDE query expansion
│   │   ├── reranker.py           # Cross-encoder reranking
│   │   ├── formatting.py         # Context/source formatting
│   │   ├── trace_models.py       # Pipeline trace dataclasses
│   │   └── production_profile.py # Production config profiles
│   ├── usecases/                 # Business logic orchestration
│   │   ├── chat.py               # Chat processing (sync + streaming)
│   │   └── pipeline.py           # Offline pipeline orchestrator
│   ├── source_metadata.py        # Source document metadata pipeline
│   └── __init__.py
├── frontend/                     # SvelteKit frontend
│   ├── src/                      # Frontend source
│   ├── tests/                    # Playwright E2E tests
│   ├── static/                   # Static assets
│   ├── package.json              # Node dependencies
│   ├── svelte.config.js          # SvelteKit config
│   ├── vite.config.ts            # Vite bundler config
│   └── playwright.config.ts      # Playwright E2E config
├── tests/                        # Backend Python tests
│   ├── fixtures/                 # Test fixtures
│   └── test_*.py                 # Test modules
├── data/                         # Data directory
│   └── raw/                      # Downloaded documents (default)
├── scripts/                      # Utility scripts
├── experiments/                  # Experiment configuration files
├── docs/                         # Documentation
├── wandb/                        # Weights & Biases local data
├── docker-compose.yml            # Docker Compose configuration
├── Dockerfile                    # Backend Docker image
├── pyproject.toml                # Python project config (uv)
└── uv.lock                       # Locked Python dependencies
```

## Directory Purposes

**`src/app/`:**
- Purpose: FastAPI web application layer
- Contains: Route handlers, middleware, schemas, application factory
- Key files: `factory.py` (app creation), `routes/` (API endpoints), `middleware/` (auth, rate limiting)

**`src/cli/`:**
- Purpose: Command-line entry points
- Contains: Server startup scripts, pipeline runners
- Key files: `serve.py` (dev server), `ingest.py` (data pipeline), `eval_pipeline.py` (evaluation)

**`src/config/`:**
- Purpose: Centralized configuration
- Contains: Pydantic Settings class, path utilities
- Key files: `settings.py` (all env var definitions with defaults)

**`src/infra/`:**
- Purpose: External service adapters and dependency injection
- Contains: LLM client wrapper, storage implementations, DI container
- Key files: `di.py` (ServiceContainer), `llm/qwen_client.py`, `storage/file_chat_history_store.py`

**`src/ingestion/`:**
- Purpose: Offline data processing pipeline
- Contains: Step functions for download/convert/chunk/index, vector store abstraction
- Key files: `steps/` (individual pipeline stages), `indexing/vector_store.py`, `indexing/search.py`

**`src/rag/`:**
- Purpose: Query-time RAG retrieval and index management
- Contains: Runtime index initialization, retrieval with tracing, HyDE, reranking
- Key files: `runtime.py` (core retrieval), `trace_models.py` (pipeline tracing)

**`src/usecases/`:**
- Purpose: Business logic orchestration
- Contains: Chat processing, pipeline coordination
- Key files: `chat.py` (RAG chat orchestration), `pipeline.py` (offline pipeline runner)

**`src/evals/`:**
- Purpose: RAG quality evaluation and metrics
- Contains: DeepEval integration, metric definitions, dataset building, synthetic data
- Key files: `deepeval_models.py`, `metrics/`, `dataset_builder.py`

**`frontend/`:**
- Purpose: SvelteKit web UI
- Contains: Svelte components, Playwright E2E tests, build config
- Key files: `src/routes/` (pages), `tests/` (E2E specs)

**`tests/`:**
- Purpose: Backend Python test suite
- Contains: pytest test modules organized by feature
- Key files: `conftest.py` (fixtures), 50+ test modules

## Key File Locations

**Entry Points:**
- `src/app/factory.py`: FastAPI app factory (`create_app()`)
- `src/cli/serve.py`: Development server (`uvicorn` wrapper)
- `src/cli/serve_production.py`: Production server
- `src/usecases/pipeline.py`: Offline data pipeline (`python -m src.usecases.pipeline`)
- `src/cli/eval_pipeline.py`: Evaluation pipeline
- `frontend/src/routes/`: SvelteKit page routes

**Configuration:**
- `pyproject.toml`: Python project definition, dependencies, tool config
- `src/config/settings.py`: All application settings (env vars with defaults)
- `frontend/svelte.config.js`: SvelteKit configuration
- `frontend/vite.config.ts`: Vite bundler configuration
- `docker-compose.yml`: Multi-container orchestration
- `.env.example`: Environment variable template

**Core Logic:**
- `src/usecases/chat.py`: Main chat orchestration (sync + streaming)
- `src/rag/runtime.py`: RAG retrieval pipeline (1000+ lines)
- `src/infra/di.py`: Dependency injection container
- `src/infra/llm/qwen_client.py`: Qwen/Dashscope LLM client
- `src/ingestion/indexing/vector_store.py`: Vector store factory and implementation

**Testing:**
- `tests/`: Python test suite (pytest)
- `tests/conftest.py`: Shared fixtures
- `tests/fixtures/`: Test data fixtures
- `frontend/tests/`: Playwright E2E tests
- `frontend/playwright.config.ts`: Playwright configuration

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `chat_history_store.py`, `vector_store.py`)
- Test files: `test_<module>.py` (e.g., `test_chroma_store.py`, `test_chat_multi_turn.py`)
- CLI scripts: `snake_case.py` (e.g., `serve.py`, `eval_pipeline.py`)
- Frontend: Svelte components use PascalCase (`.svelte` files)

**Directories:**
- Python packages: `snake_case/` (e.g., `src/ingestion/`, `src/evals/`)
- Nested feature dirs: plural nouns (e.g., `routes/`, `middleware/`, `steps/`, `metrics/`)

**Classes:**
- Pydantic models: PascalCase (e.g., `Settings`, `ChatRequest`, `ChatResponse`)
- Services: PascalCase (e.g., `ServiceContainer`, `FileChatHistoryStore`, `VectorStoreFactory`)
- Use cases: snake_case functions (e.g., `process_chat_message`, `stream_chat_message`)

**Configuration:**
- Environment variables: `UPPER_SNAKE_CASE` (e.g., `DASHSCOPE_API_KEY`, `MODEL_NAME`)
- Settings attributes: `snake_case` (e.g., `dashscope_api_key`, `model_name`)

## Where to Add New Code

**New API Endpoint:**
- Route handler: `src/app/routes/<feature>.py`
- Request/response schemas: `src/app/schemas/`
- Export from: `src/app/routes/__init__.py`
- Register in: `src/app/factory.py:create_app()`

**New RAG Feature (retrieval, reranking, etc.):**
- Runtime logic: `src/rag/`
- Add to retrieval config: `src/rag/runtime.py:RetrievalDiversityConfig`
- Add settings: `src/config/settings.py:Settings`

**New Ingestion Step:**
- Step function: `src/ingestion/steps/<step_name>.py`
- Add to pipeline: `src/usecases/pipeline.py:run_pipeline()`

**New Infrastructure Service:**
- Implementation: `src/infra/<service>/`
- Register in DI: `src/infra/di.py:ServiceContainer`

**New Evaluation Metric:**
- Metric definition: `src/evals/metrics/`
- Add to pipeline: `src/cli/eval_pipeline.py`

**Utilities:**
- Shared helpers: Colocate with consuming module or add to relevant `src/<layer>/`
- Cross-cutting: Consider `src/infra/` for infrastructure utilities

## Special Directories

**`.planning/`:**
- Purpose: AI-assisted planning and codebase documentation
- Generated: Yes (by codemap skill)
- Committed: Yes

**`.deepeval/`:**
- Purpose: DeepEval evaluation framework cache and config
- Generated: Yes
- Committed: No (likely gitignored)

**`data/`:**
- Purpose: Raw and processed document storage
- Contains: Downloaded PDFs/HTML, ChromaDB persistence, evaluation artifacts
- Generated: Yes (by ingestion pipeline)
- Committed: No (gitignored)

**`wandb/`:**
- Purpose: Weights & Biases local run data
- Generated: Yes (by W&B SDK)
- Committed: No

**`experiments/`:**
- Purpose: Ablation study and experiment configuration manifests
- Contains: YAML/JSON experiment definitions
- Committed: Yes

**`.worktrees/`:**
- Purpose: Git worktrees for parallel development
- Generated: Yes (by git worktree)
- Committed: No

**`frontend/.svelte-kit/`:**
- Purpose: SvelteKit generated build artifacts
- Generated: Yes (by SvelteKit)
- Committed: No

---

*Structure analysis: 2026-04-06*
