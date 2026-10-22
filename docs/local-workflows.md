# Local Workflows

This is the canonical operator guide for running the system locally.

Use this document when you need to:

- refresh the corpus and vector index
- start the chat/RAG app
- run offline pipeline evaluation
- explain the available surfaces to another user

## Mental Model

There are three supported entrypoints:

1. `dotenvx run -- uv run python -m src.cli.ingest`
   Refreshes the offline data pipeline from source content through indexing.
2. `dotenvx run -- uv run python -m src.cli.serve`
   Starts the backend API and runtime RAG service.
3. `dotenvx run -- uv run python -m src.cli.eval_pipeline`
   Runs offline evaluation and writes artifacts under `data/evals/`.

There is no separate canonical CLI for "chunk only" or "RAG only".

- Chunking is an internal stage inside `src.cli.ingest` (`L3` in the pipeline).
- Runtime RAG is provided by the API server started via `src.cli.serve`.
- All commands require `dotenvx run --` to decrypt environment variables.

## Recommended End-to-End Flow

### 1. Initial setup

```bash
uv sync
npm install @dotenvx/dotenvx -g
dotenvx set DASHSCOPE_API_KEY "your_api_key_here"
uv run python scripts/download_nltk_data.py
```

### 2. Refresh the corpus and index

Run the full ingestion pipeline:

```bash
dotenvx run -- uv run python -m src.cli.ingest
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
dotenvx run -- uv run python -m src.cli.ingest --skip-download

# Force-clear and rebuild the vector store
dotenvx run -- uv run python -m src.cli.ingest --force

# Re-convert HTML to Markdown even if markdown files already exist
dotenvx run -- uv run python -m src.cli.ingest --force-html
```

### 3. Start the backend API and runtime RAG

```bash
dotenvx run -- uv run python -m src.cli.serve
```

The backend serves on `http://localhost:8000`.

This is the process that powers:

- `POST /chat`
- `GET /history`
- `GET /evaluation/latest`
- `GET /evaluation/history`

### Private-lab production-mode constraints

- Inject `APP__APP__ENVIRONMENT=production`, caller authentication via `APP__API__API_KEYS` or `APP__API__API_KEYS_JSON`, and a separate `APP__API__SESSION_SIGNING_SECRET` through your approved secret manager/environment workflow. The entrypoint name alone does not select production settings.
- The signing secret must be independently generated and contain at least 32 UTF-8 bytes after trimming outer whitespace. Do not reuse a caller/provider API key. Missing or weak production configuration fails before serving; an explicitly weak secret also fails in development.
- Without a configured development secret, a process-random key is used. Restarting that process, rotating a configured secret, or moving from the old API-key/environment-derived signer invalidates old cookies and starts fresh browser sessions. Historical messages are not deleted or migrated; there is no legacy-signature fallback.
- File-backed history supports **one process/worker and one store instance**. `src.cli.serve_production --workers` rejects values other than `1`; do not bypass this with multiple Uvicorn workers, independent servers sharing the file, or an external process manager. This guard does not implement cross-process locking.
- Bind explicitly to loopback for private local use, for example `dotenvx run -- uv run python -m src.cli.serve_production --host 127.0.0.1 --workers 1`. Existing bind defaults are unchanged. Do not expose this research application publicly; provider/profile readiness, container parity and a value-free preflight remain separate migration gates.
- Generation providers are restricted to `qwen`, `gemini`, and `litellm`; unknown values fail rather than falling back to Qwen. The selected comparison profile does not silently change serving defaults.

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
dotenvx run -- uv run python -m src.cli.eval_pipeline
```

Common variants:

```bash
# Run a versioned experiment config
dotenvx run -- uv run python -m src.cli.eval_pipeline --config experiments/v1/baseline.yaml

# Run a specific experiment variant from the config
dotenvx run -- uv run python -m src.cli.eval_pipeline --config experiments/v1/baseline.yaml --variant chunk_small

# Run the base experiment plus all named variants
dotenvx run -- uv run python -m src.cli.eval_pipeline --config experiments/v1/baseline.yaml --all-variants

# Select a previously reviewed/frozen dataset explicitly
dotenvx run -- uv run python -m src.cli.eval_pipeline --dataset-path path/to/reviewed-dataset.json

# Retained compatibility flag; every assessment already executes a fresh attempt
dotenvx run -- uv run python -m src.cli.eval_pipeline --force-rerun
```

Evaluation artifacts are written to `data/evals/`. Assessments no longer automatically reuse completed runs or answer caches. `--reuse-cached-dataset` is rejected until identity verification exists; use an explicit dataset path instead. Repeated runs can therefore perform new provider work: obtain the required live-run/budget approval first. Fresh attempts alone are not controlled benchmark timing or verified comparisons. See the [P2-B1 handoff](plans/migration/20261016-p2-b1-handoff.md) for the unverified index/semantic-identity boundary and isolated offline regression command.

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
dotenvx run -- uv run python -m src.cli.ingest --skip-download
dotenvx run -- uv run python -m src.cli.serve
cd frontend && npm run dev
```

### Full corpus refresh

```bash
dotenvx run -- uv run python -m src.cli.ingest
dotenvx run -- uv run python -m src.cli.serve
cd frontend && npm run dev
```

### Regression check before sharing changes

```bash
dotenvx run -- uv run python -m src.cli.ingest --skip-download
dotenvx run -- uv run python -m src.cli.eval_pipeline --config experiments/v1/baseline.yaml --all-variants
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
