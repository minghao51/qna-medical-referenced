# Project Structure

## Directory Tree

```
qna_medical_referenced/
├── .claude/                          # Claude Code configuration
├── .context7/                        # Context7 documentation cache
├── .deepeval/                        # DeepEval telemetry/config
├── .env                              # Local environment variables (secrets)
├── .env.example                      # Template for required env vars
├── .env.keys                         # API key configuration
├── .github/                          # GitHub Actions CI/CD
│   └── workflows/
│       ├── ci.yml                    # Lint, test, build, Docker
│       └── docs-consistency.yml      # Doc integrity checks
├── .planning/                        # Architecture docs (this file)
│   └── codebase/                     # Codebase documentation
│       ├── ARCHITECTURE.md
│       ├── CONCERNS.md
│       ├── CONVENTIONS.md
│       ├── INTEGRATIONS.md
│       ├── STACK.md
│       ├── STRUCTURE.md
│       └── TESTING.md
├── .playwright-mcp/                  # Playwright MCP config
├── .pre-commit-config.yaml           # Pre-commit hooks (ruff, mypy, bandit, conventional commits)
├── .qwen/                            # Qwen client cache
├── .venv/                            # Python virtual environment
├── .worktrees/                       # Git worktrees
├── AGENTS.md                         # Agent instructions
├── CLAUDE.md                         # Claude-specific instructions
├── config/                           # YAML configuration
│   └── settings.yaml                 # Default settings source of truth
├── data/                             # Runtime data directory
│   ├── chat_history.json             # Persisted chat sessions
│   ├── rate_limits.db                # SQLite rate limit state
│   ├── chroma/                       # ChromaDB persistent storage
│   ├── raw/                          # Downloaded source documents (HTML, PDF)
│   ├── processed/                    # Converted Markdown files
│   ├── vectors/                      # Legacy vector storage
│   ├── evals/                        # Evaluation results
│   ├── evals_comprehensive_ablation/ # Ablation study results
│   ├── evals_feature_ablation_summary/ # Feature ablation summaries
│   ├── evals_reranking_ablation/     # Reranking ablation results
│   └── ...                           # Additional eval output dirs
├── docker-compose.yml                # Backend + Frontend + Test services
├── Dockerfile                        # Multi-stage Python build (builder → runtime)
├── docs/                             # Project documentation
│   ├── architecture/                 # Architecture docs
│   ├── evaluation/                   # Evaluation methodology
│   ├── testing/                      # Testing guides
│   ├── plans/                        # Feature plans
│   ├── reports/                      # Generated reports
│   ├── data/                         # Data documentation
│   ├── notebooks/                    # Published notebook HTML
│   └── *.md                          # Feature docs, quickstart, config guide
├── experiments/                      # Experiment YAML configs and outputs
│   ├── medical_semantic_exp.yaml
│   ├── outputs/
│   └── v1/
├── frontend/                         # SvelteKit 5 frontend SPA
│   ├── Dockerfile                    # Frontend multi-stage build (bun 1.3.9)
│   ├── package.json                  # Node dependencies
│   ├── svelte.config.js              # SvelteKit config (adapter-node)
│   ├── vite.config.ts                # Vite build config
│   ├── tsconfig.json                 # TypeScript config
│   ├── playwright.config.ts          # E2E test config
│   ├── src/
│   │   ├── app.html                  # HTML shell
│   │   ├── app.d.ts                  # Type declarations
│   │   ├── lib/                      # Shared library code
│   │   │   ├── components/           # Svelte components
│   │   │   ├── utils/                # Utility functions
│   │   │   ├── styles/               # CSS/styles
│   │   │   ├── assets/               # Static assets
│   │   │   ├── types.ts              # TypeScript type definitions
│   │   │   └── confidenceCalculator.ts
│   │   └── routes/                   # SvelteKit file-based routing
│   │       ├── +layout.svelte        # Root layout
│   │       ├── +page.svelte          # Main chat page
│   │       ├── docs/                 # Documentation pages
│   │       └── eval/                 # Evaluation dashboard pages
│   ├── static/                       # Static assets served directly
│   └── tests/                        # Playwright E2E tests
│       ├── chat.spec.ts
│       ├── helpers.ts
│       ├── markdown-rendering.spec.ts
│       ├── pipeline.spec.ts
│       ├── quality-metrics.spec.ts
│       └── visual-verification.spec.ts
├── pyproject.toml                    # Python project config, deps, tooling
├── uv.lock                           # Lockfile for uv package manager
├── README.md                         # Project overview
├── scripts/                          # Utility scripts
│   ├── benchmark_deepeval_multi.py   # Multi-run DeepEval benchmark
│   ├── check_docs_consistency.sh     # Doc consistency checker
│   ├── cleanup_wandb_runs.py         # W&B run cleanup
│   ├── download_nltk_data.py         # NLTK data downloader (used in Dockerfile)
│   ├── run_feature_ablations.py      # Feature ablation runner
│   ├── run_missing_ablations.sh      # Shell script for missing ablations
│   ├── run_variant_clean.py          # Variant cleanup script
│   └── manual/                       # Manual operation scripts
├── src/                              # Python backend source code
│   ├── __init__.py
│   ├── core/                         # Shared kernel (depends on nothing)
│   │   ├── __init__.py
│   │   ├── exceptions.py             # Layer-agnostic domain exceptions (AppError, StorageError, …)
│   │   └── source_metadata.py        # Source metadata inference (labels, domains, types)
│   ├── app/                          # HTTP/API layer
│   │   ├── __init__.py
│   │   ├── exceptions.py             # AppError hierarchy + FastAPI error handlers
│   │   ├── factory.py                # FastAPI app factory (create_app), lifespan, middleware setup
│   │   ├── logging.py                # Structured logging configuration
│   │   ├── security.py               # API key auth (bcrypt + legacy SHA256), AuthContext, APIKeyRecord
│   │   ├── session.py                # Anonymous session cookie management
│   │   ├── middleware/               # Starlette middleware
│   │   │   ├── __init__.py           # Re-exports all middleware
│   │   │   ├── auth.py               # APIKeyMiddleware — X-API-Key validation
│   │   │   ├── rate_limit.py         # RateLimitMiddleware — SQLite sliding-window
│   │   │   └── request_id.py         # RequestIDMiddleware — X-Request-ID tracing
│   │   ├── routes/                   # FastAPI routers
│   │   │   ├── __init__.py           # Re-exports all routers
│   │   │   ├── chat.py               # POST /chat — SSE streaming RAG responses
│   │   │   ├── evaluation.py         # Evaluation/metrics endpoints
│   │   │   ├── health.py             # GET /health — health check with runtime status
│   │   │   └── history.py            # Chat history CRUD endpoints
│   │   └── schemas/                  # Pydantic request/response models
│   │       ├── __init__.py
│   │       └── chat.py               # ChatRequest, ChatResponse models
│   ├── cli/                          # CLI entry points
│   │   ├── __init__.py
│   │   ├── serve.py                  # Dev server (uvicorn --reload)
│   │   ├── serve_production.py       # Production server (single worker, concurrency limit)
│   │   ├── ingest.py                 # Ingestion pipeline runner
│   │   └── eval_pipeline.py          # Evaluation pipeline CLI
│   ├── config/                       # Configuration management
│   │   ├── __init__.py               # Re-exports settings + path constants
│   │   ├── settings.py               # Pydantic BaseSettings (~285 lines, nested config models)
│   │   ├── context.py                # RuntimeState — thread-safe mutable runtime flags
│   │   ├── paths.py                  # Canonical filesystem paths
│   │   └── models/                   # Nested Pydantic config models
│   │       ├── __init__.py           # Re-exports ApiConfig, RetrievalConfig, StorageConfig
│   │       ├── api_config.py
│   │       ├── llm_config.py
│   │       ├── retrieval_config.py
│   │       └── storage_config.py
│   ├── evals/                        # Evaluation framework
│   │   ├── __init__.py
│   │   ├── artifacts.py              # Eval artifact management
│   │   ├── artifact_service.py       # EvaluationService — loads/shapes eval artifacts for routes
│   │   ├── dataset_builder.py        # Build eval datasets from sources
│   │   ├── deepeval_models.py        # DeepEval integration models
│   │   │   ├── schemas.py                # Eval data models
│   │   │   ├── assessment/               # Assessment orchestration
│   │   │   ├── orchestrator.py       # End-to-end eval orchestration (~645 lines)
│   │   │   ├── answer_eval.py        # LLM-as-judge answer evaluation
│   │   │   ├── retrieval_eval.py     # Retrieval quality evaluation (~765 lines)
│   │   │   ├── thresholds.py         # Quality thresholds
│   │   │   ├── l6_contract.py        # L6 contract validation
│   │   │   └── reporting.py          # Report generation
│   │   ├── checks/                   # Leveled pipeline quality checks
│   │   │   ├── l0_download.py        # Download integrity checks
│   │   │   ├── l1_html.py            # HTML conversion checks
│   │   │   ├── l2_pdf.py             # PDF loading checks
│   │   │   ├── l3_chunking.py        # Chunking quality checks
│   │   │   ├── l4_reference.py       # Reference data checks
│   │   │   ├── l5_index.py           # Index quality checks
│   │   │   └── shared.py             # Shared check utilities
│   │   ├── metrics/                  # Domain-specific metrics
│   │   │   ├── _utils.py             # Metric utilities
│   │   │   └── medical.py            # Medical domain metrics
│   │   └── synthetic/                # Synthetic data generation
│   │       └── generator.py          # Synthetic Q&A pair generator
│   ├── experiments/                  # Experiment management
│   │   ├── __init__.py
│   │   ├── comparison_report.py      # Cross-experiment comparison
│   │   ├── config.py                 # YAML config loading
│   │   ├── addition_config.py       # Feature-addition experiment schema (variants vs baseline)
│   │   ├── feature_ablation_runner.py # Feature ablation execution
│   │   ├── feature_addition_runner.py # Feature addition experiments
│   │   ├── metric_utils.py           # Metric computation helpers
│   │   ├── run_addition.py           # Addition experiment runner
│   │   ├── wandb_history.py          # W&B run history queries
│   │   └── wandb_tracking.py         # W&B experiment tracking
│   ├── infra/                        # Infrastructure layer
│   │   ├── __init__.py
│   │   ├── di.py                     # ServiceContainer (DI), lazy service initialization
│   │   ├── llm/                      # LLM client implementations
│   │   │   ├── __init__.py           # get_client() factory
│   │   │   ├── qwen_client.py        # Qwen/DashScope OpenAI-compatible client
│   │   │   └── litellm_client.py     # LiteLLM multi-provider client (OpenRouter)
│   │   └── storage/                  # Storage implementations
│   │       ├── __init__.py
│   │       ├── interfaces.py         # ChatHistoryStore Protocol
│   │       ├── chat_history_store.py # Abstract chat history store
│   │       └── file_chat_history_store.py # JSON file-backed, per-session truncation
│   ├── ingestion/                    # Data processing pipeline
│   │   ├── __init__.py
│   │   ├── artifacts.py              # Ingestion artifact management
│   │   ├── nodes/                    # Hamilton DAG nodes (one per canonical stage)
│   │   │   ├── download.py           # L0 download node
│   │   │   ├── parse.py              # L1/L2 parse node
│   │   │   ├── chunk.py              # L3 chunk node
│   │   │   ├── enrich.py             # L3b/c enrich + HyPE node
│   │   │   ├── reference.py          # L4 reference node
│   │   │   └── embedding.py          # L5 embed node
│   │   ├── indexing/                 # Vector indexing subsystem
│   │   │   ├── chroma_store.py       # ChromaVectorStore — hybrid search (~1010 lines)
│   │   │   ├── embedding.py          # Text embedding (Qwen API)
│   │   │   ├── keyword_index.py      # BM25 keyword search + medical entity boosting
│   │   │   ├── search.py             # Similarity, rank fusion, MMR algorithms
│   │   │   ├── text_utils.py         # Tokenization, acronyms, content hashing
│   │   │   └── migrate.py            # Migration utilities
│   │   └── steps/                    # Pipeline step implementations
│   │       ├── convert_html.py       # HTML → Markdown conversion
│   │       ├── download_pdfs.py      # PDF downloading
│   │       ├── download_web.py       # Web content downloading
│   │       ├── enrich_chunks.py      # LLM keyword extraction + summarization
│   │       ├── hypothetical_questions.py # HyPE index-time question generation
│   │       ├── load_markdown.py      # Markdown document loader
│   │       ├── load_pdfs.py          # PDF document loader
│   │       ├── load_reference_data.py # Medical reference range loader
│   │       └── chunking/             # Chunking strategy implementations
│   │           ├── core.py           # Core chunking logic
│   │           ├── strategies.py     # Strategy selection
│   │           ├── config.py         # Chunking configuration
│   │           ├── helpers.py        # Helper utilities
│   │           ├── medical_entity_detector.py # Medical entity detection
│   │           ├── medical_semantic.py # Medical-semantic chunking
│   │           ├── medical_structure_rules.py # Structure-based rules
│   │           ├── chonkie_adapter.py # Chonkie library adapter
│   │           └── qwen_embedding_wrapper.py # Embedding wrapper for chunking
│   ├── rag/                          # Retrieval-Augmented Generation engine
│   │   ├── __init__.py               # Re-exports core functions
│   │   ├── runtime.py                # Central retrieval orchestrator (~495 lines)
│   │   ├── config.py                 # RetrievalDiversityConfig + config resolution (~105 lines)
│   │   ├── diversification.py        # MMR reranking + result deduplication (~130 lines)
│   │   ├── index.py                  # Index initialization + experiment config (~360 lines)
│   │   ├── query_expansion.py        # Lexical/medical query expansion (~125 lines)
│   │   ├── retrieval.py              # Candidate retrieval + result merging (~115 lines)
│   │   ├── formatting.py             # Context formatting + source citation building
│   │   ├── hyde.py                   # HyDE query expansion (~305 lines)
│   │   ├── medical_expansion.py      # Medical term expansion provider (noop)
│   │   ├── production_profile.py     # Production profile application
│   │   ├── reranker.py               # Cross-encoder reranking
│   │   ├── trace_models.py           # Pipeline trace Pydantic models
│   │   └── query_understanding/      # Query classification + routing
│   │       ├── classifier.py         # Query type classifier (~315 lines)
│   │       ├── router.py             # Retrieval parameter router (~250 lines)
│   │       └── strategies.py         # Routing strategies (~200 lines)
│   └── usecases/                     # Use case orchestration (chat only)
│       ├── __init__.py
│       ├── chat.py                   # Chat processing (sync + streaming)
│       └── pipeline.py               # Offline ingestion pipeline orchestration
├── tests/                            # Python test suite
│   ├── conftest.py                   # Global fixtures and hooks
│   ├── fixtures/                     # Test data fixtures
│   │   ├── golden_queries.json
│   │   ├── golden_queries_expanded.json
│   │   ├── golden_queries_comprehensive.json
│   │   ├── golden_queries_diverse.json
│   │   ├── golden_queries_all.json
│   │   ├── golden_conversations.json
│   │   └── sample_medical.txt
│   ├── unit/                         # Unit tests (~50 files)
│   │   ├── test_chunker.py
│   │   ├── test_configuration.py
│   │   ├── test_settings.py
│   │   ├── test_retrieval_reranking_modes.py
│   │   └── ... (~45 more)
│   ├── integration/                  # Integration tests (~15 files)
│   │   ├── test_app_security.py
│   │   ├── test_chat_sources.py
│   │   ├── test_chroma_store.py
│   │   ├── test_retrieval.py
│   │   └── ... (~10 more)
│   └── e2e/                          # End-to-end tests
│       ├── test_backend_e2e_real_apis.py
│       └── test_hamilton_pipeline.py
└── wandb/                            # Weights & Biases local cache
```

## Key File Locations

| Purpose | File |
|---------|------|
| App factory & startup | `src/app/factory.py` |
| All configuration | `src/config/settings.py` + `config/settings.yaml` |
| Config sub-models | `src/config/models/` |
| Main retrieval orchestrator | `src/rag/runtime.py` |
| Index init + experiment config | `src/rag/index.py` |
| MMR diversification | `src/rag/diversification.py` |
| Query expansion | `src/rag/query_expansion.py` |
| Candidate retrieval | `src/rag/retrieval.py` |
| Vector store (ChromaDB) | `src/ingestion/indexing/chroma_store.py` |
| Chat endpoint (SSE) | `src/app/routes/chat.py` |
| Chat use case | `src/usecases/chat.py` |
| DI container | `src/infra/di.py` |
| Ingestion pipeline | `src/cli/ingest.py` → `src/ingestion/pipeline.py` |
| LLM client | `src/infra/llm/qwen_client.py` |
| Production entrypoint | `src/cli/serve_production.py` |
| Docker entrypoint | `Dockerfile` (CMD: `python -m src.cli.serve_production`) |
| Source metadata logic | `src/core/source_metadata.py` |
| Trace/data models | `src/rag/trace_models.py` |
| Evaluation orchestrator | `src/evals/assessment/orchestrator.py` |
| Feature-addition schema | `src/experiments/addition_config.py` |
| Frontend main page | `frontend/src/routes/+page.svelte` |
| Frontend package config | `frontend/package.json` |
| Pre-commit hooks | `.pre-commit-config.yaml` |
| Default settings | `config/settings.yaml` |

## Naming Conventions

### Files and Directories

| Pattern | Convention | Examples |
|---------|-----------|----------|
| Python modules | `snake_case.py` | `chat_history_store.py`, `keyword_index.py` |
| Test files | `test_*.py` | `test_chunker.py`, `test_reranker.py` |
| CLI entry points | Verb or noun describing the action | `serve.py`, `ingest.py`, `eval_pipeline.py` |
| Pipeline step files | Verb phrase describing the step | `download_web.py`, `convert_html.py`, `load_pdfs.py` |
| Config files | Domain noun | `settings.py`, `context.py`, `paths.py` |
| Config models | `{domain}_config.py` | `api_config.py`, `llm_config.py` |
| Svelte routes | SvelteKit file-based routing | `+page.svelte`, `+layout.svelte` |
| Experiment configs | YAML in `experiments/` | `medical_semantic_exp.yaml` |
| Eval check levels | `l{N}_{stage}.py` | `l0_download.py`, `l3_chunking.py`, `l5_index.py` |
| E2E test files | `test_*.py` in `tests/e2e/` | `test_backend_e2e_real_apis.py` |
| Integration tests | `test_*.py` in `tests/integration/` | `test_chroma_store.py` |
| Unit tests | `test_*.py` in `tests/unit/` | `test_chunker.py` |

### Code Conventions

- **Imports**: Relative within package (`from src.config import settings`), absolute for external libs
- **Module-level singletons**: `settings` (config), `get_runtime_state()` (runtime), `get_container()` (DI)
- **Re-export pattern**: Each package has `__init__.py` that re-exports key symbols
- **Backward-compat**: compat shims were deleted in Phase 1 (roadmap P1.5); `settings.py` retains `_LEGACY_FIELD_MAP` for flat → nested env var migration
- **Pydantic models**: Used for schemas (`src/app/schemas/`), trace models (`src/rag/trace_models.py`), nested config (`src/config/models/`), and settings (`src/config/settings.py`)
- **Protocol-based interfaces**: `ChatHistoryStore` in `src/infra/storage/interfaces.py`
- **Dataclass-based config**: `RetrievalDiversityConfig`, `RuntimeRetrievalConfig`

## Important Config Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Python project metadata, dependencies (uv-managed), ruff/pytest/mypy/bandit config |
| `uv.lock` | Deterministic dependency lockfile |
| `config/settings.yaml` | Default settings source of truth |
| `.env.example` | Template showing required environment variables |
| `.env` | Local secrets (API keys, model names) — gitignored |
| `.env.keys` | API key records for authentication (encrypted via dotenvx) |
| `.pre-commit-config.yaml` | Pre-commit hooks: ruff, ruff-format, mypy, bandit, conventional commits, quarto render |
| `docker-compose.yml` | 3-service setup: backend, frontend, test (profile-gated) |
| `Dockerfile` | Multi-stage Python build; copies `src/`, mounts `data/` |
| `frontend/Dockerfile` | Multi-stage Node build with oven/bun:1.3.9-alpine |
| `frontend/svelte.config.js` | SvelteKit config with `adapter-node` |
| `frontend/vite.config.ts` | Vite dev/build config (vite 7) |
| `frontend/tsconfig.json` | TypeScript strict mode |
| `frontend/playwright.config.ts` | E2E test configuration |
| `experiments/*.yaml` | Experiment/ablation configuration files |
| `.python-version` | Pins Python 3.12 |

## Where Different Types of Code Live

| Type | Location |
|------|----------|
| HTTP routes | `src/app/routes/` |
| Middleware | `src/app/middleware/` |
| Request/response schemas | `src/app/schemas/` |
| Business logic / use cases | `src/usecases/` |
| RAG retrieval | `src/rag/` |
| RAG config | `src/rag/config.py` |
| Index init | `src/rag/index.py` |
| MMR diversification | `src/rag/diversification.py` |
| Data ingestion pipeline | `src/ingestion/` |
| Vector store | `src/ingestion/indexing/chroma_store.py` |
| LLM integration | `src/infra/llm/` |
| DI / service container | `src/infra/di.py` |
| Storage abstractions | `src/infra/storage/` |
| Configuration | `src/config/` + `config/settings.yaml` |
| Runtime state | `src/config/context.py` |
| Evaluation | `src/evals/` |
| Experiments / ablation | `src/experiments/` |
| CLI commands | `src/cli/` |
| Utility scripts | `scripts/` |
| Source metadata | `src/core/source_metadata.py` |
| Unit tests | `tests/unit/` |
| Integration tests | `tests/integration/` |
| E2E tests | `tests/e2e/` |
| E2E tests (frontend) | `frontend/tests/` |
| Frontend components | `frontend/src/lib/components/` |
| Frontend routes | `frontend/src/routes/` |
| Frontend utilities | `frontend/src/lib/utils/` |
| Documentation | `docs/` |
| Runtime data | `data/` |
| Experiment data | `experiments/` |
