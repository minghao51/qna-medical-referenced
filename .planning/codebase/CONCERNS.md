# CONCERNS.md - Tech Debt, Bugs, Security

## Tech Debt

### High Priority

1. **Vector Store Duplicate Code**
   - Location: `src/pipeline/L5_vector_store.py`, `src/vectorstore/store.py`
   - Issue: Two implementations of vector store exist
   - Fix: Consolidate into single implementation

2. **Missing Type Hints**
   - Location: Several pipeline files
   - Issue: Some functions lack complete type annotations
   - Fix: Add full type hints

3. **No Database for Chat History**
   - Location: `src/storage/chat_store.py`
   - Issue: JSON file not suitable for production with concurrent writes
   - Fix: Consider SQLite or PostgreSQL for chat history

4. **Hardcoded Weights**
   - Location: `src/pipeline/L5_vector_store.py`
   - Issue: Semantic (0.6), keyword (0.2), boost (0.2) hardcoded
   - Fix: Move to configuration

### Medium Priority

5. **In-Memory Vector Store Singleton**
   - Location: `src/pipeline/L5_vector_store.py:379`
   - Issue: Global singleton may cause memory issues with large datasets
   - Fix: Implement LRU cache or chunked loading

6. **No Cache for Gemini API**
   - Location: `src/llm/client.py`
   - Issue: Repeated queries re-hit API
   - Fix: Add response caching layer

7. **Error Messages Expose Details**
   - Location: `src/main.py:127`
   - Issue: Logs internal errors but generic message to client
   - Note: Current behavior is secure but could improve logging

8. **No Input Sanitization Beyond Basic**
   - Location: `src/main.py:40-45`
   - Issue: Only strips whitespace
   - Fix: Add more robust input validation

## Known Bugs

### Open Issues

1. **LSP Type Errors in Vector Store**
   - Severity: Low
   - Location: `src/pipeline/L5_vector_store.py:194,248`
   - Description: `Object of type "None" cannot be used as iterable value`
   - Impact: Type checking warnings, no runtime impact

2. **Duplicate Embedding on Restart**
   - Severity: Medium
   - Location: `src/pipeline/L5_vector_store.py`
   - Description: Re-adding documents on each server restart
   - Impact: Index grows with duplicates

3. **Rate Limiter Race Condition**
   - Severity: Low
   - Location: `src/middleware/rate_limit.py`
   - Description: SQLite + asyncio.Lock may have edge cases
   - Impact: Potential rate limit bypass under high concurrency

## Security

### Current Security Measures

1. **API Key Authentication**
   - Middleware validates `X-API-Key` header
   - Configurable via `API_KEYS` env var
   - Bypassed for health/docs endpoints

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
   - Gemini API client created per-request
   - Consider singleton client

3. **Synchronous PDF Loading**
   - L2 PDF loader is synchronous
   - Blocks event loop on large PDFs
   - Consider async implementation
