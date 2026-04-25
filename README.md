# Health Screening Interpreter

> **Project Purpose:** This repository explores ingestion, evaluation, retrieval, and RAG (Retrieval-Augmented Generation) pipeline strategies for medical Q&A systems. It serves as a testbed for comparing different approaches to document processing, query expansion, and quality assessment.

Medical Q&A system with:

- a FastAPI backend for chat, history, and evaluation APIs
- an offline ingestion and indexing pipeline for the document corpus
- a Svelte frontend for chat and evaluation dashboards

## Security Notice

**API Keys & Secrets**:
- This project uses [dotenvx](https://dotenvx.com) for encrypted environment variables
- Copy `.env.example` for reference, then set keys: `dotenvx set DASHSCOPE_API_KEY "your-key"`
- **NEVER commit `.env.keys` to version control** - it contains private decryption keys
- Share only `DOTENV_PRIVATE_KEY` with team via secure vault (1Password, etc.)
- All API keys are hashed using bcrypt (with salt) before storage
- For production deployments, enable API key authentication (`API_KEYS` or `API_KEYS_JSON`)
- Rotate exposed keys immediately if accidentally committed
- See [`.context7/dotenvx-best-practices.md`](.context7/dotenvx-best-practices.md) for complete guide

**Production Checklist**:
- [ ] Set strong API keys and enable authentication
- [ ] Configure rate limiting (`RATE_LIMIT_PER_MINUTE`)
- [ ] Use HTTPS and reverse proxy in production
- [ ] Restrict CORS origins (`CORS_ALLOWED_ORIGINS`)
- [ ] Monitor logs for security events

## Start Here

For setup and day-to-day usage, use the docs in this order:

- `docs/quickstart.md` for local setup
- `docs/local-workflows.md` for canonical ingestion, serving, and evaluation commands
- `docs/configuration.md` for environment variables and runtime settings
- `docs/dependencies.md` for dependency management
- `docs/architecture/overview.md` for repository structure
- `docs/architecture/rag-system.md` for ingestion and retrieval data flow
- `docs/architecture/pipeline-strategies.md` for pipeline strategies and gap tracker
- `docs/testing/backend-tests.md` and `docs/testing/playwright.md` for test workflows

## Canonical Commands

```bash
# Install all dependencies (including test dependencies)
uv sync --extra test

# Setup environment (requires dotenvx: npm install @dotenvx/dotenvx -g)
dotenvx set DASHSCOPE_API_KEY "your-key"
uv run python scripts/download_nltk_data.py

# Run with dotenvx to decrypt .env
dotenvx run -- uv run python -m src.cli.serve
dotenvx run -- uv run python -m src.cli.ingest  # Standard pipeline (use --parallel for Hamilton DAG)
dotenvx run -- uv run python -m src.cli.eval_pipeline

uv run pytest
uv run ruff check .

bash scripts/check_docs_consistency.sh
```

### Hamilton Pipeline Usage

The ingestion CLI supports a **Hamilton DAG** mode for parallel, efficient execution:

```bash
# Full pipeline (standard mode)
dotenvx run -- uv run python -m src.cli.ingest

# Hamilton DAG mode (parallel execution)
dotenvx run -- uv run python -m src.cli.ingest --parallel 4

# Additional feature flags
dotenvx run -- uv run python -m src.cli.ingest --enable-hype
dotenvx run -- uv run python -m src.cli.ingest --enable-keyword-extraction
```

**Pipeline Stages:**
- **L0**: Download web content and PDFs (Bronze layer)
- **L1-L2**: Parse and convert documents (Bronze→Silver layer)
- **L3**: Chunk documents (Silver→Gold layer)
- **L4**: Enrich with HyPE/keywords (Gold layer)
- **L5-L6**: Generate embeddings and store vectors (Platinum layer)

**Features:**
- Parallel execution with configurable cores
- Idempotent operations (safe to re-run)
- DAG visualization with `--visualize` flag
- Incremental updates (skip completed stages)

**Note**: Use `uv sync --extra test` to install all test dependencies, including:
- `pytest-asyncio` for async test support
- `deepeval` for evaluation tests
- Other optional dependencies

For production deployments, `uv sync` alone is sufficient.

The backend API serves on `http://localhost:8000`.

## Repository Map

```text
src/
  app/          FastAPI app factory, routes, schemas, middleware
  cli/          Canonical CLI entrypoints
  config/       Settings and path ownership
  evals/        Pipeline quality assessment
  infra/        External integrations
  ingestion/    Offline ingestion and indexing internals
  rag/          Runtime retrieval and trace formatting
  usecases/     Application orchestration

frontend/       Svelte frontend
docs/           Current docs, plans, and historical reports
scripts/        Small operational scripts
tests/          Backend test suite
  test_chat_multi_turn.py      # Multi-turn session tests
  test_eval_multi_turn.py      # DeepEval conversation evaluation
  fixtures/
    golden_conversations.json  # 15 conversations across 4 categories
```

## Multi-Turn Conversations

The system supports session-based multi-turn conversations with:
- Cookie-backed session persistence (see `docs/anonymous-sessions.md`)
- Context building from chat history
- Turn-level source and keyword verification
- Golden conversations dataset for testing (15 conversations across 4 categories)

Testing:
- `tests/test_chat_multi_turn.py` - Session persistence and context tests
- `tests/test_eval_multi_turn.py` - DeepEval conversation evaluation

## Query Expansion

The system supports multiple query expansion layers:
- **HyDE (Hypothetical Document Embeddings)**: Query-time hypothetical answer generation
- **HyPE (Hypothetical Prompt Embeddings)**: Index-time hypothetical question generation
- Acronym expansion, keyword focus, tokenization

See `docs/architecture/pipeline-strategies.md` for detailed comparison.

## Deployment

- `docs/public-app-deployment.md` — Publishing with anonymous public access
- `docs/anonymous-sessions.md` — Cookie-backed chat history behavior
- `docs/admin-api-auth.md` — Optional API key authentication

## Data Sources

- `docs/data/sources.md` — Ingestion source inventory (Singapore government health sites)

## Latest Feature Ablation Findings

The latest feature-family ablation pass on the expanded `54`-query golden set is summarized in `docs/feature_ablation_findings.md`.

- **Keyword enrichment**: no measurable retrieval gain over baseline
- **HyPE / HyDE**: no measurable retrieval gain; `hype_10pct` only wins on latency
- **Cross-encoder reranking**: meaningful retrieval lift with a clear latency tradeoff

Expanded benchmark snapshot:

| Family | Winner | Key result |
|---|---|---|
| Keyword | `baseline` | Same quality as enriched variants, lowest p50 latency |
| HyPE / HyDE | `hype_10pct` | Same quality as `hype_disabled`, slightly faster |
| Reranking | `cross_encoder_only` | `NDCG@K` 0.7205 vs 0.6813 baseline, `evidence_hit_rate` 0.1852 vs 0.0185 |

The default served runtime now uses `baseline_cross_encoder`, which keeps baseline ingestion/indexing settings and enables cross-encoder reranking at retrieval time.

## API Surface

- `GET /`
- `GET /health`
- `POST /chat` - Supports multi-turn via session cookies
- `GET /history`
- `DELETE /history`
- `GET /evaluation/latest`
- `GET /evaluation/runs`
- `GET /evaluation/history`
- `GET /evaluation/steps/{stage}`

## Documentation Layout

- `docs/README.md` is the documentation index
- `docs/architecture/` contains maintained architecture docs
- `docs/evaluation/` contains current evaluation-specific documentation
- `docs/testing/` contains operational test guides
- `docs/plans/` contains design docs that still matter
- `docs/archive/` contains dated historical writeups organized by type (reports, handoffs, plans)
