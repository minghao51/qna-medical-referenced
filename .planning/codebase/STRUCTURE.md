# Directory Structure

## Root Layout
```
qna_medical_referenced/
├── src/                    # Backend source code
├── frontend/               # SvelteKit frontend
├── tests/                  # Python test suite
├── experiments/            # Experiment configurations
├── scripts/                # Utility scripts
├── docs/                   # Documentation
├── docker-compose.yml      # Container orchestration
├── pyproject.toml         # Python dependencies
└── .env.example           # Environment template
```

## Backend Structure (`src/`)

```
src/
├── app/                    # FastAPI application layer
│   ├── factory.py         # App factory
│   ├── routes/            # API endpoints
│   │   ├── chat.py        # Chat endpoints
│   │   ├── evaluation.py  # Evaluation endpoints
│   │   └── health.py      # Health check
│   └── schemas/           # Pydantic models
│
├── cli/                    # CLI entry points
│   ├── serve.py           # Start server
│   ├── ingest.py          # Document ingestion
│   └── eval_pipeline.py   # Evaluation pipeline
│
├── config/                 # Configuration
│   ├── settings.py        # Pydantic settings
│   └── paths.py           # Path management
│
├── evals/                  # Evaluation system
│   ├── assessment/        # Quality assessment
│   │   └── orchestrator.py
│   ├── artifacts.py       # Evaluation artifacts
│   └── dataset_builder.py # Test dataset builder
│
├── infra/                  # Infrastructure layer
│   ├── llm/               # LLM clients
│   │   └── qwen_client.py
│   └── storage/           # Storage backends
│       └── file_chat_history_store.py
│
├── ingestion/              # Document processing
│   ├── chunkers.py        # Text chunking strategies
│   └── pipeline.py        # Ingestion pipeline
│
├── rag/                    # RAG core
│   └── runtime.py         # Retrieval runtime
│
├── usecases/               # Application orchestration
│   ├── chat.py            # Chat use case
│   └── evaluation.py      # Evaluation use case
│
└── experiments/            # Experiment tracking
    ├── wandb_tracking.py  # W&B integration
    └── config.py          # Experiment config
```

## Frontend Structure (`frontend/`)

```
frontend/
├── src/
│   ├── routes/            # SvelteKit routes
│   │   ├── +page.svelte           # Chat interface
│   │   └── eval/
│   │       └── +page.svelte       # Evaluation dashboard
│   │
│   ├── lib/
│   │   ├── components/     # UI components
│   │   └── utils/          # Utility functions
│   │   └── types.ts        # TypeScript interfaces
│   │
│   └── app.css            # Global styles
│
├── package.json           # Dependencies
├── tsconfig.json          # TypeScript config
└── vite.config.ts         # Vite build config
```

## Test Structure (`tests/`)

```
tests/
├── test_answer_eval_*.py     # Evaluation tests
├── test_chat_*.py            # Chat functionality tests
├── test_dataset_builder.py   # Dataset builder tests
├── test_eval_pipeline_*.py   # Pipeline tests
├── test_experiment_config.py # Config tests
├── test_medical_metrics.py   # Domain metrics tests
├── test_orchestrator_*.py    # Orchestrator tests
├── test_pipeline_*.py        # Pipeline integration tests
├── test_synthetic_generator.py # Data generation tests
└── test_wandb_tracking.py    # W&B integration tests
```

## Key Files

### Configuration
- `src/config/settings.py` - Centralized Pydantic settings
- `.env.example` - Environment variable template

### Core Logic
- `src/usecases/chat.py` - Chat orchestration
- `src/rag/runtime.py` - RAG retrieval logic
- `src/evals/assessment/orchestrator.py` - Evaluation orchestration

### API Routes
- `src/app/routes/chat.py` - Chat endpoints
- `src/app/routes/evaluation.py` - Evaluation endpoints
- `src/app/routes/health.py` - Health check

### Frontend Types
- `frontend/src/lib/types.ts` - TypeScript interfaces

## Naming Conventions
- **Python**: `snake_case` for files and functions
- **TypeScript/Svelte**: `camelCase` for files, `PascalCase` for components
- **Tests**: `test_*.py` prefix
- **Config**: `*.yaml` for experiments, `.env` for environment
