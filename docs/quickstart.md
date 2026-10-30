# Quick Start

Prerequisites and first-time setup. For daily commands, see `docs/local-workflows.md`.

## Prerequisites

- Python 3.12.x
- `uv`
- Node.js and `npm` for the frontend
- A DashScope API key for Qwen, or a Google Gemini API key (see below)
- [dotenvx](https://dotenvx.com) for encrypted environment variables (`npm install @dotenvx/dotenvx -g`)

Environment overrides use the `APP__` prefix with `__` as the nested delimiter, mirroring the
`config/settings.yaml` structure (for example `llm.dashscope_api_key` becomes
`APP__LLM__DASHSCOPE_API_KEY`). Flat legacy names such as `DASHSCOPE_API_KEY` are **not** read.

**Provider default:** `config/settings.yaml` sets `llm.provider: gemini`, so a Gemini API key
(`APP__LLM__GEMINI_API_KEY`) is required unless you override the provider (for example
`APP__LLM__PROVIDER=qwen` together with `APP__LLM__DASHSCOPE_API_KEY`).

## First-Time Setup

```bash
# 1. Install dependencies
uv sync --dev --group evaluation

# 2. Configure the API key for the default provider (llm.provider: gemini)
dotenvx set APP__LLM__GEMINI_API_KEY "your_api_key_here"
# Using Qwen instead? Override the provider and store the DashScope key:
#   dotenvx set APP__LLM__PROVIDER qwen
#   dotenvx set APP__LLM__DASHSCOPE_API_KEY "your_api_key_here"

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

- Chat fails immediately: verify API key with `dotenvx get APP__LLM__DASHSCOPE_API_KEY` (or
  `dotenvx get APP__LLM__GEMINI_API_KEY` when `llm.provider` is `gemini`, the shipped default)
- Retrieval looks empty: run `dotenvx run -- uv run python -m src.cli.ingest`
- Docs drift from code: run `bash scripts/check_docs_consistency.sh`
