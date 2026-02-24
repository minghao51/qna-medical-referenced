# STRUCTURE.md - Directory Layout, Key Locations

## Project Root

```
qna_medical_referenced/
├── .planning/codebase/     # Documentation (generated)
├── data/                   # Data storage
│   ├── raw/               # Raw source files (HTML, PDF, CSV)
│   ├── vectors/           # Vector store (JSON)
│   ├── chat_history.json  # Chat sessions
│   └── rate_limits.db     # SQLite rate limits
├── src/                   # Backend source code
├── frontend/              # Frontend (SvelteKit)
├── tests/                 # Backend tests
├── docs/                  # Project documentation
├── docker-compose.yml     # Container orchestration
├── pyproject.toml         # Python dependencies
└── README.md              # Project overview
```

## Backend Structure (`src/`)

```
src/
├── main.py                    # FastAPI app, endpoints
├── run.py                     # Entry point
├── main_debug.py              # Debug entry point
├── models.py                  # Pydantic models
├── config/
│   └── settings.py            # Configuration (Pydantic Settings)
├── pipeline/                 # Data processing pipeline (L0-L6)
│   ├── __init__.py
│   ├── run_pipeline.py        # Pipeline orchestrator
│   ├── L0_download.py         # Download HTML from web
│   ├── L1_html_to_md.py       # Convert HTML → Markdown
│   ├── L2_pdf_loader.py       # Load PDF documents
│   ├── L3_chunker.py          # Chunk text (800 char)
│   ├── L4_reference_loader.py # Load CSV reference data
│   ├── L5_vector_store.py     # Embeddings + hybrid search
│   └── L6_rag_pipeline.py     # RAG initialization + retrieval
├── llm/
│   └── client.py              # Google Gemini client
├── middleware/
│   ├── __init__.py
│   ├── auth.py                # API key authentication
│   ├── rate_limit.py          # Rate limiting (SQLite)
│   └── request_id.py         # Request ID middleware
├── storage/
│   ├── __init__.py
│   └── chat_store.py          # Chat history (JSON file)
└── vectorstore/
    └── __init__.py            # (Legacy, L5_vector_store used)
```

## Frontend Structure (`frontend/`)

```
frontend/
├── src/
│   ├── app.html              # HTML template
│   ├── app.d.ts               # Type declarations
│   ├── lib/
│   │   ├── index.ts           # Library exports
│   │   ├── types.ts           # TypeScript types
│   │   └── components/
│   │       ├── PipelinePanel.svelte  # Pipeline trace display
│   │       └── StepCard.svelte       # Step card component
│   └── routes/
│       ├── +layout.svelte     # Layout component
│       └── +page.svelte       # Main chat page
├── tests/
│   ├── chat.spec.ts           # Chat E2E tests
│   └── pipeline.spec.ts       # Pipeline E2E tests
├── package.json
├── svelte.config.js
├── vite.config.ts
├── tsconfig.json
└── Dockerfile
```

## Key Locations

| Purpose | Location |
|---------|----------|
| API endpoints | `src/main.py` |
| LLM client | `src/llm/client.py` |
| Vector store | `src/pipeline/L5_vector_store.py` |
| RAG pipeline | `src/pipeline/L6_rag_pipeline.py` |
| Pipeline runner | `src/pipeline/run_pipeline.py` |
| Chat storage | `src/storage/chat_store.py` |
| Config | `src/config/settings.py` |
| Frontend entry | `frontend/src/routes/+page.svelte` |

## Data Locations

| Data | Location |
|------|----------|
| Raw HTML/PDF | `data/raw/*.html`, `data/raw/*.pdf` |
| Vector index | `data/vectors/medical_docs.json` |
| Chat history | `data/chat_history.json` |
| Rate limits | `data/rate_limits.db` |
| Reference ranges | `data/raw/LabQAR/reference_ranges.csv` |

## Test Locations

| Tests | Location |
|-------|----------|
| Backend unit tests | `tests/test_*.py` |
| Frontend E2E | `frontend/tests/*.spec.ts` |
| Test fixtures | `tests/fixtures/` |

## Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Python dependencies, pytest, ruff config |
| `frontend/package.json` | Node dependencies |
| `docker-compose.yml` | Multi-container setup |
| `.env.example` | Environment template |
| `.gitignore` | Git ignore rules |
