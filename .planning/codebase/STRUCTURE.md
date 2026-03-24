# Codebase Structure Documentation

## Directory Layout

```
qna_medical_referenced/
├── .planning/                    # Planning and documentation
│   └── codebase/                # Architecture documentation
│       ├── ARCHITECTURE.md      # This file
│       └── STRUCTURE.md         # Codebase structure
├── data/                        # Data storage (gitignored)
│   ├── raw/                     # Downloaded source documents
│   ├── processed/               # Processed intermediate files
│   │   ├── html/               # Converted HTML files
│   │   └── pdf/                # Processed PDF metadata
│   ├── vectors/                 # ChromaDB vector store
│   ├── evals/                   # Evaluation results
│   └── evals_expanded/          # Expanded evaluation results
├── docs/                        # Project documentation
│   ├── architecture/           # Architecture diagrams
│   ├── data/                   # Data documentation
│   ├── evaluation/             # Evaluation documentation
│   ├── plans/                  # Project plans
│   ├── reports/                # Monthly reports
│   ├── superpowers/            # Superpowers plans
│   └── testing/                # Testing documentation
├── experiments/                 # Experiment configurations
│   └── v1/                     # Experiment manifests
├── frontend/                    # SvelteKit frontend
│   ├── src/
│   │   ├── lib/                # Shared utilities and components
│   │   │   ├── components/     # Svelte components
│   │   │   ├── utils/          # TypeScript utilities
│   │   │   └── types.ts        # Type definitions
│   │   └── routes/             # SvelteKit routes
│   ├── static/                 # Static assets
│   ├── tests/                  # Frontend tests (Playwright)
│   └── build/                  # Build output
├── output/                      # Test output
│   └── playwright/             # Playwright test results
├── scripts/                     # Utility scripts
│   ├── __pycache__/
│   └── manual/                 # Manual scripts
├── src/                         # Python backend source
│   ├── app/                    # FastAPI application
│   ├── cli/                    # Command-line interfaces
│   ├── config/                 # Configuration management
│   ├── evals/                  # Evaluation framework
│   ├── experiments/            # Experiment tracking
│   ├── infra/                  # Infrastructure services
│   ├── ingestion/              # Data ingestion pipeline
│   ├── rag/                    # RAG retrieval system
│   └── usecases/               # Business logic
├── tests/                       # Backend tests
│   ├── fixtures/               # Test fixtures
│   └── test_*.py               # Test files
├── wandb/                       # Weights & Biases cache
├── .env                         # Environment variables (gitignored)
├── .gitignore
├── CLAUDE.md                    # Project instructions for Claude
├── docker-compose.yml           # Docker Compose configuration
├── frontend.Dockerfile          # Frontend Docker image
├── pyproject.toml              # Python project configuration
└── uv.lock                     # Python dependency lock file
```

## Python Backend Structure (`src/`)

### `src/app/` - Application Layer

**Purpose**: FastAPI application, routing, middleware

**Key Files**:
- `factory.py` - FastAPI app factory with middleware stack
- `exceptions.py` - Custom exception classes and handlers
- `logging.py` - Logging configuration
- `security.py` - Security validation
- `session.py` - Session management

**Subdirectories**:
```
src/app/
├── middleware/                 # Request processing middleware
│   ├── auth.py                # API key authentication
│   ├── rate_limit.py          # Rate limiting
│   └── request_id.py          # Request ID tracking
├── routes/                    # API endpoints
│   ├── chat.py                # Chat endpoints
│   ├── evaluation.py          # Evaluation endpoints
│   ├── health.py              # Health check
│   └── history.py             # Chat history management
└── schemas/                   # Pydantic models
    ├── chat.py                # Chat request/response models
    └── __init__.py
```

**Naming Conventions**:
- Route files: `{resource}.py` (e.g., `chat.py`, `history.py`)
- Middleware files: `{concern}.py` (e.g., `auth.py`, `rate_limit.py`)
- Schema files: Match route name (e.g., `chat.py` for chat schemas)

### `src/cli/` - Command-Line Interfaces

**Purpose**: Development and operational CLI tools

**Files**:
- `serve.py` - Development server (auto-reload)
- `serve_production.py` - Production server
- `ingest.py` - Ingestion pipeline CLI
- `eval_pipeline.py` - Evaluation pipeline CLI
- `__init__.py`

**Naming Conventions**:
- CLI commands: `{command}.py` (e.g., `serve.py`, `ingest.py`)
- Use `verb_noun` pattern for clarity

### `src/config/` - Configuration

**Purpose**: Centralized configuration management

**Files**:
- `settings.py` - Pydantic settings with environment variable loading
- `paths.py` - Centralized path definitions
- `__init__.py`

**Key Settings Categories**:
- LLM configuration (models, API keys)
- Storage paths
- API configuration (CORS, rate limiting)
- Retrieval parameters
- Evaluation settings

### `src/evals/` - Evaluation Framework

**Purpose**: Comprehensive pipeline quality assessment

**Directory Structure**:
```
src/evals/
├── assessment/                # Assessment orchestration
│   ├── answer_eval.py        # L6 answer quality evaluation
│   ├── l6_contract.py        # L6 evaluation contract
│   ├── orchestrator.py       # End-to-end orchestration
│   ├── reporting.py          # Summary and reporting
│   ├── retrieval_eval.py     # L5 retrieval evaluation
│   └── thresholds.py         # Quality threshold evaluation
├── checks/                    # Pipeline quality checks
│   ├── l0_download.py        # Download audit
│   ├── l1_html.py            # HTML quality
│   ├── l2_pdf.py             # PDF quality
│   ├── l3_chunking.py        # Chunking quality
│   ├── l4_reference.py       # Reference data
│   ├── l5_index.py           # Index quality
│   └── shared.py             # Shared utilities
├── metrics/                   # Evaluation metrics
│   ├── _utils.py             # Metric utilities
│   └── medical.py            # Medical domain metrics
├── synthetic/                 # Synthetic data generation
│   └── generator.py          # Test case generation
├── artifacts.py              # Artifact storage
├── dataset_builder.py        # Dataset construction
├── deepeval_models.py        # DeepEval model wrappers
├── pipeline_assessment.py    # Compatibility facade
├── schemas.py                # Pydantic models
├── step_checks.py            # Step check orchestration
└── __init__.py
```

**Naming Conventions**:
- Check files: `l{stage}_{concern}.py` (e.g., `l0_download.py`, `l3_chunking.py`)
- Assessment files: `{component}_eval.py` or `{component}.py`
- Metric files: `{domain}.py` (e.g., `medical.py`)

### `src/experiments/` - Experiment Tracking

**Purpose**: Experiment configuration and W&B integration

**Files**:
- `config.py` - Experiment configuration schemas
- `wandb_tracking.py` - W&B logging integration
- `wandb_history.py` - W&B run history queries
- `__init__.py`

### `src/infra/` - Infrastructure Services

**Purpose**: External service integration and storage

**Directory Structure**:
```
src/infra/
├── llm/                       # LLM service integration
│   └── qwen_client.py        # Qwen API client
└── storage/                   # Storage implementations
    ├── interfaces.py         # Storage abstractions
    ├── file_chat_history_store.py  # File-based history
    ├── chat_history_store.py # Alias for history store
    └── __init__.py
```

**Naming Conventions**:
- LLM clients: `{model}_client.py` (e.g., `qwen_client.py`)
- Storage implementations: `{technology}_{resource}_store.py` (e.g., `file_chat_history_store.py`)
- Interfaces: `interfaces.py` or `{resource}_interface.py`

### `src/ingestion/` - Data Ingestion Pipeline

**Purpose**: Document processing from raw sources to indexed chunks

**Directory Structure**:
```
src/ingestion/
├── steps/                     # Pipeline steps (L0-L4)
│   ├── chunking/             # Chunking strategies
│   │   ├── chonkie_adapter.py      # Third-party adapter
│   │   ├── config.py               # Chunking configuration
│   │   ├── core.py                 # Core chunking logic
│   │   ├── helpers.py              # Chunking utilities
│   │   ├── qwen_embedding_wrapper.py  # Semantic chunking
│   │   ├── strategies.py           # Chunking strategies
│   │   └── __init__.py
│   ├── chunk_text.py        # L3: Chunk orchestration
│   ├── convert_html.py      # L1: HTML → Markdown
│   ├── download_pdfs.py     # L0b: PDF download
│   ├── download_web.py      # L0: Web download
│   ├── hype.py              # L3b: HyPE generation
│   ├── load_markdown.py     # L1 alt: Load Markdown
│   ├── load_pdfs.py         # L2: PDF processing
│   └── load_reference_data.py  # L4: Reference data
├── indexing/                  # L5: Indexing and search
│   ├── embedding.py          # Text embedding
│   ├── keyword_index.py      # BM25 index
│   ├── persistence.py        # JSON persistence
│   ├── search.py             # Search algorithms
│   ├── text_utils.py         # Text processing
│   └── vector_store.py       # Hybrid vector store
├── artifacts.py              # Ingestion artifacts
└── __init__.py
```

**Naming Conventions**:
- Step files: `{action}_{resource}.py` (e.g., `download_web.py`, `load_pdfs.py`)
- Indexing files: `{concern}.py` (e.g., `embedding.py`, `search.py`)
- Strategy files: `{strategy}.py` or `strategies.py`

**Pipeline Stages**:
- L0: Data acquisition (download_web, download_pdfs)
- L1: HTML processing (convert_html)
- L2: PDF processing (load_pdfs)
- L3: Chunking (chunk_text, chunking/)
- L3b: HyPE generation (hype.py)
- L4: Reference data (load_reference_data)
- L5: Indexing (indexing/)
- L6: Runtime (handled by src/rag/)

### `src/rag/` - RAG Retrieval System

**Purpose**: Retrieval-augmented generation core logic

**Files**:
- `runtime.py` - Runtime retrieval system (main entry point)
- `hyde.py` - HyDE query expansion
- `formatting.py` - Context and source formatting
- `trace_models.py` - Pipeline trace models
- `__init__.py`

**Key Functions**:
- `initialize_runtime_index()` - Lazy vector store initialization
- `retrieve_context()` - Synchronous retrieval
- `retrieve_context_with_trace()` - Detailed trace retrieval
- `retrieve_context_with_trace_async()` - Async retrieval with HyDE

### `src/usecases/` - Business Logic Layer

**Purpose**: Orchestration of business operations

**Files**:
- `chat.py` - Chat message processing
- `pipeline.py` - Offline pipeline orchestration
- `__init__.py`

**Naming Conventions**:
- Use case files: `{domain}.py` (e.g., `chat.py`, `pipeline.py`)
- Functions: `verb_noun()` (e.g., `process_chat_message()`, `run_pipeline()`)

## Frontend Structure (`frontend/`)

### `frontend/src/` - Frontend Source

**Directory Structure**:
```
frontend/src/
├── lib/                       # Shared utilities and components
│   ├── components/           # Reusable Svelte components
│   │   ├── markdown/        # Markdown rendering
│   │   │   ├── context.ts
│   │   │   ├── highlight.ts
│   │   │   └── renderers/   # Custom markdown renderers
│   │   ├── AppShell.svelte
│   │   ├── DagFlowDiagram.svelte
│   │   ├── DocumentInspector.svelte
│   │   ├── DrillDownModal.svelte
│   │   ├── EmptyState.svelte
│   │   ├── EvalSection.svelte
│   │   ├── IngestionTab.svelte
│   │   ├── LoadingSkeleton.svelte
│   │   ├── MarkdownRenderer.svelte
│   │   ├── MetricBar.svelte
│   │   ├── MetricChart.svelte
│   │   ├── MetricTile.svelte
│   │   ├── MultiSelect.svelte
│   │   ├── PipelineFlowDiagram.svelte
│   │   ├── QualityTab.svelte
│   │   ├── RetrievalTab.svelte
│   │   ├── StrategyCard.svelte
│   │   ├── TabNav.svelte
│   │   ├── ThresholdEditor.svelte
│   │   ├── TrendingTab.svelte
│   │   └── [many more]
│   └── utils/               # TypeScript utilities
│       ├── eval.ts         # Evaluation utilities
│       ├── export.ts       # Data export
│       ├── format.ts       # Formatting functions
│       ├── health-score.ts # Health score calculation
│       ├── metric-definitions.ts
│       ├── types.ts        # Type definitions
│       └── url.ts          # URL utilities
├── routes/                  # SvelteKit routes
│   ├── +layout.svelte      # Root layout
│   ├── +page.svelte        # Home page
│   ├── docs/               # Documentation routes
│   │   └── pipeline/
│   │       └── +page.svelte
│   └── eval/               # Evaluation routes
│       └── +page.svelte
├── app.d.ts                # Global type declarations
└── app.html                # HTML template
```

**Naming Conventions**:
- Components: PascalCase.svelte (e.g., `AppShell.svelte`, `MetricBar.svelte`)
- Utilities: kebab-case.ts or camelCase.ts (e.g., `health-score.ts`, `eval.ts`)
- Routes: SvelteKit conventions (+page.svelte, +layout.svelte)

**Component Organization**:
- Layout components: AppShell, TabNav
- Visualization components: PipelineFlowDiagram, MetricChart, QualityDistributionChart
- Domain-specific components: EvalSection, IngestionTab, RetrievalTab, TrendingTab
- Utility components: LoadingSkeleton, EmptyState, Tooltip

## Test Structure (`tests/`)

### Backend Tests (`tests/`)

**Purpose**: Backend testing with pytest

**Organization**:
```
tests/
├── fixtures/                # Test fixtures and data
│   └── [test data files]
├── conftest.py              # Pytest configuration
├── test_answer_eval_*.py    # Answer evaluation tests
├── test_app_*.py           # Application tests
├── test_chat_*.py          # Chat functionality tests
├── test_chunker.py         # Chunking tests
├── test_dataset_builder.py # Dataset building tests
├── test_deepeval_*.py      # DeepEval integration tests
├── test_download_*.py      # Download step tests
├── test_embedding.py       # Embedding tests
├── test_eval_*.py          # Evaluation framework tests
├── test_experiment_*.py    # Experiment configuration tests
├── test_hyde.py            # HyDE tests
├── test_ingestion_*.py     # Ingestion pipeline tests
├── test_keyword_index.py   # Keyword index tests
├── test_medical_metrics.py # Medical metric tests
├── test_orchestrator_*.py  # Orchestrator tests
├── test_pdf_loader.py      # PDF loading tests
├── test_pipeline_*.py      # Pipeline tests
├── test_retrieval.py       # Retrieval tests
├── test_runtime_*.py       # Runtime tests
├── test_settings.py        # Configuration tests
├── test_source_*.py        # Source metadata tests
├── test_storage_*.py       # Storage tests
├── test_synthetic_*.py     # Synthetic data tests
├── test_thresholds_*.py    # Threshold tests
└── test_wandb_*.py         # W&B integration tests
```

**Naming Conventions**:
- Test files: `test_{module_or_feature}.py` (e.g., `test_chat_multi_turn.py`)
- Test functions: `test_{specific_behavior}` (e.g., `test_retrieval_with_hyde`)
- Test classes: `Test{Feature}` (e.g., `TestVectorStore`)

**Test Markers**:
- `live_api`: Tests requiring live Qwen API access
- `deepeval`: DeepEval integration tests (slow, requires API)
- `e2e_real_apis`: End-to-end tests with real APIs
- `slow`: Slow tests (can be deselected with `-m "not slow"`)

### Frontend Tests (`frontend/tests/`)

**Purpose**: Frontend E2E testing with Playwright

**Organization**:
```
frontend/tests/
├── [test files].spec.ts    # Playwright test specs
└── [test utilities]
```

**Naming Conventions**:
- Test files: `{feature}.spec.ts` (e.g., `chat.spec.ts`)
- Test functions: `test {scenario}` (e.g., `test user sends message`)

## Data Structure (`data/`)

### Data Directories

```
data/
├── raw/                     # Downloaded source documents
│   └── LabQAR/             # Raw laboratory QA data
├── processed/              # Processed intermediate files
│   ├── html/               # Converted HTML files
│   └── pdf/                # Processed PDF metadata
├── vectors/                # ChromaDB vector store (persistent)
│   └── medical_docs.json   # Vector embeddings
├── evals/                  # Evaluation results
│   └── [timestamp]_[experiment_name]/
│       ├── summary.json
│       ├── step_findings.json
│       └── [artifact files]
└── evals_expanded/         # Expanded evaluation results
```

**Naming Conventions**:
- Evaluation runs: `{timestamp}_{experiment_name}/`
- Vector stores: `{collection_name}.json`
- Processed files: Preserve original structure

## Configuration Files

### Root Configuration

- `pyproject.toml` - Python project configuration (dependencies, tools)
- `uv.lock` - Python dependency lock file (generated)
- `.env` - Environment variables (gitignored)
- `.gitignore` - Git ignore rules
- `CLAUDE.md` - Project instructions for Claude Code
- `docker-compose.yml` - Docker Compose configuration

### Frontend Configuration

- `frontend/package.json` - Frontend dependencies
- `frontend/vite.config.ts` - Vite configuration
- `frontend/tsconfig.json` - TypeScript configuration
- `frontend/svelte.config.js` - Svelte configuration

### Docker Configuration

- `docker-compose.yml` - Multi-container orchestration
- `frontend.Dockerfile` - Frontend container image

## Module Organization

### Python Module Structure

```
src/
├── __init__.py
├── app/                    # FastAPI application
│   ├── __init__.py
│   ├── factory.py
│   └── ...
├── cli/                    # Command-line interfaces
│   ├── __init__.py
│   └── ...
├── config/                 # Configuration
│   ├── __init__.py
│   ├── settings.py
│   └── paths.py
├── evals/                  # Evaluation
│   ├── __init__.py
│   └── ...
├── experiments/            # Experiments
│   ├── __init__.py
│   └── ...
├── infra/                  # Infrastructure
│   ├── __init__.py
│   └── ...
├── ingestion/              # Ingestion pipeline
│   ├── __init__.py
│   └── ...
├── rag/                    # RAG system
│   ├── __init__.py
│   └── ...
└── usecases/               # Business logic
    ├── __init__.py
    └── ...
```

**Import Patterns**:
```python
# From anywhere in the application
from src.config import settings
from src.rag import retrieve_context, initialize_runtime_index
from src.infra.llm import get_client
from src.infra.storage import FileChatHistoryStore
from src.usecases.chat import process_chat_message
```

### Frontend Module Structure

```
frontend/src/
├── lib/                    # Shared code
│   ├── components/         # Reusable components
│   └── utils/             # Utilities
└── routes/                # Page routes
```

**Import Patterns**:
```typescript
// Component imports
import MetricBar from '$lib/components/MetricBar.svelte';

// Utility imports
import { calculateHealthScore } from '$lib/utils/health-score';
import type { PipelineTrace } from '$lib/types';
```

## Naming Conventions Summary

### Python Files
- **Modules**: `snake_case.py` (e.g., `chat.py`, `vector_store.py`)
- **Tests**: `test_{module}.py` (e.g., `test_chat.py`)
- **Packages**: Directory with `__init__.py`

### Python Code
- **Functions**: `snake_case` (e.g., `retrieve_context()`)
- **Classes**: `PascalCase` (e.g., `VectorStore`, `QwenClient`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)
- **Private**: `_leading_underscore` (e.g., `_internal_function()`)

### Frontend Files
- **Components**: `PascalCase.svelte` (e.g., `AppShell.svelte`)
- **Utilities**: `kebab-case.ts` or `camelCase.ts` (e.g., `health-score.ts`)
- **Routes**: SvelteKit conventions (`+page.svelte`, `+layout.svelte`)

### Frontend Code
- **Components**: `PascalCase` (e.g., `MetricBar`)
- **Functions**: `camelCase` (e.g., `calculateHealthScore()`)
- **Types**: `PascalCase` (e.g., `PipelineTrace`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)

### Directories
- **Python packages**: `snake_case` (e.g., `src/ingestion/`)
- **Frontend**: `kebab-case` or `camelCase` (e.g., `lib/utils/`)

## Important File Locations

### Configuration
- `src/config/settings.py` - All application settings
- `.env` - Environment variables (not in git)
- `pyproject.toml` - Python dependencies and tooling

### Entry Points
- `src/app/factory.py` - FastAPI application factory
- `src/cli/serve.py` - Development server
- `src/usecases/chat.py` - Chat business logic
- `src/usecases/pipeline.py` - Pipeline orchestration
- `src/rag/runtime.py` - RAG runtime system

### Key Components
- `src/rag/runtime.py` - Retrieval system
- `src/ingestion/indexing/vector_store.py` - Vector store
- `src/infra/llm/qwen_client.py` - LLM client
- `src/infra/storage/file_chat_history_store.py` - Chat history

### Evaluation
- `src/evals/assessment/orchestrator.py` - Evaluation orchestration
- `src/evals/pipeline_assessment.py` - Assessment facade
- `tests/test_pipeline_assessment_smoke.py` - E2E test

### Data
- `data/raw/` - Downloaded documents
- `data/processed/` - Processed files
- `data/vectors/` - Vector store
- `data/evals/` - Evaluation results

### Frontend
- `frontend/src/routes/+page.svelte` - Main dashboard
- `frontend/src/lib/components/` - Reusable components
- `frontend/src/lib/utils/types.ts` - Type definitions

## File Naming Patterns

### Python Modules by Layer
- **Application**: `{feature}.py` (e.g., `chat.py`, `health.py`)
- **Use Cases**: `{domain}.py` (e.g., `chat.py`, `pipeline.py`)
- **RAG**: `{concern}.py` (e.g., `runtime.py`, `hyde.py`)
- **Ingestion Steps**: `{verb}_{noun}.py` (e.g., `download_web.py`, `load_pdfs.py`)
- **Infrastructure**: `{service}_{type}.py` (e.g., `qwen_client.py`, `file_chat_history_store.py`)
- **Evaluation**: `{component}_eval.py` or `l{stage}_{concern}.py`

### Test Files
- **Unit Tests**: `test_{module}.py`
- **Integration Tests**: `test_{feature}_e2e.py`
- **API Tests**: `test_{route}_routes.py`

### Frontend Components
- **Layout**: `AppShell.svelte`, `Nav.svelte`
- **Features**: `{Feature}Tab.svelte`, `{Feature}Section.svelte`
- **Visualizations**: `{Type}Chart.svelte`, `{Type}Diagram.svelte`
- **Utilities**: `{utility}.svelte` (e.g., `LoadingSkeleton.svelte`)

## Module Dependencies

### Dependency Flow
```
CLI → App → Use Cases → RAG + Infra
                    ↓
              Ingestion → Config
                    ↓
                 Indexing
```

### Import Guidelines
- **No circular imports**: Use dependency injection or lazy imports
- **Abstractions over implementations**: Import from interfaces, not concrete classes
- **Configuration**: Always import from `src.config.settings`, not direct env access
- **Logging**: Use standard logging, not print statements

## Testing Conventions

### Test Organization
- **Unit tests**: Test individual functions/classes in isolation
- **Integration tests**: Test multiple components together
- **E2E tests**: Test full workflows (marked with `e2e_real_apis`)
- **Smoke tests**: Quick sanity checks (e.g., `test_pipeline_assessment_smoke.py`)

### Test Naming
```python
def test_{specific_behavior}():
    """Test that {expected outcome} when {conditions}."""
    pass

class Test{Feature}:
    def test_{scenario}(self):
        """Test {scenario}."""
        pass
```

### Fixture Conventions
```python
# In conftest.py
@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    pass

@pytest.fixture
def sample_vector_store():
    """Sample vector store with test data."""
    pass
```

## Documentation Conventions

### Docstrings
- **Modules**: Describe module purpose and usage
- **Classes**: Describe class purpose and key methods
- **Functions**: Describe parameters, return values, and side effects
- **Format**: Google-style docstrings (preferred)

### Comments
- **Why, not what**: Explain reasoning, not obvious code
- **TODO**: Mark future work with `TODO:` prefix
- **FIXME**: Mark broken code with `FIXME:` prefix
- **XXX**: Mark tricky code with `XXX:` prefix

## Code Quality Tools

### Python
- **Ruff**: Linting and formatting (`ruff check`, `ruff format`)
- **MyPy**: Type checking (`mypy src/`)
- **Pytest**: Test runner (`pytest`)

### Frontend
- **ESLint**: Linting (configured in package.json)
- **Prettier**: Formatting (configured in package.json)
- **Playwright**: E2E testing (`npm run e2e`)
- **Vite**: Build tool and dev server

### CI/CD
- **Pre-commit hooks**: Run linters before commits
- **Docker**: Containerized development and deployment
- **GitHub Actions**: CI/CD pipeline (if configured)

## Git Conventions

### Commit Messages
- **Format**: `{type}: {description}`
- **Types**: feat, fix, docs, test, refactor, chore
- **Examples**:
  - `feat: add HyDE query expansion`
  - `fix: handle empty vector store`
  - `test: add retrieval quality tests`

### Branch Naming
- **Features**: `feat/{feature-name}`
- **Fixes**: `fix/{issue-description}`
- **Experiments**: `exp/{experiment-name}`

## Deployment Structure

### Docker
- **Backend**: Single container with Python runtime
- **Frontend**: Separate container with Node.js runtime
- **Volumes**: Mount data directories for persistence

### Environment-Specific
- **Development**: Hot reload, debug logging
- **Production**: Optimized builds, structured logging
- **Testing**: Isolated test environment

## Migration Paths

### Adding New Features
1. Create use case in `src/usecases/`
2. Add route in `src/app/routes/`
3. Add schema in `src/app/schemas/`
4. Add tests in `tests/`
5. Update frontend if needed

### Adding New Evaluation Metrics
1. Create metric in `src/evals/metrics/`
2. Register in assessment contract
3. Add threshold evaluation
4. Add tests
5. Update frontend visualization

### Adding New Ingestion Steps
1. Create step in `src/ingestion/steps/`
2. Add quality check in `src/evals/checks/`
3. Update pipeline orchestration
4. Add tests
5. Update documentation
