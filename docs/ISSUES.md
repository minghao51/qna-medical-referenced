# Issue Tracker — Critical & High Priority

**Generated:** 2026-04-06  
**Source:** `.planning/codebase/CONCERNS.md` audit

---

## P0 — Critical (Fix Immediately)

### P0-1: `except: pass` blocks swallowing errors completely
- **Risk:** Critical — Silent failures in HTML conversion, dataset building, and chat; bugs are invisible in production
- **Effort:** 1h
- **Files:** `src/ingestion/steps/convert_html.py:34-35,39-40`, `src/evals/dataset_builder.py:345`, `src/usecases/chat.py:227`
- **Fix:** Replace each `except Exception: pass` with `except Exception as e: logger.warning("Failed to X: %s", e)`. Add `import logging; logger = logging.getLogger(__name__)` at top of each file if missing.

### P0-2: API key auth uses non-timing-safe string comparison
- **Risk:** Critical — Vulnerable to timing attacks; no rate limiting per key; no key rotation
- **Effort:** 2h
- **Files:** `src/app/middleware/auth.py:48-69`, `src/app/security.py`
- **Fix:** (1) Replace `record.matches(api_key)` with `hmac.compare_digest` in `APIKeyRecord.matches()`. (2) Add per-key rate limiting using a dict `{key: [timestamps]}` with sliding window. (3) Add `created_at` and `expires_at` fields to key config. (4) Log each auth attempt with key prefix (first 4 chars) for audit.

### P0-3: Race condition in vector store initialization
- **Risk:** Critical — Under concurrent requests, two threads can both see `_vector_store_initialized=False` and rebuild the index simultaneously, corrupting ChromaDB state
- **Effort:** 3h
- **Files:** `src/rag/runtime.py:46-47,214-249`
- **Fix:** Replace the two module-level globals with a `threading.Lock()` + double-checked locking pattern. See detailed fix in `src/rag/runtime.py`.

### P0-4: In-memory vector store — large collections exceed RAM
- **Risk:** Critical — ChromaDB `PersistentClient` loads all documents into memory on every `_get_all_documents()` call. At ~10K+ chunks this will OOM
- **Effort:** 2h (Docker server mode)
- **Files:** `src/ingestion/indexing/chroma_store.py`, `docker-compose.yml` (new)
- **Fix:** Migrate to ChromaDB server mode via Docker. Replace `PersistentClient` with `HttpClient(host="localhost", port=8000)`. Add `docker-compose.yml` with volume mount for persistence. Solves concurrency AND provides a path to scale.

---

## P1 — High (Fix Within Sprint)

### P1-1: Module-level global state for config (7 modules)
- **Risk:** High — Race conditions, test pollution, non-deterministic behavior
- **Effort:** 6h
- **Files:** `src/rag/runtime.py`, `src/ingestion/steps/convert_html.py`, `src/ingestion/steps/chunking/config.py`, `src/ingestion/steps/load_pdfs.py`, `src/ingestion/steps/load_markdown.py`, `src/rag/reranker.py`, `src/infra/di.py`
- **Fix:** Create a `RuntimeContext` dataclass in `src/config/context.py` that holds all runtime config. Replace all `global X` + setter functions with a single `get_context()` / `set_context(ctx)` pair. Wire through `src/infra/di.py`.

### P1-2: 63 instances of `except Exception:` without logging
- **Risk:** High — Silent failures across LLM calls, file I/O, evaluation
- **Effort:** 8h
- **Files:** All modules under `src/`, notably `src/app/routes/evaluation.py`, `src/usecases/chat.py`, `src/evals/assessment/orchestrator.py`
- **Fix:** Phase 1 (quick win): Add `logger.exception("...")` inside every bare `except` block. Phase 2 (proper): Replace with specific exception types — `json.JSONDecodeError`, `FileNotFoundError`, `httpx.HTTPError`, etc.

### P1-3: ChromaDB `_get_all_documents()` loads entire collection per search
- **Risk:** High — Every search triggers full collection fetch + BM25 index rebuild
- **Effort:** 4h
- **Files:** `src/ingestion/indexing/chroma_store.py:221-233`
- **Fix:** Maintain keyword index incrementally: update in `add_documents()`, remove in `delete_document()`. Only do full rebuild on `clear()`.

### P1-4: `_diversify_results` fallback defeats diversity constraints
- **Risk:** High — Fill loop adds back duplicates by ID only, ignoring source/page limits
- **Effort:** 1h
- **Files:** `src/rag/runtime.py:492-502`
- **Fix:** Accept fewer results when constraints are too strict. Log warning: `logger.warning("Only %d/%d results after diversity constraints", len(selected), top_k)`.

### P1-5: Pin deepeval to specific minor version
- **Risk:** High — Transitive dependency conflicts can break `uv sync`
- **Effort:** 15m
- **Files:** `pyproject.toml`
- **Fix:** Change `deepeval>=2.0.0` to `deepeval>=2.0.0,<2.1.0`.

### P1-6: Concurrent access to global state untested
- **Risk:** High — No test coverage for race conditions
- **Effort:** 3h
- **Files:** New: `tests/test_concurrent_access.py`
- **Fix:** Add tests with `ThreadPoolExecutor` spawning 10 threads calling `initialize_vector_store()` concurrently.

---

## Summary

| Priority | Count | Total Effort |
|----------|-------|-------------|
| **P0** | 4 | ~8h |
| **P1** | 6 | ~22h |
