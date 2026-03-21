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
      hype.py             # HyPE (index-time query expansion)
    indexing/             # vector store + embedding/search/persistence helpers

  evals/                  # Pipeline quality assessment
    pipeline_assessment.py # full-pipeline evaluation orchestration
    step_checks.py        # stage-specific quality metrics
    metrics.py            # ranked IR metrics (HitRate@k, MRR, nDCG)
    dataset_builder.py    # evaluation dataset construction
    artifacts.py          # artifact persistence and retrieval
    schemas.py            # evaluation data models

  infra/                  # External systems/infrastructure adapters
    llm/qwen_client.py
    storage/chat_history_store.py

  config/                 # Settings and path ownership
    settings.py
    paths.py

  cli/                    # Canonical command entrypoints
    serve.py
    ingest.py
    eval_pipeline.py      # evaluation CLI

```

## Runtime vs Offline Responsibilities

### Runtime (`src/app`, `src/usecases`, `src/rag`, `src/infra/llm`, `src/infra/storage`)

Used when serving `/chat` requests.

Flow:

1. `src.app.routes.chat` receives the request.
2. `src.usecases.chat.process_chat_message` orchestrates retrieval + generation + history persistence.
3. `src.rag.runtime` retrieves context from the vector store (with multi-turn context building).
4. `src.infra.llm.qwen_client.QwenClient` generates the answer.
5. `src.infra.storage.chat_history_store` stores conversation history (session-based for multi-turn).

### Offline ingestion (`src.ingestion`)

Used when preparing/refreshing the corpus and vector index.

Flow:

1. `src.usecases.pipeline.run_pipeline()` orchestrates the refresh
2. `src.ingestion.steps.download_web` (optional web downloads)
3. `src.ingestion.steps.convert_html` (HTML -> Markdown)
4. `src.ingestion.steps.load_pdfs`
5. `src.ingestion.steps.chunk_text`
6. `src.ingestion.steps.hype` (HyPE query expansion - index-time hypothetical question generation)
7. `src.ingestion.steps.load_reference_data`
8. `src.ingestion.indexing.vector_store` (embedding + persistence)
9. `src.rag.runtime.initialize_runtime_index()` confirms runtime index availability

### Evaluation system (`src.evals`, `src.app.routes.evaluation`)

Used for assessing pipeline quality and tracking metrics over time.

Components:
- `src.evals.pipeline_assessment` - orchestrates quality assessment across all pipeline stages
- `src.evals.step_checks` - stage-specific quality metrics (download, HTML conversion, PDF extraction, chunking, indexing, retrieval)
- `src.evals.metrics` - ranked IR metrics (HitRate@k, Recall@k, MRR, nDCG)
- `src.evals.dataset_builder` - builds evaluation datasets from fixtures and synthetic generation
- `src.evals.artifacts` - manages versioned evaluation artifacts on disk
- `src.cli.eval_pipeline` - CLI entrypoint for running evaluations
- Multi-turn evaluation with DeepEval's ConversationalGEval
- Golden conversations dataset (15 conversations across 4 categories)

Evaluation CLI:
```bash
uv run python -m src.cli.eval_pipeline
uv run python -m src.cli.eval_pipeline --variant ablation-test
```

Evaluation API endpoints:
- `GET /evaluation/latest` - latest evaluation run results
- `GET /evaluation/runs` - list all evaluation runs
- `GET /evaluation/history` - historical trending metrics
- `GET /evaluation/steps/{stage}` - metrics for specific pipeline stage

Artifacts are stored in `data/evals/<timestamp>_<slug>/` with:
- `summary.json` - aggregate metrics and findings
- `step_metrics.json` - per-stage quality metrics
- `retrieval_results.jsonl` - per-query retrieval traces
- Other stage-specific metrics files

See `docs/evaluation/pipeline_quality_assessment_plan.md` for the implemented evaluation spec.

## Configuration Ownership

- `src.config.settings` is the source of runtime settings (API keys, model names, limits, data dirs).
- `src.config.paths` is the source of filesystem paths (`data/raw`, `data/vectors`, `data/chat_history.json`, rate limit DB).
- Canonical modules should not read environment variables directly with `os.getenv()`.

## Canonical Commands

```bash
uv run python -m src.cli.serve          # Start API server
uv run python -m src.cli.ingest         # Run ingestion pipeline
uv run python -m src.cli.eval_pipeline  # Run evaluation assessment
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
- **Markdown:** svelte-markdown 0.4.1, highlight.js 11.9.0

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

### Markdown Rendering (Phase 5)

| Component | File | Description |
|-----------|------|-------------|
| `MarkdownRenderer.svelte` | `frontend/src/lib/components/` | Full markdown rendering with syntax highlighting |

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
| `/history` | GET | Load chat history for the current anonymous session |
| `/history` | DELETE | Clear chat history and rotate to a fresh anonymous session |
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
npm run dev    # Development server on http://localhost:5173
npm run build  # Production build
npm run test   # Playwright E2E tests
```

## Markdown Rendering

The application uses a custom `MarkdownRenderer` component for rendering chat message content with full markdown support.

**Technology:**
- svelte-markdown 0.4.1: Markdown parsing
- highlight.js 11.9.0: Code syntax highlighting with tree-shaking

**Features:**
- Tables with responsive scrolling
- Headings (H1-H6) with proper hierarchy
- Code blocks with syntax highlighting (Python, JavaScript, TypeScript, Bash, JSON, XML)
- Lists (ordered/unordered) with proper indentation
- Bold, italic, strikethrough, links, blockquotes
- Copy button for code blocks

**Security:**
- Built-in XSS sanitization via svelte-markdown
- Only safe HTML tags allowed
- No script execution or dangerous protocols

**Responsive Layout:**
- Max-width: 1400px (up from 800px)
- Optimal line length: 75ch on wide screens
- Mobile-optimized with scrollable tables
