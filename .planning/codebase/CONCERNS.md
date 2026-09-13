# Codebase Concerns

**Analysis Date:** 2026-05-12

## Tech Debt

**Remaining God Module: `src/ingestion/indexing/chroma_store.py` (~1010 lines):**
- Issue: Single file with multiple responsibilities (ChromaDB client wrapper, embedding orchestration, hybrid search, persistence management)
- Files: `src/ingestion/indexing/chroma_store.py`
- Impact: Hard to test, maintain, or add features without risking regressions
- Note: The previous primary god module (`src/rag/runtime.py`) was successfully split from ~1425 → ~495 lines by extracting `index.py`, `config.py`, `diversification.py`, `query_expansion.py`, and `retrieval.py`

**Massive Code Duplication in Sync/Async Retrieval:**
- Issue: `retrieve_context_with_trace` and `retrieve_context_with_trace_async` share ~80% identical logic
- Files: `src/rag/runtime.py:919-1273` (check updated line numbers)
- Impact: Bug fixes must be applied in two places; easy to introduce inconsistencies
- Fix approach: Extract shared trace-building logic into a helper

**Mutable Module-Level Global State:**
- Issue: Multiple modules use `set_*()` functions mutating globals for runtime configuration
- Files: `src/ingestion/steps/convert_html.py`, `src/ingestion/steps/load_pdfs.py`, `src/ingestion/steps/load_markdown.py`, `src/rag/reranker.py`, `src/config/settings.py:284`
- Impact: Breaks thread safety, creates hidden coupling, fragile testing
- Fix approach: Consolidate runtime config into a `RuntimeConfig` dataclass passed explicitly

**Import-Time Side Effects:**
- Issue: Modules trigger side effects on import (Settings instantiation, env var mutations, app creation)
- Files: `src/config/__init__.py`, `src/config/settings.py:284`, `src/app/factory.py`, `src/evals/deepeval_models.py`, `src/infra/llm/litellm_client.py`
- Impact: Importing transitively causes env var leaks; complicates testing
- Fix approach: Lazy initialization or explicit dependency injection

**Circular Import in Chunking Module:**
- Issue: `chonkie_adapter` ↔ `medical_semantic` may create circular import
- Files: `src/ingestion/steps/chunking/chonkie_adapter.py`, `src/ingestion/steps/chunking/medical_semantic.py`
- Impact: Works via lazy imports but fragile
- Fix approach: Break cycle by moving shared types to a third module

**Broad Exception Handling (72+ instances):**
- Issue: Numerous `except Exception as` blocks across codebase
- Files: Concentrated in `src/evals/`, `src/infra/llm/`, `src/rag/runtime.py`, `src/usecases/`
- Impact: Errors swallowed silently, hard to debug
- Fix approach: Narrow exception types; add structured error categorization

---

## Previously Addressed Issues

**God Module: `src/rag/runtime.py`** — **Refactored (2026-04):**
- From ~1425 lines to ~495 lines
- Logic extracted to: `src/rag/index.py`, `src/rag/config.py`, `src/rag/diversification.py`, `src/rag/query_expansion.py`, `src/rag/retrieval.py`

**Settings God Object** — **Partially Refactored:**
- From ~590 lines to ~284 lines
- Nested config models added in `src/config/models/` (`ApiConfig`, `LLMConfig`, `StorageConfig`, `RetrievalConfig`)
- Config sources: `config/settings.yaml` + env vars (`APP__` prefix) + `.env`
- Legacy flat env var names supported via `_LEGACY_FIELD_MAP`

**Unused Variable in Chat Route** — **Fixed:**
- File: `src/app/routes/chat.py` — `GeneratorExit`/`CancelledError` handling improved

**Sync Retrieval Called in Async Context** — **Addressed:**
- `initialize_runtime_index_async` added for async contexts
- Some remaining `asyncio.run()` calls in `src/usecases/pipeline.py`

---

## Known Bugs

**`indexing_features` silently dropped by the vector-store factory (pre-existing, inherited by P3.2):**
- Symptoms: `ChromaVectorStoreFactory._normalize_runtime_config` keeps only
  collection/weights/embedding keys, so the `indexing_features` dict that
  `apply_runtime_config` writes (enable_hype, hype_* and enrichment knobs)
  never survives a read. The only consumer was the deleted rag-side builder
  (`_build_index_from_sources`), which therefore never saw experiment HyPE/
  enrichment overrides — on `main` too. `IngestionRunConfig.from_runtime_state`
  (P3.2) reads the same (empty) source, preserving behavior bug-for-bug.
- Files: `src/ingestion/indexing/factory.py`, `src/ingestion/runtime_config.py`
- Fix approach (deferred): thread an explicit features dict from
  `apply_runtime_config` into `run_ingestion` instead of piggybacking on the
  store config; must ship with its own eval-parity story since enabling it
  changes runtime index behavior vs today.

**Sync Retrieval Called in Async Context (partial):**
- Symptoms: `asyncio.run()` called inside potentially async event loops
- Files: `src/usecases/pipeline.py`
- Workaround: Ensure async routes use async variants

---

## Security Considerations

**Legacy Unsalted SHA256 for API Key Verification:**
- Risk: `src/app/security.py` uses SHA256 without salt; vulnerable to rainbow table attacks
- Current mitigation: `bcrypt` preferred (12 rounds), SHA256 is legacy; `hmac.compare_digest` provides timing-safe comparison
- Recommendations: Add telemetry for legacy hash usage; set migration deadline

**Environment Variable Leakage:**
- Risk: API keys set to `os.environ` accessible to any library that reads env vars
- Files: `src/config/settings.py`, `src/evals/deepeval_models.py`, `src/infra/llm/litellm_client.py`
- Recommendations: Pass API keys explicitly to clients

**.env File Tracking:**
- Risk: `.env` committed with encryption (dotenvx); `.env.keys` (private keys) in `.gitignore`
- Recommendations: Defense-in-depth; ensure `.env.keys` never committed

**CORS Overly Permissive:**
- Risk: `allow_methods=["*"]` and `allow_headers=["*"]` in production
- Files: `src/app/factory.py`
- Recommendations: Restrict methods/headers for non-dev environments

**Subprocess Call in Evaluation:**
- Risk: `subprocess.run(["git", "rev-parse", "HEAD"])` at `src/evals/assessment/reporting.py`
- Current mitigation: Hardcoded command, safe
- Recommendations: Flag for audit

---

## Performance Bottlenecks

**O(n²) MMR Diversification:**
- Problem: `mmr_rerank` iterates over all candidates, computing similarity against every selected item; strings tokenized from scratch each time
- Files: `src/rag/diversification.py` (extracted from `runtime.py`)
- Cause: No caching of token sets or similarity scores
- Improvement path: Pre-compute tokens once; cache similarity scores; use approximate methods for large sets

**Sequential Vector Searches:**
- Problem: Each expanded query triggers separate sequential search
- Files: `src/rag/runtime.py`
- Improvement path: Use `asyncio.gather` for parallel searches

**No Tokenization Caching:**
- Problem: `_content_similarity` tokenizes strings on every call during MMR
- Files: `src/rag/diversification.py`
- Improvement path: Pre-compute token sets once per retrieval request

---

## Fragile Areas

**Mixed Sync/Async Patterns:**
- Why fragile: Both sync and async versions of nearly every function; sync called from async context causes event loop blocking
- Safe modification: Standardize on async for web layer; keep sync only for CLI/offline tools
- Files: `src/rag/runtime.py`, `src/usecases/chat.py`

**Large Files with Many Responsibilities:**
- Why fragile: `chroma_store.py` (~1010L), `retrieval_eval.py` (~765L), `orchestrator.py` (~645L)
- Safe modification: Extract specific responsibilities before adding features
- Files: `src/ingestion/indexing/chroma_store.py`, `src/evals/assessment/retrieval_eval.py`, `src/evals/assessment/orchestrator.py`

**Settings with Legacy Flat Field Mapping:**
- Why fragile: 58 legacy field name → nested path mappings in `_LEGACY_FIELD_MAP`; dual access patterns increase complexity
- Safe modification: Remove legacy mappings after migration period; standardize on nested `settings.api.*` access

---

## Scaling Limits

**In-Memory Rate Limiting:**
- Current capacity: Per-process limits reset on restart
- Limit: Multi-instance deployments have independent limits
- Scaling path: Redis-backed rate limiting for distributed deployments

**No Vector Store Health Checks:**
- Current capacity: Health endpoint doesn't verify vector store connectivity
- Limit: Index failures not detected until queries fail
- Scaling path: Add vector store ping to health endpoint

---

## Dependencies at Risk

**Unbounded Upper Version Constraints:**
- Risk: `chromadb>=0.4.0`, `litellm>=1.0.0`, `openai>=1.0.0`, `wandb>=0.23.0` have no upper bounds
- Impact: Breaking changes in minor releases could slip through
- Migration plan: Pin upper bounds with `~` or `^` constraints

**Heavy Optional Dependencies:**
- `evaluation` extras: 4 LangChain packages
- `reranking` extras: `sentence-transformers>=3.0.0` (pulls PyTorch)
- `extraction` extras: `camelot-py>=0.12.0` (requires Ghostscript)

**Outdated Frontend Dependencies:**
- `marked` at v4 (current is v14+)
- `highlight.js` at exact `11.9.0` (current is 11.11+)
- Files: `frontend/package.json`

---

## Missing Critical Features

**Medical Expansion Provider is No-Op:**
- Problem: `medical_expansion_provider: str = "noop"` — pipeline exists but no real provider
- Blocks: Medical-specific query expansion
- Files: `src/rag/medical_expansion.py`, `src/config/settings.py` → `settings.retrieval.medical_expansion_provider`

**Chat History TTL Cleanup Not Implemented:**
- Problem: `chat_history_ttl_seconds` defined but no background task cleans expired sessions
- Blocks: Storage growth over time
- Files: `src/config/settings.py` → `settings.api.chat_history_ttl_seconds`

**No API Versioning:**
- Problem: All routes unversioned (`/chat`, `/health`, `/evaluation`)
- Blocks: API changes break existing clients

**No Graceful Shutdown for SSE Streaming:**
- Problem: LLM continues generating if client disconnects mid-stream
- Files: `src/app/routes/chat.py` (partially addressed — `GeneratorExit`/`CancelledError` handling added)

---

## Test Coverage Gaps

**Async Event Loop Handling:**
- What's not tested: `asyncio.run()` inside async contexts behavior
- Files: `src/usecases/pipeline.py`
- Risk: Medium — mostly addressed with async variants
- Priority: Medium

**Rate Limiting Under Load:**
- What's not tested: In-memory rate limiting across concurrent requests
- Files: `src/app/middleware/rate_limit.py`
- Risk: Medium — limits reset on restart
- Priority: Medium

---

## Recommendations Summary

| Priority | Issue | Effort |
|---|---|---|
| P1 | Split `src/ingestion/indexing/chroma_store.py` into focused modules | Large |
| P1 | Deduplicate sync/async retrieval functions in `runtime.py` | Medium |
| P1 | Replace module-level globals with explicit config | Large |
| P2 | Add vector store health checks | Small |
| P2 | Narrow exception types | Medium |
| P2 | Update `marked` and `highlight.js` in frontend | Small |
| P2 | Pin upper bounds on critical dependencies | Small |
| P2 | Remove legacy `_LEGACY_FIELD_MAP` after migration | Small |
| P3 | Remove legacy SHA256 support | Small |
| P3 | Add API versioning | Medium |
| P3 | Implement chat history TTL cleanup | Small |
| P3 | Use structured logging | Medium |

---

*Concerns audit: 2026-05-12*
