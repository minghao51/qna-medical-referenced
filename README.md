# Health Screening Interpreter

> **Project Purpose:** This repository explores ingestion, evaluation, retrieval, and RAG (Retrieval-Augmented Generation) pipeline strategies for medical Q&A systems. It serves as a testbed for comparing different approaches to document processing, query expansion, and quality assessment.

Medical Q&A system with:

- a FastAPI backend for chat, history, and evaluation APIs
- an offline ingestion and indexing pipeline for the document corpus
- a Svelte frontend for chat and evaluation dashboards

## Start Here

For setup and day-to-day usage, use the docs in this order:

- `docs/quickstart.md` for local setup
- `docs/local-workflows.md` for canonical ingestion, serving, and evaluation commands
- `docs/configuration.md` for environment variables and runtime settings
- `docs/architecture/overview.md` for repository structure
- `docs/testing/backend-tests.md` and `docs/testing/playwright.md` for test workflows

## Canonical Commands

```bash
# Install all dependencies (including test dependencies)
uv sync --extra test

cp .env.example .env
uv run python scripts/download_nltk_data.py

uv run python -m src.cli.serve
uv run python -m src.cli.ingest
uv run python -m src.cli.eval_pipeline

uv run pytest
uv run ruff check .

bash scripts/check_docs_consistency.sh
```

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
- `docs/reports/` contains dated historical writeups
