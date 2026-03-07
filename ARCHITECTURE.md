# Architecture Note

This file is now a short redirect to the maintained architecture docs in `docs/architecture/`.

Start here:

- `docs/architecture/overview.md` - repository/backend structure map
- `docs/architecture/rag-system.md` - runtime retrieval + offline ingestion data flow

Architecture note:

- The codebase has been reorganized into clear layers:
  - `src/app` - HTTP layer (FastAPI routes, middleware, schemas)
  - `src/usecases` - Business logic orchestration
  - `src/rag` - Runtime retrieval and context generation
  - `src/ingestion` - Offline data pipeline and indexing
  - `src/infra` - External integrations (LLM clients, storage)
  - `src/config` - Settings and path configuration
  - `src/cli` - Command-line entry points
