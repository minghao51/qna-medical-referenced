# Codebase Structure

## Top-Level Directory Layout

```
qna_medical_referenced/
├── src/                    # Python source code
│   ├── app/               # HTTP layer (FastAPI)
│   ├── usecases/          # Business logic orchestration
│   ├── rag/               # Runtime RAG implementation
│   ├── ingestion/         # Offline data pipeline
│   ├── infra/             # External integrations
│   ├── config/            # Configuration management
│   ├── cli/               # Command-line entry points
│   └── evals/             # Evaluation system
├── frontend/              # SvelteKit application
│   ├── src/
│   │   ├── routes/       # SvelteKit routes
│   │   ├── lib/          # Shared utilities
│   │   └── components/   # Reusable components
│   ├── static/           # Static assets
│   └── tests/            # Frontend tests
├── data/                 # Runtime data storage
│   ├── documents/        # Indexed documents
│   ├── vectors/          # Vector embeddings
│   └── chat_history/     # Conversation history
├── docs/                 # Documentation
├── tests/                # Backend test suite
├── scripts/              # Utility scripts
├── .planning/            # Planning documentation
└── pyproject.toml        # Python dependencies
```

## Source Code Structure (`src/`)

### HTTP Layer (`src/app/`)
```
app/
├── factory.py           # FastAPI app factory
├── routes/             # API endpoints
│   ├── chat.py         # Chat completion endpoint
│   ├── ingest.py       # Ingestion management
│   └── eval_routes.py  # Evaluation endpoints
└── schemas/            # Pydantic models
    ├── chat.py         # Chat request/response schemas
    └── common.py       # Shared schemas
```

### Business Logic (`src/usecases/`)
```
usecases/
└── chat.py             # Chat use case orchestration
```

### RAG Implementation (`src/rag/`)
```
rag/
├── runtime.py          # RAG runtime engine
├── formatting.py       # Response formatting
└── trace_models.py     # Pipeline tracing models
```

### Ingestion Pipeline (`src/ingestion/`)
```
ingestion/
├── steps/             # Processing steps
│   ├── download_web.py    # Web content download
│   ├── convert_html.py    # HTML to markdown
│   ├── load_pdfs.py       # PDF loading
│   ├── load_markdown.py   # Markdown loading
│   └── chunk_text.py      # Text chunking
└── indexing/           # Indexing and search
    ├── embedding.py       # Embedding generation
    ├── vector_store.py    # Vector search
    └── persistence.py     # Storage management
```

### Infrastructure (`src/infra/`)
```
infra/
└── llm/               # LLM clients
    ├── dashscope.py   # Alibaba Dashscope client
    └── base.py        # Base LLM interface
```

### Configuration (`src/config/`)
```
config/
├── settings.py        # Application settings
└── paths.py           # Path configuration
```

### CLI Entry Points (`src/cli/`)
```
cli/
├── serve.py           # Start HTTP server
├── ingest.py          # Run ingestion pipeline
└── eval_pipeline.py   # Run evaluation
```

### Evaluation System (`src/evals/`)
```
evals/
├── pipeline_assessment.py  # Main evaluation framework
├── step_checks.py          # Pipeline step validation
├── schemas.py              # Evaluation schemas
├── metrics/                # Metric implementations
│   ├── retrieval.py        # Retrieval metrics
│   └── ranking.py          # Ranking metrics
└── artifacts/              # Artifact management
```

## Frontend Structure (`frontend/`)

```
frontend/
├── src/
│   ├── routes/        # SvelteKit routes
│   │   +page.svelte       # Main chat interface
│   │   +layout.ts         # Root layout
│   │   └── +server.ts     # Server endpoints
│   ├── lib/           # Utilities
│   │   └── components/    # Reusable components
├── static/           # Static assets
├── tests/            # Playwright tests
│   ├── chat.spec.ts
│   └── setup.ts
└── package.json      # Dependencies
```

## Test Structure (`tests/`)

```
tests/
├── conftest.py                    # Shared fixtures
├── test_settings.py               # Configuration tests
├── test_eval_metrics.py           # Metric tests
├── test_chunker.py                # Chunking tests
├── test_embedding.py              # Embedding tests
├── test_retrieval.py              # Retrieval tests
├── test_eval_artifacts.py         # Artifact tests
├── test_pipeline_assessment_smoke.py  # Integration tests
├── test_eval_pipeline_cli.py      # CLI tests
└── test_runtime_index_initialization.py  # Index tests
```

## Naming Conventions

### Files
- **Python modules**: `snake_case.py`
- **Test files**: `test_*.py`
- **Svelte components**: `*.svelte`
- **TypeScript files**: `*.ts`

### Directories
- **Source code**: `src/`
- **Tests**: Mirror source structure under `tests/`
- **Documentation**: `docs/`
- **Data**: `data/`

### Imports
- **Absolute imports preferred**: `from src.config import settings`
- **Third-party**: After standard library
- **Local**: Organized by module

## Key Locations

| Purpose | Location |
|---------|----------|
| Main server entry point | `src/cli/serve.py` |
| Chat endpoint | `src/app/routes/chat.py` |
| RAG runtime | `src/rag/runtime.py` |
| Vector store | `src/ingestion/indexing/vector_store.py` |
| Settings | `src/config/settings.py` |
| Frontend main page | `frontend/src/routes/+page.svelte` |
| Evaluation framework | `src/evals/pipeline_assessment.py` |
| LLM client | `src/infra/llm/dashscope.py` |
