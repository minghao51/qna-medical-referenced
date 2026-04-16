# Directory Structure Analysis - QnA Medical Referenced System

## Project Layout

```
qna_medical_referenced/
├── .planning/codebase/     # Generated documentation
├── src/                    # Backend source code
├── frontend/               # Frontend source code
├── tests/                  # Test files
├── data/                   # Data files and datasets
├── docs/                   # Documentation
├── scripts/                # Utility scripts
├── wandb/                  # Weights & Biases logs
├── .venv/                  # Virtual environment
├── .git/                   # Git repository
├── .env                    # Environment variables
├── pyproject.toml          # Python project configuration
├── docker-compose.yml      # Docker Compose configuration
└── README.md              # Project documentation
```

## Backend Source Structure (`src/`)

### Core Application Layer (`src/app/`)
```
src/app/
├── __init__.py            # Package initialization
├── factory.py             # FastAPI application factory (ENTRY POINT)
├── exceptions.py          # Custom exception handlers
├── logging.py             # Logging configuration
├── security.py            # Security utilities
├── session.py             # Session management
├── middleware/            # Request middleware
│   ├── __init__.py
│   ├── auth.py            # Authentication middleware
│   ├── rate_limit.py     # Rate limiting
│   └── request_id.py      # Request ID tracking
├── routes/                # API route handlers
│   ├── __init__.py
│   ├── chat.py           # Chat endpoints
│   ├── evaluation.py     # Evaluation endpoints
│   ├── health.py         # Health check endpoints
│   └── history.py        # Chat history endpoints
├── schemas/               # Data validation schemas
│   ├── __init__.py
│   └── chat.py           # Chat-related schemas
```

### Business Logic Layer (`src/usecases/`)
```
src/usecases/
├── __init__.py
├── chat.py               # Chat interaction use case
└── pipeline.py          # Evaluation pipeline use case
```

### Domain Layer (`src/rag/`)
```
src/rag/
├── __init__.py
├── formatting.py         # Response formatting utilities
├── hyde.py              # Hypothetical Document Embedding
├── medical_expansion.py # Medical domain context expansion
├── production_profile.py # Production deployment profiles
├── reranker.py          # Re-ranking algorithms
├── runtime.py           # Runtime vector index management
└── trace_models.py      # Tracing and logging models
```

### Infrastructure Layer (`src/infra/`)
```
src/infra/
├── di/                  # Dependency Injection
│   ├── __init__.py
│   ├── container.py     # DI container
│   └── providers.py     # Service providers
├── storage/             # Storage abstractions
│   ├── __init__.py
│   ├── base.py          # Base storage interface
│   └── file.py          # File-based storage implementation
├── llm/                 # LLM service adapters
│   ├── __init__.py
│   ├── base.py          # Base LLM interface
│   ├── openai.py        # OpenAI adapter
│   └── qwen.py          # Qwen adapter
└── vectorstore/         # Vector store implementations
    ├── __init__.py
    ├── chroma.py        # ChromaDB implementation
    └── base.py          # Base vector store interface
```

### Data Processing (`src/ingestion/`)
```
src/ingestion/
├── __init__.py
├── index.py            # Main ingestion script
├── steps/              # Pipeline steps
│   ├── __init__.py
│   ├── chunking/       # Document chunking strategies
│   │   ├── __init__.py
│   │   ├── semantic_chunker.py
│   │   ├── recursive_chunker.py
│   │   └── config.py
│   └── extraction/     # Content extraction
│       ├── __init__.py
│       ├── html.py     # HTML extraction
│       └── pdf.py       # PDF extraction
└── indexing/           # Indexing pipeline
    ├── __init__.py
    ├── chroma_store.py # ChromaDB vector store
    ├── embedding.py    # Embedding generation
    ├── keyword_index.py # Keyword index
    ├── migrate.py       # Index migration
    ├── persistence.py   # Index persistence
    ├── search.py        # Search functionality
    ├── text_utils.py    # Text utilities
    └── vector_store.py  # Vector store abstraction
```

### Evaluation System (`src/evals/`)
```
src/evals/
├── __init__.py
├── artifacts.py        # Evaluation artifacts
└── assessment/         # Evaluation assessment
    ├── __init__.py
    ├── answer_eval.py   # Answer evaluation
    ├── l6_contract.py   # L6 evaluation contract
    ├── orchestrator.py  # Evaluation orchestrator
    ├── reporting.py     # Evaluation reporting
    ├── retrieval_eval.py # Retrieval evaluation
    └── thresholds.py    # Evaluation thresholds
└── checks/             # Data validation checks
    ├── __init__.py
    ├── l0_download.py   # Download validation
    ├── l1_html.py      # HTML validation
    ├── l2_pdf.py       # PDF validation
    ├── l3_parse.py     # Parse validation
    ├── l4_chunk.py     # Chunk validation
    ├── l5_index.py     # Index validation
    └── l6_eval.py      # Evaluation validation
```

### Configuration (`src/config/`)
```
src/config/
├── __init__.py
├── context.py          # Configuration context
├── paths.py            # File path management
└── settings.py         # Application settings
```

### Command Line Interface (`src/cli/`)
```
src/cli/
├── __init__.py
├── eval_pipeline.py    # Evaluation CLI
├── ingest.py           # Data ingestion CLI
├── serve.py            # Development server
└── serve_production.py # Production server
```

## Frontend Structure (`frontend/`)

### Core Application
```
frontend/
├── src/
│   ├── app.html        # Root HTML template (ENTRY POINT)
│   ├── app.d.ts        # TypeScript definitions
│   ├── routes/         # File-based routing
│   │   ├── +layout.svelte  # Root layout
│   │   ├── +page.svelte    # Home page
│   │   ├── docs/
│   │   │   └── pipeline/
│   │   │       └── +page.svelte
│   │   └── eval/
│   │       ├── +page.svelte
│   │       └── ablation/
│   │           └── +page.svelte
│   └── lib/
│       ├── components/  # Svelte components
│       │   ├── AppNav.svelte
│       │   ├── AppShell.svelte
│       │   ├── CategoryBreakdownChart.svelte
│       │   ├── ConfidenceBadge.svelte
│       │   ├── DagFlowDiagram.svelte
│       │   ├── DocumentInspector.svelte
│       │   ├── DrillDownModal.svelte
│       │   ├── EmptyState.svelte
│       │   ├── EvalSection.svelte
│       │   ├── FlowNode.svelte
│       │   ├── HealthScoreBadge.svelte
│       │   ├── IngestionTab.svelte
│       │   ├── LoadingSkeleton.svelte
│       │   ├── MarkdownRenderer.svelte
│       │   ├── MetricBar.svelte
│       │   ├── MetricChart.svelte
│       │   ├── MetricTile.svelte
│       │   ├── MultiSelect.svelte
│       │   ├── PipelineFlowDiagram.svelte
│       │   ├── PipelinePanel.svelte
│       │   ├── QualityDistributionChart.svelte
│       │   ├── QualityTab.svelte
│       │   ├── RetrievalTab.svelte
│       │   ├── SourceDistributionChart.svelte
│       │   ├── SourceQualityIndicator.svelte
│       │   ├── StepCard.svelte
│       │   ├── StrategyCard.svelte
│       │   ├── TabNav.svelte
│       │   ├── ThresholdEditor.svelte
│       │   ├── Tooltip.svelte
│       │   └── TrendingTab.svelte
│       │   └── markdown/
│       │       ├── context.ts
│       │       ├── highlight.ts
│       │       └── renderers/
│       │           ├── CodeBlockRenderer.svelte
│       │           ├── HtmlRenderer.svelte
│       │           └── LinkRenderer.svelte
│       ├── styles/
│       │   └── markdown.css
│       ├── types.ts     # TypeScript type definitions
│       └── utils/       # Utility functions
│           ├── api.ts
│           ├── eval.ts
│           ├── export.ts
│           ├── format.ts
│           ├── health-score.ts
│           ├── metric-definitions.ts
│           └── url.ts
│
├── static/              # Static assets
├── build/               # Build output
├── node_modules/        # Dependencies
├── svelte.config.js     # SvelteKit configuration
├── package.json         # NPM dependencies
└── vite.config.js       # Vite configuration
```

## Key Locations

### Entry Points
- **Backend**: `src/app/factory.py` - FastAPI application factory
- **Frontend**: `frontend/src/app.html` - Root HTML template

### Configuration
- **Backend Settings**: `src/config/settings.py`
- **Environment**: `.env` file
- **Frontend Config**: `frontend/svelte.config.js`

### Data Flow Components
- **RAG System**: `src/rag/`
- **Evaluation Pipeline**: `src/evals/`
- **Data Ingestion**: `src/ingestion/`

### API Routes
- **Chat**: `src/app/routes/chat.py`
- **Evaluation**: `src/app/routes/evaluation.py`
- **Health Check**: `src/app/routes/health.py`
- **History**: `src/app/routes/history.py`

## Naming Conventions

### Python Backend
- **Snake Case** for all Python files and functions
- **Pascal Case** for classes and exceptions
- **Private members** prefixed with underscore
- **Type hints** used throughout
- **Docstrings** following Google style

### TypeScript/Svelte Frontend
- **Pascal Case** for component filenames (e.g., `AppShell.svelte`)
- **Pascal Case** for class/type names
- **camelCase** for function and variable names
- **kebab-case** for CSS classes
- **Svelte-specific** syntax for reactive declarations

### File Organization
- **Feature-based** grouping in backend
- **Component-based** grouping in frontend
- **Clear separation** between layers (app, usecases, domain, infra)
- **Consistent directory** structure across modules

## Build and Deployment

### Backend Build
- **Package management**: `pyproject.toml` + `uv.lock`
- **Environment**: `.env` file with all configurations
- **Docker**: `Dockerfile` and `docker-compose.yml`
- **Virtualenv**: `.venv/` directory

### Frontend Build
- **Build tool**: Vite (via SvelteKit)
- **Package manager**: NPM
- **Output**: `build/` directory with static assets
- **Development**: Hot reload on changes

## Testing Structure

```
tests/
├── __init__.py
├── test_app_security.py
├── test_chat_sources.py
├── test_chat_multi_turn.py
└── [additional test files...]
```
