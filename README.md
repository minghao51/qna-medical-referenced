# Health Screening Interpreter

Medical Q&A system with a FastAPI backend, RAG retrieval pipeline, and Gemini-based answer generation for health-screening questions.

## Quick Start (Backend)

```bash
uv sync
cp .env.example .env
# add GEMINI_API_KEY (and optionally API_KEYS) to .env

uv run python scripts/download_nltk_data.py
uv run python -m src.main
```

API server starts on `http://localhost:8000`.

## Common Commands

```bash
# Run backend API
uv run python -m src.main

# Run full RAG data pipeline (L0-L6)
uv run python -m src.pipeline.run_pipeline

# Pipeline variants
uv run python -m src.pipeline.run_pipeline --skip-download
uv run python -m src.pipeline.run_pipeline --force

# Tests and lint
uv run pytest
uv run ruff check .
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Basic service check |
| `/health` | GET | Health status |
| `/chat` | POST | Ask a question |
| `/history/{session_id}` | GET | Read chat history |
| `/history/{session_id}` | DELETE | Clear chat history |

### Example Request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"message":"What is a normal LDL cholesterol level?","session_id":"user123"}'
```

## Project Layout (High Level)

```text
src/
  main.py                 FastAPI app and routes
  api/                    API schemas
  services/               Chat orchestration logic
  pipeline/               L0-L6 data pipeline + retrieval
  llm/                    Gemini client
  middleware/             API key, rate limit, request ID
  storage/                Chat history persistence
docs/
  README.md               Docs index
  architecture/           System docs
  data/                   Source and dataset docs
  testing/                Test docs
  reports/                Dated historical reports
tests/                    Backend tests
frontend/                 Frontend app
```

## Documentation

- `docs/README.md` - documentation index
- `docs/architecture/overview.md` - system architecture overview
- `docs/architecture/rag-system.md` - detailed RAG data flow
- `docs/data/sources.md` - web data sources used by L0
- `docs/testing/backend-tests.md` - backend test inventory

## Notes

- Runtime retrieval and indexing currently share code in `src/pipeline/`.
- Historical reports in `docs/reports/` may reference older file paths.
