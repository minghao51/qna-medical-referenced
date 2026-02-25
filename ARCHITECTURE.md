# Architecture Note

This file is now a short redirect to the maintained architecture docs in `docs/architecture/`.

Start here:

- `docs/architecture/overview.md` - repository/backend structure map
- `docs/architecture/rag-system.md` - runtime retrieval + offline ingestion data flow

Compatibility note:

- Legacy modules under `src/pipeline/`, `src/main.py`, and `src/run.py` are preserved as temporary wrappers.
- Canonical backend code now lives under `src/app`, `src/usecases`, `src/rag`, `src/ingestion`, `src/infra`, and `src/config`.
