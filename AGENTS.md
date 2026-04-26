## 1. Workflow
- **Analyze First:** Read relevant files before proposing solutions. Never hallucinate.
- **Approve Changes:** Present a plan for approval before modifying code.
- **Minimal Scope:** Change as little code as possible. No new abstractions.

## 2. Output Style
- High-level summaries only.
- No speculation about code you haven't read.

## 3. Technical Stack
- **Python:**
  - Package manager: `uv`.
  - Execution: Always `uv run <command>`. Never `python`.
  - Installing package : `uv add`
  - Sync: `uv sync`.
- **Frontend:**
  - Verify: Run `npm run check` and `npm test` after changes.
- **Files:** Markdown files must follow `YYYYMMDD-filename.md` format.
- **Docker:** `dotenvx run -- docker-compose up` for runs requiring api keys etc.

## 4. Project Structure

```
src/
  app/          FastAPI routes, schemas, middleware, security
  config/       Settings (pydantic-settings), paths
  rag/          RAG runtime — retrieval, query understanding, chunking dispatch
  ingestion/    Document pipeline — extractors, chunkers, vector store (ChromaDB)
  evals/        Evaluation framework — assessment orchestrator, metrics, dataset builder
  experiments/  Experiment runner — feature addition, ablation, comparison reports
  services/     Business logic services (evaluation_service)
  usecases/     Application use cases
  cli/          CLI entry points
experiments/    YAML configs + outputs (JSON/MD reports)
data/           Runtime data — chroma/, vectors/, evals/, raw/, processed/
tests/          pytest suite (431 tests). Fixtures in tests/fixtures/
frontend/       SvelteKit 5 + TypeScript + Playwright E2E
scripts/        Utility scripts (benchmarks, ablations, cleanup)
docs/           Project documentation
```

## 5. Key Patterns

- **RAG pipeline:** `ingestion/` handles extraction → chunking → embedding → ChromaDB index. `rag/runtime.py` handles retrieval with configurable strategies (rrf_hybrid, semantic_only, bm25_only).
- **Evaluation:** `evals/assessment/orchestrator.py` runs full assessment pipeline (L0-L6). Uses DeepEval for answer quality. Stage functions injected via `pipeline_assessment.py` facade.
- **Experiments:** Feature addition experiments defined in YAML (`experiments/*.yaml`), run via `src/experiments/run_addition.py`. Results in `experiments/outputs/`.
- **Vector store:** ChromaDB with local JSON snapshots in `data/vectors/`. `chroma_store.py` manages in-memory index + lazy embedding loading.
- **Config:** `src/config/settings.py` loads from env vars. Experiments override via `configure_runtime_for_experiment()`.

## 6. Testing

- **Backend:** `uv run python -m pytest` — ~495 tests. Markers: `live_api`, `deepeval`, `e2e_real_apis`, `slow`.
- **Frontend:** `cd frontend && npm run check` (type check) + `npm test` (Playwright).
- **Linting:** `uv run ruff check` (line-length 100, target py312).

## 7. Environment

- **API keys:** Managed via `.env` file. Always prefix commands with `dotenvx run --` when API access needed.
