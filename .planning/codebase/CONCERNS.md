# CONCERNS.md - Tech Debt, Bugs, Security

## Tech Debt

### High Priority

1. **Missing Type Hints**
   - Location: Several ingestion and RAG files
   - Issue: Some functions lack complete type annotations
   - Fix: Add full type hints

2. **No Database for Chat History**
   - Location: `src/infra/storage/chat_history_store.py`
   - Issue: JSON file not suitable for production with concurrent writes
   - Fix: Consider SQLite or PostgreSQL for chat history

3. **Hardcoded Weights**
   - Location: `src/ingestion/indexing/vector_store.py`
   - Issue: Semantic (0.6), keyword (0.2), boost (0.2) hardcoded
   - Fix: Move to configuration

### Medium Priority

4. **In-Memory Vector Store Singleton**
   - Location: `src/rag/runtime.py`
   - Issue: Global singleton may cause memory issues with large datasets
   - Fix: Implement LRU cache or chunked loading

5. **No Cache for Qwen API**
   - Location: `src/infra/llm/qwen_client.py`
   - Issue: Repeated queries re-hit API
   - Fix: Add response caching layer

6. **Error Messages Expose Details**
   - Location: `src/app/routes/chat.py`
   - Issue: Logs internal errors but generic message to client
   - Note: Current behavior is secure but could improve logging

7. **No Input Sanitization Beyond Basic**
   - Location: `src/app/schemas/chat.py`
   - Issue: Only strips whitespace
   - Fix: Add more robust input validation

## Known Bugs

### Open Issues

1. **LSP Type Errors in Vector Store**
   - Severity: Low
   - Location: `src/ingestion/indexing/vector_store.py`
   - Description: Type checking warnings in some edge cases
   - Impact: Type checking warnings, no runtime impact

2. **Duplicate Embedding on Restart**
   - Severity: Medium
   - Location: `src/ingestion/indexing/vector_store.py`
   - Description: Re-adding documents on each server restart if not properly deduplicated
   - Impact: Index grows with duplicates
   - Mitigation: Use unique document IDs

3. **Rate Limiter Race Condition**
   - Severity: Low
   - Location: `src/app/middleware/rate_limit.py`
   - Description: SQLite + asyncio.Lock may have edge cases
   - Impact: Potential rate limit bypass under high concurrency

## Security

### Current Security Measures

1. **API Key Authentication**
   - Middleware validates `X-API-Key` header
   - Configurable via `API_KEYS` env var
   - Bypassed for health endpoints

2. **Rate Limiting**
   - Per-API-key or per-IP limit: 60 req/min
   - SQLite-backed tracking

3. **Input Validation**
   - Pydantic models for request validation
   - Max message length: 2000 chars

4. **No PII in Logs**
   - Error messages sanitized
   - No stack traces exposed

### Potential Security Improvements

1. **HTTPS Only**
   - Not enforced in development
   - Add in production deployment

2. **API Key Rotation**
   - Not implemented
   - Add key rotation mechanism

3. **Request Size Limits**
   - Max 2000 chars enforced
   - Consider adding file upload limits

## Performance Concerns

1. **Large Embedding Files**
   - Vector store is JSON-based
   - Loads entire index into memory
   - Consider chunked loading for scale

2. **No Connection Pooling**
   - Qwen API client created per-request
   - Consider singleton client

3. **Synchronous PDF Loading**
   - PDF loader is synchronous
   - Blocks event loop on large PDFs
   - Consider async implementation

## Resolved Issues

The following issues have been resolved by architectural changes:

1. ~~**Duplicate Vector Store Code**~~ - RESOLVED
   - Old: `src/pipeline/L5_vector_store.py`, `src/vectorstore/store.py`
   - New: Single implementation in `src/ingestion/indexing/vector_store.py`
   - Runtime access via `src/rag/runtime.py`

2. ~~**Legacy Pipeline Modules**~~ - RESOLVED
   - Old: `src/pipeline/` with L0-L6 modules
   - New: `src/ingestion/` and `src/rag/` with clear separation
   - Offline ingestion and runtime retrieval properly separated

3. ~~**Scattered Middleware**~~ - RESOLVED
   - Old: `src/middleware/`
   - New: `src/app/middleware/` with proper HTTP layer organization
