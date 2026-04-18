# Codebase Concerns Report

Generated: 2026-04-18

---

## 1. Technical Debt

### 1.1 God Module: `src/rag/runtime.py` (1417 lines)

This is the single largest and most complex file in the codebase. It conflates at least 6 distinct responsibilities:

| Responsibility | Lines | Functions |
|---|---|---|
| Index initialization & lifecycle | 393-583 | `initialize_vector_store`, `initialize_runtime_index`, `_build_index_from_sources` |
| Experiment configuration | 586-663 | `configure_runtime_for_experiment` |
| Retrieval orchestration (sync + async) | 864-1041, 1043-1273 | `retrieve_context`, `retrieve_context_with_trace`, `retrieve_context_with_trace_async` |
| MMR diversification & scoring | 666-790 | `_mmr_rerank`, `_diversify_results`, `_content_similarity` |
| Query expansion & HyPE/HyDE integration | 249-390 | `_expand_queries`, `_expand_queries_async`, `_prepare_expanded_queries` |
| Candidate retrieval & merging | 1308-1417 | `_retrieve_candidates`, `_merge_result_sets` |

**Recommendation:** Split into `src/rag/indexing.py`, `src/rag/diversification.py`, `src/rag/query_expansion.py`, `src/rag/retrieval.py`, `src/rag/experiment_config.py`.

### 1.2 Massive Code Duplication in Retrieval Functions

`retrieve_context_with_trace` (lines 919-1040) and `retrieve_context_with_trace_async` (lines 1043-1273) share ~80% identical logic for building pipeline traces, applying reranking, and diversification. The async version adds HyDE support but otherwise mirrors the sync version field-by-field.

**Impact:** Any bug fix or feature addition must be applied in two places.

**Recommendation:** Extract shared trace-building logic into a helper, with sync/async only differing in the retrieval step.

### 1.3 Deprecated Security Code Still Active

`src/app/security.py:64-77` - Legacy unsalted SHA256 hashing is still supported for backward compatibility. The `_hash_secret_legacy` function and legacy verification path in `_verify_secret` (lines 103-108) remain active.

```
DEPRECATED: Unsalted SHA256 is cryptographically insecure. This function exists
only to verify existing legacy hashes. All new keys must use bcrypt.
```

**Recommendation:** Set a removal deadline, add migration logging metrics, and plan removal.

### 1.4 Mutable Module-Level Global State

Multiple modules use `set_*()` functions that mutate module-level globals for runtime configuration:

| File | Globals |
|---|---|
| `src/ingestion/steps/convert_html.py` | `_extractor_strategy`, `_extractor_mode`, `_page_classification_enabled` |
| `src/ingestion/steps/load_pdfs.py` | `_pdf_extractor_strategy`, `_pdf_table_extractor` |
| `src/ingestion/steps/load_markdown.py` | `_index_only_classified_pages` |
| `src/ingestion/steps/chunk_text.py` | `_structured_chunking_enabled`, `_source_chunk_configs`, `_auto_select_strategy` |
| `src/rag/reranker.py:134` | `_reranker_instance` (global singleton) |
| `src/infra/di.py:139,151` | `_container` (global singleton) |
| `src/config/settings.py:588-589` | Mutates `os.environ` at import time |

This pattern makes testing fragile, breaks thread safety, and creates hidden coupling.

**Recommendation:** Consolidate runtime configuration into a single `RuntimeConfig` dataclass passed explicitly through the call chain.

### 1.5 Import-Time Side Effects

- `src/config/__init__.py` - Importing this module triggers `Settings()` instantiation (reads `.env`, validates all settings)
- `src/config/settings.py:588-589` - Sets `os.environ["WANDB_API_KEY"]` at module import time
- `src/app/factory.py:159` - `app = create_app()` at module level creates the entire FastAPI app on import
- `src/evals/deepeval_models.py:95-96` - Mutates `os.environ["OPENROUTER_API_KEY"]` at import time
- `src/infra/llm/litellm_client.py:41-42` - Same pattern for `OPENROUTER_API_KEY`

**Impact:** Importing any module that transitively imports `src.config` has side effects. This complicates testing and can leak environment variables.

### 1.6 Circular Import Detected

```
src.ingestion.steps.chunking.chonkie_adapter
  -> src.ingestion.steps.chunking.medical_semantic
  -> src.ingestion.steps.chunking.chonkie_adapter
```

`medical_semantic.py` imports `ChonkieChunkerAdapter` from `chonkie_adapter.py`, and `chonkie_adapter.py` may conditionally import `medical_semantic` at runtime (or the cycle exists through re-exports). Currently works due to lazy imports but is fragile.

### 1.7 Broad Exception Handling (63+ instances)

The codebase has 63+ `except Exception` blocks. Notable concentrations:

| File | Count | Concern |
|---|---|---|
| `src/rag/runtime.py` | 2 | Swallows errors in retrieval pipeline |
| `src/infra/llm/qwen_client.py` | 3 | LLM errors silently retried |
| `src/infra/llm/litellm_client.py` | 3 | Same pattern |
| `src/evals/assessment/orchestrator.py` | 3 | Evaluation errors swallowed |
| `src/ingestion/steps/convert_html.py` | 5 | Optional import handling (acceptable) |
| `src/ingestion/steps/load_pdfs.py` | 5 | Optional import handling (acceptable) |
| `src/experiments/wandb_history.py` | 4 | W&B failures silently caught |

One bare `except: pass` at `src/evals/dataset_builder.py:351`.

**Recommendation:** Narrow exception types where possible. Add structured error categorization.

### 1.8 Unused Variable

`src/app/routes/chat.py:83` - Variable `e` assigned but never used:
```python
except Exception as e:
    logger.exception("Failed to serialize SSE event")
```

---

## 2. Security Concerns

### 2.1 Legacy Unsalted SHA256 for API Key Verification

`src/app/security.py:64-108` - The `_hash_secret_legacy` function uses `hashlib.sha256` without salt. The verification path at line 103-108 still accepts these hashes. While `hmac.compare_digest` is used (timing-safe comparison), the underlying hash is vulnerable to rainbow table attacks.

**Severity:** Medium (requires attacker to obtain hash database)
**Recommendation:** Add telemetry for legacy hash usage, set migration deadline.

### 2.2 Environment Variable Leakage Risk

- `src/config/settings.py:588-589`: Copies `wandb_api_key` from settings to `os.environ`
- `src/evals/deepeval_models.py:95-96`: Copies `openrouter_api_key` to `os.environ`
- `src/infra/llm/litellm_client.py:41-42`: Same pattern

This makes secrets accessible to any library that reads environment variables, including potentially untrusted dependencies.

**Severity:** Low-Medium
**Recommendation:** Pass API keys explicitly to clients rather than setting global environment variables.

### 2.3 `.env` File Committed to Repository

The `.env` file is committed (encrypted via dotenvx) with a public key visible in the file header. While encryption mitigates risk, the `.env.keys` file exists with private decryption keys. If `.env.keys` were accidentally committed (it's in `.gitignore` but the pattern exists), all secrets would be exposed.

**Severity:** Low (current state is encrypted, but defense-in-depth concern)

### 2.4 CORS Configuration

`src/app/factory.py:132-138`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Default origins include only localhost, but `allow_methods=["*"]` and `allow_headers=["*"]` are overly broad for production.

**Severity:** Low (defaults are dev-only)
**Recommendation:** Restrict methods and headers for non-development environments.

### 2.5 Subprocess Call in Evaluation

`src/evals/assessment/reporting.py:17-23` uses `subprocess.run(["git", "rev-parse", "HEAD"])` with `check=True`. While the command is hardcoded and safe, subprocess usage should be flagged for audit.

**Severity:** Informational

### 2.6 No Input Validation on Chat Message Content

`src/app/routes/chat.py` accepts a `ChatRequest` but validation of message content depends on the schema. The `max_message_length` setting (2000 chars) truncates at the RAG layer (`src/rag/runtime.py:869-871`) rather than rejecting at the API boundary.

**Recommendation:** Validate and reject oversized messages at the request schema level.

---

## 3. Performance Concerns

### 3.1 O(n^2) MMR Diversification

`src/rag/runtime.py:689-713` - `_mmr_rerank` iterates over all remaining candidates and computes `_content_similarity` against every already-selected item. For each similarity check, both strings are tokenized from scratch.

Worst case: O(top_k * len(results) * avg_content_length) per query.

**Recommendation:** Pre-compute token sets once, cache similarity scores, or use approximate methods for large candidate sets.

### 3.2 Synchronous Retrieval in Async Context

`src/usecases/chat.py:192`:
```python
context, sources = retrieve_context(message, top_k=top_k)
```

This is called inside `stream_chat_message` (an async function) but uses the synchronous `retrieve_context`, blocking the event loop during retrieval.

**Severity:** High (blocks async event loop during vector search)
**Recommendation:** Always use `retrieve_context_with_trace_async` in async handlers.

### 3.3 `asyncio.run()` Inside Potentially Async Contexts

- `src/rag/runtime.py:408,439` - `_build_index_from_sources` calls `asyncio.run()` for HyPE generation and chunk enrichment. This is called from `initialize_runtime_index` which may be invoked during FastAPI lifespan (async context).
- `src/app/routes/evaluation.py:527` - `asyncio.run()` in route handler
- `src/usecases/pipeline.py:66,72,107,140` - Multiple `asyncio.run()` calls

Calling `asyncio.run()` inside an already-running event loop will raise `RuntimeError`.

**Severity:** Medium-High (will crash if called from async context)
**Recommendation:** Use `await` consistently or check for running loop with `asyncio.get_running_loop()`.

### 3.4 Sequential Similarity Search Across Expanded Queries

`src/rag/runtime.py:1345-1349`:
```python
result_sets = [
    vector_store.similarity_search(expanded_query, top_k=top_k, search_mode=search_mode)
    for expanded_query in expanded_queries
]
```

Each expanded query triggers a separate vector store search, executed sequentially. With HyDE + lexical expansion, this can be 5-10 sequential searches.

**Recommendation:** Use `asyncio.gather` for parallel searches, or batch queries at the vector store level.

### 3.5 No Caching for Tokenization

`src/rag/runtime.py:671-678` - `_content_similarity` tokenizes strings on every call. During MMR reranking, the same documents are tokenized repeatedly.

**Recommendation:** Pre-compute token sets once per retrieval request.

---

## 4. Code Quality Issues

### 4.1 DI Container Uses `Any` Types

`src/infra/di.py:42-43`:
```python
vector_store: Any = None
llm_client: Any = None
```

The service container discards type information, negating the benefits of the DI pattern.

**Recommendation:** Define protocol interfaces and use them as type annotations.

### 4.2 Inconsistent Architecture Boundaries

The codebase has three overlapping layers:
- `src/app/routes/` - HTTP handlers
- `src/usecases/` - Business logic
- `src/services/` - Another service layer

Routes call usecases directly (`src/app/routes/chat.py:28` imports from `src/usecases/chat.py`), but evaluation routes (`src/app/routes/evaluation.py`) call `src/services/evaluation_service.py`. The boundary between `usecases` and `services` is unclear.

**Recommendation:** Pick one pattern. Either routes -> usecases -> domain, or routes -> services -> domain.

### 4.3 Settings Object as God Configuration

`src/config/settings.py` (589 lines) contains 60+ configuration fields spanning LLM, embedding, retrieval, reranking, rate limiting, HyDE, HyPE, chunking, evaluation, and W&B. All settings are loaded at import time.

**Recommendation:** Group settings into namespaced configuration objects (e.g., `LLMConfig`, `RetrievalConfig`, `SecurityConfig`).

### 4.4 Lint Issues

Ruff detects:
- `E501` (line too long): 4 violations in `src/app/middleware/auth.py:78`, `src/app/routes/chat.py:125`, `src/app/routes/evaluation.py:155,298`
- `F841` (unused variable): `src/app/routes/chat.py:83`

**Recommendation:** Run `ruff check --fix` to resolve.

### 4.5 Mixed Sync/Async Patterns

The retrieval layer provides both sync and async versions of nearly every function:
- `retrieve_context` vs `retrieve_context_with_trace_async`
- `_expand_queries` vs `_expand_queries_async`
- `_retrieve_candidates` vs `_retrieve_candidates_with_trace` vs `_retrieve_candidates_with_trace_async`

This creates confusion about which to use and leads to bugs (sync called from async context).

**Recommendation:** Standardize on async for the web layer. Keep sync only for CLI/offline tools.

### 4.6 No Structured Logging

Logging uses f-strings throughout (e.g., `src/rag/runtime.py:229,383`):
```python
logger.warning(f"Query understanding failed, using default options: {e}")
```

This bypasses lazy formatting and doesn't support structured log aggregation.

**Recommendation:** Use `logger.warning("Query understanding failed: %s", e)` style or structured logging.

---

## 5. Missing Features / Incomplete Implementations

### 5.1 Medical Expansion Provider is No-Op

`src/config/settings.py:486-493`:
```python
medical_expansion_provider: str = "noop"
"""Supported values currently: noop"""
```

The entire medical expansion pipeline exists in code but has no real provider.

### 5.2 No Rate Limiting Persistence

`src/app/middleware/rate_limit.py` uses in-memory rate limiting. On restart, all limits reset. For multi-instance deployments, rate limiting is per-process.

### 5.3 No Health Check for Vector Store

`src/app/routes/health.py` checks application health but doesn't verify vector store connectivity or index status.

### 5.4 No API Versioning

All routes are unversioned (`/chat`, `/health`, `/evaluation`). API changes will break clients.

### 5.5 Chat History Cleanup Not Implemented

`src/config/settings.py:346-352` defines `chat_history_ttl_seconds` (30 days) but no background task cleans up expired sessions.

### 5.6 No Graceful Shutdown for Streaming

`src/app/routes/chat.py` - SSE streaming has no mechanism to detect client disconnect mid-stream. The LLM continues generating even if the client is gone.

---

## 6. Dependency Concerns

### 6.1 Broad Version Ranges

| Dependency | Constraint | Risk |
|---|---|---|
| `chromadb>=0.4.0` | Unbounded upper | Breaking changes likely |
| `litellm>=1.0.0` | Unbounded upper | Breaking changes likely |
| `openai>=1.0.0` | Unbounded upper | Breaking changes likely |
| `wandb>=0.23.0` | Unbounded upper | Breaking changes likely |
| `bcrypt>=4.0.0` | Unbounded upper | Moderate risk |

### 6.2 Optional Dependencies Are Heavy

- `evaluation` extras pull in `langchain<1`, `langchain-community<1`, `langchain-core<1`, `langchain-openai<1` (4 LangChain packages)
- `chunkers` extras pull in `chonkie[semantic]`
- `reranking` extras pull in `sentence-transformers>=3.0.0` (large, pulls PyTorch)
- `extraction` extras pull in `camelot-py>=0.12.0` (requires Ghostscript)

### 6.3 Frontend Dependencies

`frontend/package.json`:
- `marked` pinned to major version `4` (current is v14+). Missing security patches.
- `highlight.js` pinned to exact `11.9.0` (outdated, current is 11.11+)
- `svelte-markdown` at `0.4.1` - may not be compatible with Svelte 5

---

## 7. Recommendations Summary

| Priority | Issue | Effort |
|---|---|---|
| P0 | Fix sync retrieval in async chat handler (3.2) | Small |
| P0 | Fix `asyncio.run()` in potentially async contexts (3.3) | Medium |
| P1 | Split `src/rag/runtime.py` into focused modules (1.1) | Large |
| P1 | Deduplicate sync/async retrieval functions (1.2) | Medium |
| P1 | Replace module-level globals with explicit config (1.4) | Large |
| P1 | Resolve circular import in chunking module (1.6) | Small |
| P2 | Add input validation at API boundary (2.6) | Small |
| P2 | Narrow exception types (1.7) | Medium |
| P2 | Fix DI container type annotations (4.1) | Medium |
| P2 | Standardize on async for web layer (4.5) | Medium |
| P2 | Pin upper bounds on critical dependencies (6.1) | Small |
| P2 | Update `marked` and `highlight.js` in frontend (6.3) | Small |
| P3 | Remove legacy SHA256 support (1.3) | Small |
| P3 | Add API versioning (5.4) | Medium |
| P3 | Implement chat history TTL cleanup (5.5) | Small |
| P3 | Add vector store health checks (5.3) | Small |
| P3 | Use structured logging (4.6) | Medium |
