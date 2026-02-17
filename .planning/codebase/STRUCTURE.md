# Directory Structure

## Root Layout

```
qna_medical_referenced/
├── src/                    # Source code
├── data/                   # Data files
├── tests/                  # Test files
├── .planning/codebase/     # Planning docs
├── docs/                   # Documentation
├── pyproject.toml          # Python project config
├── uv.lock                 # Locked dependencies
├── .env                    # Environment variables
├── .gitignore
├── ARCHITECTURE.md         # Project documentation
├── README.md
├── CLAUDE.md              # AI assistant instructions
└── docs/                  # Documentation files
```

## Source Code (`src/`)

```
src/
├── main.py                # FastAPI app, entry point
├── run.py                 # Dev server runner
├── main_debug.py          # Debug runner
├── __init__.py
├── config/
│   ├── __init__.py
│   └── settings.py        # Configuration (Settings class)
├── ingest/
│   └── __init__.py        # PDFLoader, get_documents()
├── processors/
│   ├── __init__.py
│   └── chunker.py         # TextChunker, chunk_documents()
├── vectorstore/
│   ├── __init__.py
│   └── store.py           # VectorStore, get_vector_store()
├── rag/
│   ├── __init__.py
│   └── retriever.py       # retrieve_context, initialize_vector_store
├── llm/
│   ├── __init__.py
│   └── client.py          # GeminiClient, get_client()
└── middleware/
    ├── __init__.py
    ├── auth.py            # APIKeyMiddleware
    ├── rate_limit.py      # RateLimitMiddleware
    └── request_id.py      # RequestIDMiddleware
```

## Data (`data/`)

```
data/
├── vectors/               # Persisted embeddings
│   └── medical_docs.json  # Embedding + metadata storage
└── raw/                   # Source documents
    ├── LabQAR/
    │   └── reference_ranges.csv
    ├── *.pdf
```

## Tests (`tests/`)

```
tests/
├── __init__.py
├── conftest.py
├── test_chunker.py
├── test_keyword_index.py
├── test_retrieval.py
├── test_embedding.py
├── test_pdf_loader.py
└── test_settings.py
```

## Key Locations

| Purpose | File Path |
|---------|-----------|
| FastAPI app | `src/main.py` |
| Configuration | `src/config/settings.py` |
| Server runner | `src/run.py` |
| PDF loading | `src/ingest/__init__.py` |
| Text chunking | `src/processors/chunker.py` |
| Vector storage | `src/vectorstore/store.py` |
| RAG retrieval | `src/rag/retriever.py` |
| LLM client | `src/llm/client.py` |
| Embeddings file | `data/vectors/medical_docs.json` |
| Reference ranges | `data/raw/LabQAR/reference_ranges.csv` |

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Directory | lowercase, underscores | `vectorstore` |
| File | lowercase, underscores | `chunker.py` |
| Class | PascalCase | `VectorStore`, `TextChunker` |
| Function | snake_case | `get_client()`, `chunk_documents()` |
| Constants | UPPER_SNAKE | `MAX_RETRIES`, `EMBEDDING_MODEL` |
