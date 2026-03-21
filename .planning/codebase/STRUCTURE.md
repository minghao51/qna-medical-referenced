# Directory Structure

## Top-Level Layout

```
qna_medical_referenced/
├── .planning/              # Planning and codebase documentation
│   └── codebase/          # This documentation
├── docs/                  # Project documentation
│   ├── reports/           # Implementation reports
│   ├── testing/           # Testing guides
│   └── plans/             # Design documents
├── frontend/              # SvelteKit frontend application
│   ├── src/               # Svelte components and routes
│   ├── static/            # Static assets
│   ├── tests/             # Playwright E2E tests
│   └── package.json       # Frontend dependencies
├── scripts/               # Utility scripts
│   └── benchmark_*.py     # Benchmarking utilities
├── src/                   # Backend Python source
│   ├── app/               # FastAPI application layer
│   ├── cli/               # Command-line interfaces
│   ├── config/            # Configuration management
│   ├── evals/             # Evaluation framework
│   ├── experiments/       # Experiment tracking
│   ├── infra/             # Infrastructure (LLM, storage)
│   ├── ingestion/         # Data ingestion pipeline
│   ├── rag/               # RAG engine
│   └── usecases/          # Business logic layer
├── tests/                 # Backend test suite
├── .env                   # Environment variables (not in git)
├── docker-compose.yml     # Local development orchestration
├── Dockerfile             # Multi-stage container build
├── pyproject.toml         # Python project configuration
└── README.md              # Project overview
```

## Backend Structure (`src/`)

### `src/app/` - Application Layer
```
app/
├── factory.py              # FastAPI application factory
├── security.py             # Security configuration helpers
├── logging.py              # Structured logging utilities
├── exceptions.py           # Domain exception classes
├── session.py              # Session management
├── schemas/                # Pydantic request/response models
│   └── chat.py             # Chat-related schemas
├── middleware/             # HTTP middleware
│   ├── auth.py             # API key authentication
│   ├── rate_limit.py       # Rate limiting
│   └── request_id.py       # Request tracing
└── routes/                 # API endpoints
    ├── chat.py             # Chat endpoint (862 lines)
    ├── evaluation.py       # Evaluation endpoints (862 lines)
    ├── health.py           # Health check
    └── history.py          # Chat history management
```

### `src/cli/` - Command-Line Interfaces
```
cli/
├── serve.py                # Development server
├── serve_production.py     # Production server
├── ingest.py               # Ingestion pipeline CLI
├── eval_pipeline.py        # Evaluation CLI (292 lines)
└── __init__.py
```

### `src/config/` - Configuration
```
config/
├── settings.py             # Pydantic settings (305 lines)
└── __init__.py             # Settings singleton export
```

### `src/evals/` - Evaluation Framework
```
evals/
├── dataset_builder.py      # Evaluation dataset construction (622 lines)
├── pipeline_assessment.py  # Pipeline evaluation
├── deepeval_models.py      # DeepEval integration
├── artifacts.py            # Evaluation result artifacts
├── assessment/             # Assessment modules
│   ├── orchestrator.py     # Evaluation orchestration (524 lines)
│   ├── answer_eval.py      # Answer quality evaluation (492 lines)
│   ├── retrieval_eval.py   # Retrieval quality evaluation (437 lines)
│   ├── reporting.py        # Evaluation reporting
│   └── thresholds.py       # Quality thresholds
├── metrics/                # Custom metrics
│   ├── medical.py          # Medical domain metrics
│   └── _utils.py           # Metric utilities
├── synthetic/              # Synthetic test generation
│   └── generator.py        # Test case generation
└── checks/                 # Evaluation checks
    ├── l0_download.py      # Download checks
    └── l2_pdf.py           # PDF validation checks
```

### `src/experiments/` - Experiment Tracking
```
experiments/
├── config.py               # Experiment configuration (481 lines)
├── wandb_tracking.py       # WandB integration (353 lines)
├── wandb_history.py        # Run history management
└── __init__.py
```

### `src/infra/` - Infrastructure Layer
```
infra/
├── llm/                    # LLM client abstraction
│   ├── qwen_client.py      # Qwen/Dashscope client (315 lines)
│   └── __init__.py         # Client factory
└── storage/                # Storage implementations
    ├── file_chat_history_store.py  # JSON-based history
    └── __init__.py
```

### `src/ingestion/` - Data Ingestion Pipeline
```
ingestion/
├── steps/                  # Pipeline steps
│   ├── chunking/           # Text chunking strategies
│   │   ├── core.py         # Chunking logic (401 lines)
│   │   └── config.py       # Chunking configuration
│   ├── download_pdfs.py    # PDF download (243 lines)
│   ├── download_web.py     # Web scraping (552 lines)
│   ├── convert_html.py     # HTML→Markdown (407 lines)
│   ├── load_pdfs.py        # PDF loading (236 lines)
│   ├── load_markdown.py    # Markdown loading
│   ├── load_reference_data.py  # Reference data loading
│   └── chunk_text.py       # Chunking orchestration
└── indexing/               # Indexing and search
    ├── vector_store.py     # Vector database (523 lines)
    ├── embedding.py        # Embedding generation
    ├── search.py           # Search interface
    ├── text_utils.py       # Text processing utilities
    └── __init__.py
```

### `src/rag/` - RAG Engine
```
rag/
├── runtime.py              # RAG retrieval runtime (816 lines)
├── hyde.py                 # HyDE query expansion (252 lines)
├── formatting.py           # Context and source formatting
├── trace_models.py         # Tracing data models
└── __init__.py             # Runtime initialization
```

### `src/usecases/` - Business Logic Layer
```
usecases/
├── chat.py                 # Chat orchestration (237 lines)
└── __init__.py
```

## Frontend Structure (`frontend/`)

```
frontend/
├── src/
│   ├── routes/             # SvelteKit file-based routing
│   │   ├── chat/           # Chat interface
│   │   ├── eval/           # Evaluation dashboard
│   │   │   └── +page.svelte  # Large component (2439 lines)
│   │   └── +layout.svelte  # Root layout
│   ├── lib/                # Shared utilities
│   └── app.html            # HTML template
├── static/                 # Static assets
├── tests/                  # Playwright E2E tests
│   ├── chat.spec.ts        # Chat flow tests
│   └── eval.spec.ts        # Evaluation tests
├── package.json            # Dependencies
├── vite.config.ts          # Vite configuration
├── svelte.config.js        # Svelte configuration
└── tsconfig.json           # TypeScript configuration
```

## Test Structure (`tests/`)

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── test_app_security.py     # Security tests
├── test_backend_e2e_real_apis.py  # E2E tests (458 lines)
├── test_chat_sources.py     # Chat source citation tests
├── test_chunker.py          # Chunking tests
├── test_deepeval_models.py  # DeepEval integration tests
├── test_download_pdfs_manifest.py  # PDF download tests
├── test_download_web_manifest.py   # Web scraping tests
├── test_embedding.py        # Embedding tests
├── test_eval_deepeval.py    # Evaluation tests
├── test_eval_error_handling.py     # Error handling tests
├── test_evaluation_routes.py       # Route tests
├── test_experiment_config.py       # Experiment config tests
├── test_experiment_manifest.py     # Experiment manifest tests
├── test_hyde.py             # HyDE tests
├── test_orchestrator_deepeval.py   # Orchestrator tests
├── test_retrieval.py        # Retrieval tests
├── test_runtime_index_initialization.py  # Index init tests
├── test_wandb_tracking.py   # WandB tests
└── test_*.py                # Additional test modules
```

## Key File Locations

### Configuration Files
- `pyproject.toml` - Python dependencies and tool config
- `docker-compose.yml` - Docker services
- `Dockerfile` - Container build
- `.env` - Environment variables (not in git)

### Entry Points
- `src/app/factory.py` - FastAPI app creation
- `src/cli/serve.py` - Development server
- `src/cli/ingest.py` - Ingestion pipeline
- `frontend/src/routes/+layout.svelte` - Frontend entry

### Critical Components
- `src/rag/runtime.py` - Core RAG logic
- `src/usecases/chat.py` - Chat orchestration
- `src/ingestion/steps/chunking/core.py` - Chunking logic
- `src/evals/assessment/orchestrator.py` - Evaluation orchestration

### Largest Files (Potential Refactoring Targets)
1. `frontend/src/routes/eval/+page.svelte` - 2439 lines
2. `src/app/routes/evaluation.py` - 862 lines
3. `src/rag/runtime.py` - 816 lines
4. `src/evals/dataset_builder.py` - 622 lines
5. `src/ingestion/steps/download_web.py` - 552 lines

## Naming Conventions

### Python Modules
- **Snake case** for files: `chat_router.py`, `file_chat_history_store.py`
- **Snake case** for directories: `middleware/`, `usecases/`
- **Private modules**: Leading underscore: `_utils.py`

### Classes
- **PascalCase**: `APIKeyMiddleware`, `FileChatHistoryStore`
- **Exceptions**: `*Error` suffix: `InvalidInputError`, `StorageError`
- **Dataclasses**: Descriptive names: `RetrievalDiversityConfig`

### Functions
- **Snake case**: `stream_chat_message`, `initialize_runtime_index`
- **Private functions**: Leading underscore: `_hash_secret`
- **Async functions**: `async` prefix: `async def chat_stream_generator`

### Variables
- **Snake case**: `chat_history_store`, `vector_store`
- **Constants**: UPPER_SNAKE_CASE: `RETRIEVAL_OVERFETCH_MULTIPLIER`
- **Private**: Leading underscore: `_vector_store_initialized`

### Frontend (Svelte)
- **Files**: kebab-case for routes: `chat/+page.svelte`
- **Components**: PascalCase: `ChatInterface.svelte`
- **Exports**: Named exports preferred

### Configuration
- **Environment variables**: UPPER_SNAKE_CASE: `DASHSCOPE_API_KEY`
- **Settings**: snake_case: `dashscope_api_key`
- **CLI flags**: kebab-case: `--rate-limit-per-minute`

## File Organization Principles

### Module Structure
1. **Public API** in `__init__.py` - Clean imports
2. **Private implementation** in module files
3. **Related functionality** grouped in packages
4. **Clear separation** of layers (app → usecases → domain → infra)

### Import Guidelines
- Absolute imports from `src` package
- Avoid circular dependencies
- Type hints via `from typing import ...`
- Use `__future__.annotations` for forward references

### Test Organization
- Mirror source structure where appropriate
- Integration tests in `tests/`
- E2E tests clearly marked with `_e2e_` suffix
- Test fixtures in `conftest.py`
