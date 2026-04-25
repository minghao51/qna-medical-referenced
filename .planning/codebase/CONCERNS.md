# Codebase Concerns

**Analysis Date:** 2026-04-19

## Tech Debt

**God Module: `src/rag/runtime.py` (1425 lines):**
- Issue: Single file with 6+ distinct responsibilities (index init, experiment config, retrieval orchestration, MMR reranking, query expansion, candidate retrieval)
- Files: `src/rag/runtime.py`
- Impact: Hard to test, maintain, or add features without risking regressions
- Fix approach: Split into focused modules (`src/rag/indexing.py`, `src/rag/diversification.py`, `src/rag/query_expansion.py`, `src/rag/retrieval.py`, `src/rag/experiment_config.py`)

**Massive Code Duplication in Sync/Async Retrieval:**
- Issue: `retrieve_context_with_trace` and `retrieve_context_with_trace_async` share ~80% identical logic
- Files: `src/rag/runtime.py:919-1273`
- Impact: Bug fixes must be applied in two places; easy to introduce inconsistencies
- Fix approach: Extract shared trace-building logic into a helper

**Mutable Module-Level Global State:**
- Issue: Multiple modules use `set_*()` functions mutating globals for runtime configuration
- Files: `src/ingestion/steps/convert_html.py`, `src/ingestion/steps/load_pdfs.py`, `src/ingestion/steps/load_markdown.py`, `src/ingestion/steps/chunk_text.py`, `src/rag/reranker.py:134`, `src/infra/di.py:131`, `src/config/settings.py:588-589`
- Impact: Breaks thread safety, creates hidden coupling, fragile testing
- Fix approach: Consolidate runtime config into a `RuntimeConfig` dataclass passed explicitly

**Import-Time Side Effects:**
- Issue: Modules trigger side effects on import (Settings instantiation, env var mutations, app creation)
- Files: `src/config/__init__.py`, `src/config/settings.py:588-589`, `src/app/factory.py:159`, `src/evals/deepeval_models.py:95-96`, `src/infra/llm/litellm_client.py:41-42`
- Impact: Importing transitively causes env var leaks; complicates testing
- Fix approach: Lazy initialization or explicit dependency injection

**Circular Import in Chunking Module:**
- Issue: `chonkie_adapter` ↔ `medical_semantic` may create circular import
- Files: `src/ingestion/steps/chunking/chonkie_adapter.py`, `src/ingestion/steps/chunking/medical_semantic.py`
- Impact: Works via lazy imports but fragile
- Fix approach: Break cycle by moving shared types to a third module

**Broad Exception Handling (72+ instances):**
- Issue: 72 `except Exception as` blocks across codebase; one bare `except: pass` at `src/evals/dataset_builder.py:375`
- Files: See grep output - concentrated in `src/evals/`, `src/infra/llm/`, `src/rag/runtime.py`, `src/usecases/`
- Impact: Errors swallowed silently, hard to debug
- Fix approach: Narrow exception types; add structured error categorization

---

## Known Bugs

**Sync Retrieval Called in Async Context:**
- Symptoms: `asyncio.run()` called inside potentially async event loops
- Files: `src/rag/runtime.py:394`, `src/usecases/pipeline.py:66,72,107,140`
- Trigger: Calling `initialize_runtime_index` from FastAPI lifespan or async route handlers
- Workaround: Ensure async routes use async variants

**Unused Variable in Chat Route:**
- Symptoms: Variable `e` assigned but never used
- Files: `src/app/routes/chat.py:83`
- Workaround: Run `ruff check --fix`

---

## Security Considerations

**Legacy Unsalted SHA256 for API Key Verification:**
- Risk: `src/app/security.py:64-108` uses SHA256 without salt; vulnerable to rainbow table attacks
- Files: `src/app/security.py`
- Current mitigation: `hmac.compare_digest` provides timing-safe comparison
- Recommendations: Add telemetry for legacy hash usage; set migration deadline

**Environment Variable Leakage:**
- Risk: API keys set to `os.environ` accessible to any library that reads env vars
- Files: `src/config/settings.py:588-589`, `src/evals/deepeval_models.py:95-96`, `src/infra/llm/litellm_client.py:41-42`
- Recommendations: Pass API keys explicitly to clients

**.env File Tracking:**
- Risk: `.env` committed with encryption; `.env.keys` (private keys) in `.gitignore`
- Recommendations: Defense-in-depth; ensure `.env.keys` never committed

**CORS Overly Permissive:**
- Risk: `allow_methods=["*"]` and `allow_headers=["*"]` in production
- Files: `src/app/factory.py:132-138`
- Recommendations: Restrict methods/headers for non-dev environments

**Subprocess Call in Evaluation:**
- Risk: `subprocess.run(["git", "rev-parse", "HEAD"])` at `src/evals/assessment/reporting.py:17-23`
- Current mitigation: Hardcoded command, safe
- Recommendations: Flag for audit

---

## Performance Bottlenecks

**O(n²) MMR Diversification:**
- Problem: `_mmr_rerank` iterates over all candidates, computing similarity against every selected item; strings tokenized from scratch each time
- Files: `src/rag/runtime.py:689-713`
- Cause: No caching of token sets or similarity scores
- Improvement path: Pre-compute tokens once; cache similarity scores; use approximate methods for large sets

**Sequential Vector Searches:**
- Problem: Each expanded query triggers separate sequential search
- Files: `src/rag/runtime.py:1345-1349`
- Improvement path: Use `asyncio.gather` for parallel searches

**No Tokenization Caching:**
- Problem: `_content_similarity` tokenizes strings on every call during MMR
- Files: `src/rag/runtime.py:671-678`
- Improvement path: Pre-compute token sets once per retrieval request

---

## Fragile Areas

**Mixed Sync/Async Patterns:**
- Why fragile: Both sync and async versions of nearly every function; sync called from async context causes event loop blocking
- Safe modification: Standardize on async for web layer; keep sync only for CLI/offline tools
- Files: `src/rag/runtime.py`, `src/usecases/chat.py`

**Large Files with Many Responsibilities:**
- Why fragile: `runtime.py` (1425L), `chroma_store.py` (902L), `retrieval_eval.py` (768L), `orchestrator.py` (643L)
- Safe modification: Extract specific responsibilities before adding features
- Files: `src/rag/runtime.py`, `src/ingestion/indexing/chroma_store.py`, `src/evals/assessment/retrieval_eval.py`, `src/evals/assessment/orchestrator.py`

**Settings God Object:**
- Why fragile: 589-line `settings.py` with 60+ fields spanning all subsystems
- Safe modification: Group into namespaced configs (`LLMConfig`, `RetrievalConfig`, `SecurityConfig`)

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
- Problem: `medical_expansion_provider: str = "noop"` - pipeline exists but no real provider
- Blocks: Medical-specific query expansion
- Files: `src/config/settings.py:486-493`

**Chat History TTL Cleanup Not Implemented:**
- Problem: `chat_history_ttl_seconds` defined but no background task cleans expired sessions
- Blocks: Storage growth over time
- Files: `src/config/settings.py:346-352`

**No API Versioning:**
- Problem: All routes unversioned (`/chat`, `/health`, `/evaluation`)
- Blocks: API changes break existing clients

**No Graceful Shutdown for SSE Streaming:**
- Problem: LLM continues generating if client disconnects mid-stream
- Files: `src/app/routes/chat.py`

---

## Test Coverage Gaps

**Async Event Loop Handling:**
- What's not tested: `asyncio.run()` inside async contexts behavior
- Files: `src/rag/runtime.py`, `src/usecases/pipeline.py`
- Risk: High - will crash in production under certain call patterns
- Priority: High

**Rate Limiting Under Load:**
- What's not tested: In-memory rate limiting across concurrent requests
- Files: `src/app/middleware/rate_limit.py`
- Risk: Medium - limits reset on restart
- Priority: Medium

---

## Recommendations Summary

| Priority | Issue | Effort |
|---|---|---|
| P0 | Fix `asyncio.run()` in potentially async contexts | Medium |
| P0 | Fix sync retrieval in async chat handler | Small |
| P1 | Split `src/rag/runtime.py` into focused modules | Large |
| P1 | Deduplicate sync/async retrieval functions | Medium |
| P1 | Replace module-level globals with explicit config | Large |
| P2 | Add vector store health checks | Small |
| P2 | Narrow exception types | Medium |
| P2 | Update `marked` and `highlight.js` in frontend | Small |
| P2 | Pin upper bounds on critical dependencies | Small |
| P3 | Remove legacy SHA256 support | Small |
| P3 | Add API versioning | Medium |
| P3 | Implement chat history TTL cleanup | Small |
| P3 | Use structured logging | Medium |

---

*Concerns audit: 2026-04-19*
