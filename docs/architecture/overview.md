# Backend Architecture Overview

This document describes the current backend structure after the package cleanup.

## Goals of the Layout

- Make responsibilities obvious to a new contributor.
- Separate runtime query serving from offline ingestion/indexing.
- Keep behavior and data paths stable.

## Current Backend Package Map

```text
src/
  app/                    # HTTP layer only
    factory.py            # FastAPI app creation + lifespan wiring
    routes/               # Route handlers by endpoint area
    schemas/              # Request/response models for HTTP APIs
    middleware/           # API key, rate limit, request id middleware

  usecases/               # Orchestration / business flows
    chat.py               # chat request -> retrieve -> generate -> persist
    pipeline.py           # offline pipeline orchestration + runtime refresh

  rag/                    # Runtime retrieval path
    runtime.py            # index init + retrieve_context(+trace)
    trace_models.py       # response trace models
    formatting.py         # source/context formatting helpers

  ingestion/              # Offline ingestion/indexing internals
    pipeline.py           # compatibility shim to usecases.pipeline
    steps/                # download/convert/load/chunk/reference steps
    indexing/             # vector store + embedding/search/persistence helpers

  infra/                  # External systems/infrastructure adapters
    llm/qwen_client.py
    storage/chat_history_store.py

  config/                 # Settings and path ownership
    settings.py
    paths.py

  cli/                    # Canonical command entrypoints
    serve.py
    ingest.py

```

## Runtime vs Offline Responsibilities

### Runtime (`src/app`, `src/usecases`, `src/rag`, `src/infra/llm`, `src/infra/storage`)

Used when serving `/chat` requests.

Flow:

1. `src.app.routes.chat` receives the request.
2. `src.usecases.chat.process_chat_message` orchestrates retrieval + generation + history persistence.
3. `src.rag.runtime` retrieves context from the vector store.
4. `src.infra.llm.qwen_client.QwenClient` generates the answer.
5. `src.infra.storage.chat_history_store` stores conversation history.

### Offline ingestion (`src.ingestion`)

Used when preparing/refreshing the corpus and vector index.

Flow:

1. `src.usecases.pipeline.run_pipeline()` orchestrates the refresh
2. `src.ingestion.steps.download_web` (optional web downloads)
3. `src.ingestion.steps.convert_html` (HTML -> Markdown)
4. `src.ingestion.steps.load_pdfs`
5. `src.ingestion.steps.chunk_text`
6. `src.ingestion.steps.load_reference_data`
7. `src.ingestion.indexing.vector_store` (embedding + persistence)
8. `src.rag.runtime.initialize_runtime_index()` confirms runtime index availability

## Configuration Ownership

- `src.config.settings` is the source of runtime settings (API keys, model names, limits, data dirs).
- `src.config.paths` is the source of filesystem paths (`data/raw`, `data/vectors`, `data/chat_history.json`, rate limit DB).
- Canonical modules should not read environment variables directly with `os.getenv()`.

## Canonical Commands

```bash
uv run python -m src.cli.serve
uv run python -m src.cli.ingest
```

---

# Frontend Architecture

The frontend is a SvelteKit application that provides the user interface for the medical Q&A system.

## Technology Stack

- **Framework:** SvelteKit 2.50.2 with Svelte 5
- **Language:** TypeScript
- **Build:** Vite 7.3.1
- **Testing:** Playwright (E2E)
- **Charts:** Chart.js 4.x

## Routes

| Route | Description |
|-------|-------------|
| `/` | Chat interface with pipeline toggle |
| `/eval` | Evaluation dashboard with metrics and historical trending |

## Key Components

### Confidence Indicators (Phase 1)

| Component | File | Description |
|-----------|------|-------------|
| `ConfidenceBadge.svelte` | `frontend/src/lib/components/` | Color-coded confidence level badges (high/medium/low) |
| `MetricBar.svelte` | `frontend/src/lib/components/` | Visual progress bar for scores |
| `SourceQualityIndicator.svelte` | `frontend/src/lib/components/` | Domain credibility badges (.gov, .edu, .org, .com) |
| `health-score.ts` | `frontend/src/lib/utils/` | Client-side confidence scoring logic |

### Document Inspection (Phase 2)

| Component | File | Description |
|-----------|------|-------------|
| `DocumentInspector.svelte` | `frontend/src/lib/components/` | Modal for full document view with metadata |
| `PipelinePanel.svelte` | `frontend/src/lib/components/` | Enhanced with clickable documents |

### Visual Flow Diagrams (Phase 3)

| Component | File | Description |
|-----------|------|-------------|
| `FlowNode.svelte` | `frontend/src/lib/components/` | Individual pipeline stage node |
| `PipelineFlowDiagram.svelte` | `frontend/src/lib/components/` | Animated pipeline flow visualization |

### Historical Trending (Phase 4)

| Component | File | Description |
|-----------|------|-------------|
| `MetricChart.svelte` | `frontend/src/lib/components/` | Reusable Chart.js wrapper |
| `eval/+page.svelte` | `frontend/src/routes/` | Enhanced with historical charts |

## Data Flow

```
API Response → Confidence Calculator → Visual Components
                                        ↓
                              PipelinePanel → DocumentInspector
                                        ↓
                              PipelineFlowDiagram
                                        ↓
                              MetricChart (historical)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Send chat message |
| `/chat?include_pipeline=true` | POST | Chat with pipeline data |
| `/history/{session_id}` | GET | Load chat history |
| `/evaluation/latest` | GET | Latest evaluation metrics |
| `/evaluation/history?limit=10` | GET | Historical evaluation data |

## Confidence Calculation

Client-side confidence scoring (0-100):

- **Retrieval Score (40%)** - Average document similarity scores
- **Source Quality (30%)** - .gov/.edu > .org > .com
- **Context Relevance (20%)** - Chunk count and coverage
- **Generation Success (10%)** - No errors, reasonable token count

## Running the Frontend

```bash
cd frontend
bun run dev    # Development server on http://localhost:5173
bun run build  # Production build
bun run test   # Playwright E2E tests
```
