# Quick Start

Prerequisites and first-time setup. For daily commands, see `docs/local-workflows.md`.

## Prerequisites

- Python 3.13+
- `uv`
- Node.js and `npm` for the frontend
- A DashScope API key for Qwen (`DASHSCOPE_API_KEY`)
- [dotenvx](https://dotenvx.com) for encrypted environment variables (`npm install @dotenvx/dotenvx -g`)

## First-Time Setup

```bash
# 1. Install dependencies
uv sync --extra test

# 2. Configure API key
dotenvx set DASHSCOPE_API_KEY "your_api_key_here"

# 3. Download NLTK data
uv run python scripts/download_nltk_data.py
```

See `docs/configuration.md` for all settings and `docs/dependencies.md` for dependency details.

## Run the System

Follow the full workflow in `docs/local-workflows.md`:

1. Build the search index: `dotenvx run -- uv run python -m src.cli.ingest`
2. Start the backend: `dotenvx run -- uv run python -m src.cli.serve`
3. Start the frontend: `cd frontend && npm install && npm run dev`

Backend API: `http://localhost:8000`
Frontend: `http://localhost:5173`

## Run Tests

```bash
uv run pytest
uv run ruff check .
cd frontend && npm test
```

## Troubleshooting

- Chat fails immediately: verify API key with `dotenvx get DASHSCOPE_API_KEY`
- Retrieval looks empty: run `dotenvx run -- uv run python -m src.cli.ingest`
- Docs drift from code: run `bash scripts/check_docs_consistency.sh`
