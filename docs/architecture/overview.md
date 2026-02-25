# Backend Architecture Overview

This document describes the current backend structure after the package cleanup.

## Goals of the Layout

- Make responsibilities obvious to a new contributor.
- Separate runtime query serving from offline ingestion/indexing.
- Keep behavior and data paths stable during the transition.
- Preserve old import paths/commands temporarily via compatibility wrappers.

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

  rag/                    # Runtime retrieval path
    runtime.py            # index init + retrieve_context(+trace)
    trace_models.py       # response trace models
    formatting.py         # source/context formatting helpers

  ingestion/              # Offline pipeline + indexing internals
    pipeline.py           # end-to-end ingestion orchestration
    steps/                # download/convert/load/chunk/reference steps
    indexing/             # vector store + embedding/search/persistence helpers

  infra/                  # External systems/infrastructure adapters
    llm/gemini_client.py
    storage/chat_history_store.py

  config/                 # Settings and path ownership
    settings.py
    paths.py

  cli/                    # Canonical command entrypoints
    serve.py
    ingest.py

  compat/                 # Transitional compatibility exports (optional)
```

## Runtime vs Offline Responsibilities

### Runtime (`src/app`, `src/usecases`, `src/rag`, `src/infra/llm`, `src/infra/storage`)

Used when serving `/chat` requests.

Flow:

1. `src.app.routes.chat` receives the request.
2. `src.usecases.chat.process_chat_message` orchestrates retrieval + generation + history persistence.
3. `src.rag.runtime` retrieves context from the vector store.
4. `src.infra.llm.gemini_client.GeminiClient` generates the answer.
5. `src.infra.storage.chat_history_store` stores conversation history.

### Offline ingestion (`src.ingestion`)

Used when preparing/refreshing the corpus and vector index.

Flow:

1. `src.ingestion.steps.download_web` (optional web downloads)
2. `src.ingestion.steps.convert_html` (HTML -> Markdown)
3. `src.ingestion.steps.load_pdfs`
4. `src.ingestion.steps.chunk_text`
5. `src.ingestion.steps.load_reference_data`
6. `src.ingestion.indexing.vector_store` (embedding + persistence)
7. `src.rag.runtime.initialize_runtime_index()` confirms runtime index availability

## Configuration Ownership

- `src.config.settings` is the source of runtime settings (API keys, model names, limits, data dirs).
- `src.config.paths` is the source of filesystem paths (`data/raw`, `data/vectors`, `data/chat_history.json`, rate limit DB).
- Canonical modules should not read environment variables directly with `os.getenv()`.

## Compatibility Wrappers (Transition)

The following are preserved temporarily so external scripts do not break immediately:

- `src.main`
- `src.run`
- `src.pipeline.*`
- legacy package paths such as `src.llm`, `src.storage`, `src.services`, `src.middleware`, `src.api`

New code and docs should use canonical paths only.

## Canonical Commands

```bash
uv run python -m src.cli.serve
uv run python -m src.cli.ingest
```
