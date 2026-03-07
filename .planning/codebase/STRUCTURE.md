# STRUCTURE.md - Directory Layout, Key Locations

## Project Root

```
qna_medical_referenced/
├── .planning/codebase/     # Documentation (generated)
├── data/                   # Data storage
│   ├── raw/               # Raw source files (HTML, PDF, CSV)
│   ├── vectors/           # Vector store (JSON)
│   ├── chat_history.json  # Chat sessions
│   └── rate_limits.db     # SQLite rate limits
├── src/                   # Backend source code
├── frontend/              # Frontend (SvelteKit)
├── tests/                 # Backend tests
├── docs/                  # Project documentation
├── docker-compose.yml     # Container orchestration
├── pyproject.toml         # Python dependencies
└── README.md              # Project overview
```

## Backend Structure (`src/`)

```
src/
├── app/                    # HTTP layer
│   ├── factory.py         # FastAPI app creation + lifespan wiring
│   ├── routes/            # Route handlers by endpoint area
│   │   ├── chat.py        # POST /chat endpoint
│   │   ├── history.py     # GET/DELETE /history/{session_id}
│   │   ├── health.py      # GET /health endpoint
│   │   └── evaluation.py  # GET /evaluation endpoints
│   ├── schemas/           # Request/response models for HTTP APIs
│   │   └── chat.py        # Chat request/response models
│   └── middleware/        # API key, rate limit, request id middleware
│       ├── auth.py        # API key authentication
│       ├── rate_limit.py  # Rate limiting (SQLite)
│       └── request_id.py  # Request ID middleware
├── usecases/              # Orchestration / business flows
│   └── chat.py            # chat request -> retrieve -> generate -> persist
├── rag/                   # Runtime retrieval path
│   ├── runtime.py         # index init + retrieve_context(+trace)
│   ├── trace_models.py    # response trace models
│   └── formatting.py      # source/context formatting helpers
├── ingestion/             # Offline pipeline + indexing internals
│   ├── pipeline.py        # end-to-end ingestion orchestration
│   ├── steps/             # download/convert/load/chunk/reference steps
│   │   ├── download_web.py     # Web content download
│   │   ├── download_pdfs.py    # PDF download
│   │   ├── convert_html.py     # HTML → Markdown
│   │   ├── load_pdfs.py        # PDF parsing
│   │   ├── load_markdown.py    # Markdown loading
│   │   ├── load_reference_data.py  # Reference data loading
│   │   └── chunk_text.py       # Text chunking
│   └── indexing/          # vector store + embedding/search/persistence helpers
│       ├── vector_store.py     # Vector embeddings
│       ├── embedding.py        # Embedding generation
│       ├── keyword_index.py    # Keyword search index
│       ├── search.py           # Search functionality
│       ├── persistence.py      # Index persistence
│       └── text_utils.py       # Text utilities
├── infra/                 # External systems/infrastructure adapters
│   ├── llm/
│   │   ├── qwen_client.py  # Qwen LLM client (Alibaba Dashscope)
│   │   └── gemini_client.py # Gemini LLM client (legacy, unused)
│   └── storage/
│       └── chat_history_store.py  # Chat history (JSON file)
├── config/                # Settings and path ownership
│   ├── settings.py        # Configuration (Pydantic Settings)
│   └── paths.py           # Filesystem path configuration
├── cli/                   # Canonical command entrypoints
│   ├── serve.py           # Server startup
│   ├── ingest.py          # Ingestion pipeline runner
│   └── eval_pipeline.py   # Evaluation pipeline
└── evals/                 # Evaluation and metrics system
    ├── pipeline_assessment.py  # Pipeline quality assessment
    ├── llm_judges.py          # LLM-based evaluation
    ├── metrics.py             # Evaluation metrics
    ├── dataset_builder.py     # Test dataset generation
    ├── step_checks.py         # Pipeline step validation
    └── artifacts.py           # Evaluation artifacts
```

## Frontend Structure (`frontend/`)

```
frontend/
├── src/
│   ├── app.html              # HTML template
│   ├── app.d.ts               # Type declarations
│   ├── lib/
│   │   ├── index.ts           # Library exports
│   │   ├── types.ts           # TypeScript types
│   │   ├── utils/health-score.ts  # Client-side confidence scoring
│   │   ├── utils/
│   │   │   ├── health-score.ts  # Health score calculations
│   │   │   └── export.ts         # Export functionality
│   │   └── components/
│   │       ├── PipelinePanel.svelte     # Pipeline trace display
│   │       ├── StepCard.svelte          # Step card component
│   │       ├── ConfidenceBadge.svelte   # Confidence level badges
│   │       ├── MetricBar.svelte         # Progress bars
│   │       ├── SourceQualityIndicator.svelte  # Domain credibility badges
│   │       ├── DocumentInspector.svelte        # Full document modal
│   │       ├── PipelineFlowDiagram.svelte      # Animated pipeline visualization
│   │       ├── MetricChart.svelte              # Chart.js wrapper
│   │       ├── FlowNode.svelte                 # Pipeline stage node
│   │       ├── LoadingSkeleton.svelte          # Loading states
│   │       ├── HealthScoreBadge.svelte         # Health score display
│   │       ├── QualityDistributionChart.svelte # Quality metrics
│   │       ├── SourceDistributionChart.svelte  # Source analytics
│   │       ├── MultiSelect.svelte              # Multi-select dropdown
│   │       ├── ThresholdEditor.svelte          # Threshold configuration
│   │       └── DrillDownModal.svelte           # Detailed drill-down view
│   └── routes/
│       ├── +layout.svelte     # Layout component
│       ├── +page.svelte       # Main chat page
│       └── eval/
│           └── +page.svelte   # Evaluation dashboard
├── tests/
│   ├── chat.spec.ts           # Chat E2E tests
│   └── pipeline.spec.ts       # Pipeline E2E tests
├── package.json
├── svelte.config.js
├── vite.config.ts
├── tsconfig.json
└── Dockerfile
```

## Key Locations

| Purpose | Location |
|---------|----------|
| API endpoints | `src/app/routes/` |
| LLM client | `src/infra/llm/qwen_client.py` |
| Vector store | `src/ingestion/indexing/vector_store.py` |
| RAG runtime | `src/rag/runtime.py` |
| Pipeline runner | `src/ingestion/pipeline.py` |
| Chat storage | `src/infra/storage/chat_history_store.py` |
| Config | `src/config/settings.py` |
| Paths | `src/config/paths.py` |
| Frontend entry | `frontend/src/routes/+page.svelte` |

## Data Locations

| Data | Location |
|------|----------|
| Raw HTML/PDF | `data/raw/*.html`, `data/raw/*.pdf` |
| Vector index | `data/vectors/medical_docs.json` |
| Chat history | `data/chat_history.json` |
| Rate limits | `data/rate_limits.db` |
| Reference ranges | `data/raw/LabQAR/reference_ranges.csv` |
| Evaluation results | `data/evals/` |

## Test Locations

| Tests | Location |
|-------|----------|
| Backend unit tests | `tests/test_*.py` |
| Frontend E2E | `frontend/tests/*.spec.ts` |
| Test fixtures | `tests/fixtures/` |

## Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Python dependencies, pytest, ruff config |
| `frontend/package.json` | Node dependencies |
| `docker-compose.yml` | Multi-container setup |
| `.env.example` | Environment template |
| `.gitignore` | Git ignore rules |

## Canonical Commands

### Development
```bash
# Backend
uv run python -m src.cli.serve

# Ingestion
uv run python -m src.cli.ingest

# Evaluation
uv run python -m src.cli.eval_pipeline

# Frontend
cd frontend && bun run dev
```

### Docker
```bash
docker-compose up          # Start all services
docker-compose up --build  # Rebuild and start
docker-compose down        # Stop services
```

## Runtime vs Offline Responsibilities

### Runtime (`src/app`, `src/usecases`, `src/rag`, `src/infra/llm`, `src/infra/storage`)
Used when serving `/chat` requests.

Flow:
1. `src.app.routes.chat` receives the request
2. `src.usecases.chat.process_chat_message` orchestrates retrieval + generation + history persistence
3. `src.rag.runtime` retrieves context from the vector store
4. `src.infra.llm.qwen_client.QwenClient` generates the answer
5. `src.infra.storage.chat_history_store` stores conversation history

### Offline ingestion (`src/ingestion`)
Used when preparing/refreshing the corpus and vector index.

Flow:
1. `src.ingestion.steps.download_web` (optional web downloads)
2. `src.ingestion.steps.convert_html` (HTML -> Markdown)
3. `src.ingestion.steps.load_pdfs`
4. `src.ingestion.steps.chunk_text`
5. `src.ingestion.steps.load_reference_data`
6. `src.ingestion.indexing.vector_store` (embedding + persistence)
7. `src.rag.runtime.initialize_runtime_index()` confirms runtime index availability
