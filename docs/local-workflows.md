# Local Workflows

This is the canonical operator guide for running the system locally.

Use this document when you need to:

- refresh the corpus and vector index
- start the chat/RAG app
- run offline pipeline evaluation
- explain the available surfaces to another user

## Mental Model

There are three supported entrypoints:

1. `uv run python -m src.cli.ingest`
   Refreshes the offline data pipeline from source content through indexing.
2. `uv run python -m src.cli.serve`
   Starts the backend API and runtime RAG service.
3. `uv run python -m src.cli.eval_pipeline`
   Runs offline evaluation and writes artifacts under `data/evals/`.

There is no separate canonical CLI for "chunk only" or "RAG only".

- Chunking is an internal stage inside `src.cli.ingest` (`L3` in the pipeline).
- Runtime RAG is provided by the API server started via `src.cli.serve`.

## Recommended End-to-End Flow

### 1. Initial setup

```bash
uv sync
cp .env.example .env
uv run python scripts/download_nltk_data.py
```

Minimum required env:

```dotenv
DASHSCOPE_API_KEY=your_api_key_here
```

### 2. Refresh the corpus and index

Run the full ingestion pipeline:

```bash
uv run python -m src.cli.ingest
```

This executes the full offline refresh flow:

- `L0` download web content
- `L0b` download PDFs
- `L1` convert HTML to Markdown
- `L2` load PDF documents
- `L3` chunk documents
- `L4` load reference data
- `L5` embed and store vectors
- `L6` initialize runtime RAG index

Useful variants:

```bash
# Reuse existing downloaded raw files and only rebuild downstream stages
uv run python -m src.cli.ingest --skip-download

# Force-clear and rebuild the vector store
uv run python -m src.cli.ingest --force

# Re-convert HTML to Markdown even if markdown files already exist
uv run python -m src.cli.ingest --force-html
```

### 3. Start the backend API and runtime RAG

```bash
uv run python -m src.cli.serve
```

The backend serves on `http://localhost:8000`.

This is the process that powers:

- `POST /chat`
- `GET /history`
- `GET /evaluation/latest`
- `GET /evaluation/history`

### 4. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the frontend URL printed by Vite, typically `http://localhost:5173`.

### 5. Run offline evaluation

In a third terminal, run the eval pipeline:

```bash
uv run python -m src.cli.eval_pipeline
```

Common variants:

```bash
# Run a versioned experiment config
uv run python -m src.cli.eval_pipeline --config experiments/v1/baseline.yaml

# Run a specific experiment variant from the config
uv run python -m src.cli.eval_pipeline --config experiments/v1/baseline.yaml --variant chunk_small

# Run the base experiment plus all named variants
uv run python -m src.cli.eval_pipeline --config experiments/v1/baseline.yaml --all-variants

# Reuse a cached dataset when iterating on evaluation
uv run python -m src.cli.eval_pipeline --reuse-cached-dataset

# Force a new eval run instead of dedup-reusing a prior matching run
uv run python -m src.cli.eval_pipeline --force-rerun
```

Evaluation artifacts are written to `data/evals/`.

## What To Tell Users

When presenting the app to another user, keep the explanation simple:

- Chat UI: `http://localhost:5173/`
  This is the user-facing RAG application. Ask medical screening questions here.
- Eval UI: `http://localhost:5173/eval`
  This is the operator/developer dashboard for retrieval and pipeline quality.
- Backend API: `http://localhost:8000`
  This powers both chat and evaluation data.

Recommended wording:

> The chat page is the product surface. The eval page is for internal verification and regression tracking. If content or retrieval quality changes, we refresh the ingestion pipeline, restart the backend if needed, and rerun the eval pipeline.

## Recommended Working Patterns

### Daily local development

```bash
uv run python -m src.cli.ingest --skip-download
uv run python -m src.cli.serve
cd frontend && npm run dev
```

### Full corpus refresh

```bash
uv run python -m src.cli.ingest
uv run python -m src.cli.serve
cd frontend && npm run dev
```

### Regression check before sharing changes

```bash
uv run python -m src.cli.ingest --skip-download
uv run python -m src.cli.eval_pipeline --config experiments/v1/baseline.yaml --all-variants
uv run pytest
```

## Result Inspection

- Chat behavior: test in `http://localhost:5173/`
- Eval summary: inspect `http://localhost:5173/eval`
- Raw eval artifacts: inspect `data/evals/<run_dir>/`
- Latest eval API payload: `http://localhost:8000/evaluation/latest`

## Notes

- If retrieval seems empty or stale, rerun `src.cli.ingest`.
- If the frontend does not reflect backend changes, restart `src.cli.serve`.
- If the eval page looks stale after code changes, restart the backend before trusting `/evaluation/*` responses.
