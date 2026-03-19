# Quick Start

This guide gets the project running locally with the fewest moving parts.

## Prerequisites

- Python 3.13+
- `uv`
- Node.js and `npm` for the frontend
- A DashScope API key for Qwen (`DASHSCOPE_API_KEY`)

## 1. Install backend dependencies

From the repository root:

```bash
uv sync
```

## 2. Configure environment

Copy the example file and add your API key:

```bash
cp .env.example .env
```

Minimum required setting:

```dotenv
DASHSCOPE_API_KEY=your_api_key_here
```

Optional:

- Leave `ENVIRONMENT=development` for local work.
- Set `API_KEYS` or `API_KEYS_JSON` if you want backend request authentication enabled locally.
- See `docs/configuration.md` for the full configuration reference.

## 3. Download NLTK data

```bash
uv run python scripts/download_nltk_data.py
```

## 4. Start the backend API

```bash
uv run python -m src.cli.serve
```

The API will be available at `http://localhost:8000`.

If you configured API keys, include `X-API-Key` in backend requests.

Useful endpoints:

- `GET /health`
- `POST /chat`
- `GET /history`

## 5. Build the local search index

Run ingestion once before expecting full RAG retrieval results:

```bash
uv run python -m src.cli.ingest
```

Useful variants:

```bash
uv run python -m src.cli.ingest --skip-download
uv run python -m src.cli.ingest --force
```

## 6. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the frontend URL printed by Vite, typically `http://localhost:5173`.

## 7. Run tests

Backend:

```bash
uv run pytest
uv run ruff check .
```

Frontend:

```bash
cd frontend
npm test
```

## 8. Run evaluation (optional)

The system includes a comprehensive evaluation framework for assessing pipeline quality:

```bash
# Run full pipeline evaluation
uv run python -m src.cli.eval_pipeline

# Run specific experiment variant
uv run python -m src.cli.eval_pipeline --variant my-experiment

# View evaluation results
# Access http://localhost:8000/evaluation/latest (after starting backend)
# Or visit the frontend evaluation dashboard at http://localhost:5173/eval
```

See `docs/architecture/overview.md` for evaluation system details.
See `docs/local-workflows.md` for the recommended operator workflow that combines ingestion, serving, frontend, and eval runs.

## Troubleshooting

- If chat responses fail immediately, re-check `.env` and confirm `DASHSCOPE_API_KEY` is set.
- If retrieval looks empty or weak, run `uv run python -m src.cli.ingest` and wait for indexing to finish.
- If docs drift from the code, run `bash scripts/check_docs_consistency.sh`.
