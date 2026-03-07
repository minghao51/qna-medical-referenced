# Health Screening Interpreter

Medical Q&A system with a FastAPI backend, RAG retrieval, an offline ingestion/indexing pipeline, and a Svelte frontend.

## Quick Start (Backend)

```bash
uv sync
cp .env.example .env
# add DASHSCOPE_API_KEY (and optionally API_KEYS) to .env

uv run python scripts/download_nltk_data.py
uv run python -m src.cli.serve
```

API server starts on `http://localhost:8000`.

## Canonical Commands

```bash
# Run backend API (canonical)
uv run python -m src.cli.serve

# Run offline ingestion/indexing pipeline (canonical)
uv run python -m src.cli.ingest
uv run python -m src.cli.ingest --skip-download
uv run python -m src.cli.ingest --force

# Tests and lint
uv run pytest
uv run ruff check .

# Docs consistency
bash scripts/check_docs_consistency.sh
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Basic service check |
| `/health` | GET | Health status |
| `/chat` | POST | Ask a question |
| `/history/{session_id}` | GET | Read chat history |
| `/history/{session_id}` | DELETE | Clear chat history |

## Repository Map (Fresh Eyes)

### Backend (canonical)

```text
src/
  app/                    FastAPI app factory, routes, schemas, middleware
  usecases/               Application orchestration (chat flow)
  rag/                    Runtime retrieval + trace models
  ingestion/              Offline data pipeline + indexing internals
  infra/                  External integrations (Qwen client, local storage)
  config/                 Settings and canonical paths
  cli/                    Canonical CLI entrypoints
```

### Frontend

```text
frontend/                 Svelte app (separate dev/build commands)
```

## Documentation

- `docs/README.md` - docs index
- `docs/architecture/overview.md` - backend structure overview (current)
- `docs/architecture/rag-system.md` - runtime retrieval + ingestion flow (current)
- `docs/testing/backend-tests.md` - backend test inventory
- `docs/reports/` - dated historical notes and reports

## Notes

- Runtime retrieval code and offline ingestion/indexing code are now separated (`src/rag` vs `src/ingestion`).
- Data paths remain compatible (`data/raw`, `data/vectors`, `data/chat_history.json`).
- Historical reports may reference paths or structures that changed later.
