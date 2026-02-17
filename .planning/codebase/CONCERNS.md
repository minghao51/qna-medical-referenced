# Codebase Concerns

## Resolved Issues

- ✅ Tests now exist (64 tests across 6 files)
- ✅ Configuration class added (`src/config/settings.py`)
- ✅ Middleware added (auth, rate limit, request ID)
- ✅ Retry logic added to LLM client
- ✅ No longer using langchain (removed unused dependencies)

## Remaining Concerns

### High Priority

**Hardcoded API Key**
- `.env` contains `GEMINI_API_KEY`
- Must not be committed to version control

**No Authentication**
- API endpoints publicly accessible
- `APIKeyMiddleware` validates `X-API-Key` header but not enforced

**No Rate Limiting (fully implemented)**
- `RateLimitMiddleware` exists but needs tuning

### Medium Priority

**Global Mutable State**
- `_vector_store_initialized` flag in `src/rag/retriever.py`
- `_vector_store` singleton in `src/vectorstore/store.py`
- Not thread-safe

**JSON File Storage**
- Entire vector store loaded into memory
- No concurrent access protection

**Duplicate PDF Loading**
- `PDFLoader.load_all_pdfs()` in `src/ingest/__init__.py`
- `ReferenceDataLoader.load_pdfs_text()` in `src/rag/retriever.py`

### Low Priority

**Missing Type Hints**
- Some functions lack complete type annotations

**No Graceful Degradation**
- If Gemini API fails, entire app fails
- No fallback to keyword-only search

**LSP Warnings**
- NLTK imports show as unresolved (runtime works)
- Possible None reference in store.py:184

## Performance Concerns

- No embedding caching for repeated queries
- Batch size of 10 for embeddings is small
- Index rebuilt on every document add (marked dirty flag helps)

## Documentation Gaps

- No API documentation beyond FastAPI auto-docs
- Some functions lack docstrings
