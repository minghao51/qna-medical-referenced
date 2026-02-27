# RAG System: Runtime Retrieval and Offline Ingestion

This document separates the system into two flows:

- Runtime retrieval/generation (serving user requests)
- Offline ingestion/indexing (building and refreshing the corpus)

## Runtime Flow (`/chat` request)

```text
HTTP POST /chat
  -> src.app.routes.chat
  -> src.usecases.chat.process_chat_message
  -> src.rag.runtime.retrieve_context(...) or retrieve_context_with_trace(...)
  -> src.ingestion.indexing.vector_store.VectorStore.similarity_search(...)
  -> src.infra.llm.gemini_client.GeminiClient.generate(...)
  -> response + sources (+ optional pipeline trace)
```

### Runtime Modules

- `src.app.factory` - FastAPI app setup and lifespan initialization
- `src.app.routes.chat` - request handler for `/chat`
- `src.usecases.chat` - orchestration and history persistence
- `src.rag.runtime` - retrieval, runtime index initialization, trace assembly
- `src.rag.trace_models` - Pydantic models for the pipeline trace response
- `src.infra.llm.gemini_client` - Gemini generation client
- `src.infra.storage.chat_history_store` - local JSON chat history storage

## Offline Ingestion / Indexing Flow

```text
src.cli.ingest
  -> src.ingestion.pipeline.run_pipeline(...)
  -> steps.download_web (optional)
  -> steps.convert_html (optional/forced)
  -> steps.load_pdfs
  -> steps.chunk_text
  -> steps.load_reference_data
  -> indexing.vector_store.add_documents(...)
  -> src.rag.runtime.initialize_runtime_index(...)
```

### Ingestion Modules

- `src.ingestion.steps.download_web` - downloads source HTML pages to `data/raw`
- `src.ingestion.steps.convert_html` - HTML to Markdown conversion in `data/raw`
- `src.ingestion.steps.load_pdfs` - PDF extraction from `data/raw`
- `src.ingestion.steps.chunk_text` - chunk generation for retrieval/indexing
- `src.ingestion.steps.load_reference_data` - CSV reference range loading
- `src.ingestion.indexing.vector_store` - hybrid retrieval index and embedding persistence
- `src.ingestion.indexing.persistence` - JSON persistence under `data/vectors`
- `src.ingestion.indexing.search` - ranking and scoring helpers
- `src.ingestion.indexing.keyword_index` - keyword/TF-IDF helpers
- `src.ingestion.indexing.embedding` - embedding helper wrapper around Gemini embed API
- `src.ingestion.indexing.text_utils` - tokenization/sanitization helpers

## Data and Path Ownership

Canonical path resolution is centralized in `src.config.paths`.

Defaults remain compatible:

- Raw data: `data/raw`
- Vector store JSON: `data/vectors`
- Chat history: `data/chat_history.json`
- Rate-limit SQLite DB: `data/rate_limits.db`

## Compatibility and Migration Notes

Legacy `src.pipeline.L0_*` ... `L6_*` wrapper modules have been removed.
Use the canonical modules above for all new development and documentation.

## Verification Checklist (Current Structure)

- Runtime retrieval code lives under `src/rag`.
- Offline ingestion code lives under `src/ingestion`.
- HTTP layer lives under `src/app`.
- Config and paths live under `src/config`.
- Some legacy wrappers still exist for transition compatibility, but not the old `src.pipeline.L0_*` ... `L6_*` stage modules.
