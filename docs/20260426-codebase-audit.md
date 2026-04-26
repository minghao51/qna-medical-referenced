# Codebase Audit Report

**Date:** 2026-04-26
**Scope:** Full-stack audit (Python backend + TypeScript/Svelte frontend)
**Lines of Code:** ~19,066 Python (src/), ~58 frontend source files
**Tests:** 495 collected (431 claimed in AGENTS.md — stale)

---

## Executive Summary

**Overall Health Rating: MODERATE**

The project has a well-defined domain boundary (ingestion → RAG → evaluation), a solid experiment framework, and near-comprehensive test coverage. Linting is clean (`ruff` passes). However, three central modules have grown into unmaintainable "god files," type safety is broken in the vector-store layer, blocking I/O runs inside async hot paths, and a high-severity path-traversal vulnerability exists in the experiments API. The codebase is production-capable with guardrails, but it carries significant architectural and runtime risks that will compound as the team or data volume grows.

### Top 5 Critical Findings

1. **Path Traversal in Experiments API** — `src/app/routes/experiments.py` accepts unsanitized `experiment_name` path parameters, allowing arbitrary file reads outside the experiments directory.
2. **God Modules Violating SRP** — `src/rag/runtime.py` (1,437 lines) and `src/ingestion/indexing/chroma_store.py` (902 lines) mix 10+ responsibilities each, making changes high-risk and reviews slow.
3. **Blocking I/O in Async Hot Path** — `FileChatHistoryStore` is called synchronously from the SSE streaming endpoint, blocking the event loop under concurrent load.
4. **Entire Vector Store Mirrored in RAM** — `ChromaVectorStore` keeps all embeddings, documents, BM25 indexes, and metadata in Python memory, creating an OOM ceiling and preventing horizontal scaling.
5. **30 MyPy Errors in Core Vector Store** — `chroma_store.py` is effectively untyped, erasing compile-time safety guarantees in the most data-intensive component.

---

## Detailed Findings

### Security

| # | Severity | Location | Description | Proposed Fix |
|---|----------|----------|-------------|--------------|
| SEC-1 | **High** | `src/app/routes/experiments.py:97,111` | `experiment_name` path param is used directly to build a `Path`. An attacker can pass `../../../config/settings` to read arbitrary YAML/JSON files. | Validate `experiment_name` against `^[A-Za-z0-9._-]+$`, or resolve the path and assert it is still under `EXPERIMENTS_DIR`. |
| SEC-2 | **Medium** | `src/app/middleware/rate_limit.py:86-123` | SQLite rate-limit backend has a read-then-write race condition (TOCTOU). Two concurrent requests with the same key can both see `count < limit` and both insert, briefly exceeding the limit. | Use `BEGIN IMMEDIATE` with retry logic, or add a `threading.Lock` around the SQLite check/insert block. |
| SEC-3 | **Medium** | `src/config/settings.py:286-287` | `WANDB_API_KEY` is copied into `os.environ` at import time, making it visible to child processes and `/proc/<pid>/environ`. | Pass the key directly to the W&B client constructor; never pollute the global environment. |
| SEC-4 | **Medium** | `src/app/routes/evaluation.py:482` | `/evaluation/evaluate-single` accepts unbounded query/body strings as query parameters. No `max_length` constraint. | Move parameters into a Pydantic request body with `Field(..., max_length=...)`. |
| SEC-5 | **Medium** | `src/app/factory.py:141-147` | CORS middleware allows credentials with configurable origins. A misconfigured wildcard or overly broad origin list creates credential-leakage risk. | Reject `*` or empty origins at startup when `allow_credentials=True` and not in development mode. |
| SEC-6 | **Medium** | `src/app/security.py:64-108` | Legacy unsalted SHA256 hashes are still accepted for API key verification. Offline cracking is orders of magnitude faster than bcrypt. | Emit deprecation warnings, set a hard removal date, and provide a CLI command to re-hash legacy keys to bcrypt. |
| SEC-7 | **Low** | `src/ingestion/steps/download_pdfs.py:33` | MD5 used for filename hashing. Bandit flags as weak hash. | Add `usedforsecurity=False` (or `# nosec B324`) — this is a non-cryptographic filename hash. |
| SEC-8 | **Low** | `src/ingestion/steps/download_web.py:32` | Same MD5 issue as SEC-7. | Same fix as SEC-7. |

### Architecture & Design

| # | Severity | Location | Description | Proposed Fix |
|---|----------|----------|-------------|--------------|
| ARCH-1 | **Critical** | `src/rag/runtime.py` | 1,437-line god module mixing query expansion, retrieval, reranking, MMR, tracing, HyDE/HyPE, medical expansion, and experiment runtime config. | Decompose into `query_expansion/`, `retrieval/engine.py`, `diversification.py`, `tracing.py`. Keep `runtime.py` as a thin facade. |
| ARCH-2 | **Critical** | `src/ingestion/indexing/chroma_store.py` | 902-line god class handling ChromaDB persistence, in-memory BM25, RRF fusion, semantic ranking, metadata normalization, legacy JSON snapshots, and hypothetical-question search. | Split into `ChromaStorage`, `SearchEngine`, and `MetadataNormalizer`. Inject dependencies. |
| ARCH-3 | **High** | `src/evals/assessment/orchestrator.py:115` | `run_assessment()` has 60+ parameters and directly mutates global ingestion state (`set_page_classification_enabled`, `set_structured_chunking_enabled`, etc.). | Encapsulate config mutation in a `RuntimeConfigurator` object. Group parameters into `AssessmentOptions` dataclass. |
| ARCH-4 | **High** | `src/evals/assessment/retrieval_eval.py` | Feature envy: digs into `trace.retrieval.score_weights` for 15+ fields and aggregates 30+ metric lists inline. | Define a `RetrievalTraceExtractor` typed interface and a `RetrievalMetricsAggregator`. |
| ARCH-5 | **High** | `src/app/routes/documents.py:98` | Route accesses `store._collection` directly, breaking encapsulation. | Add `get_document(doc_id)` to `ChromaVectorStore` public API. |
| ARCH-6 | **High** | `src/rag/runtime.py` | Imports from `ingestion.steps.*` — RAG runtime should not depend on ingestion steps. | Move `initialize_vector_store` and `_build_index_from_sources_async` to `src/ingestion/` or `bootstrap.py`. |
| ARCH-7 | **High** | `src/infra/di.py` | DI container exists but routes bypass it, pulling services from `request.app.state` or calling `get_vector_store()` directly. | Wire routes to the DI container via `Depends(get_container)` or FastAPI `dependency_overrides`. |
| ARCH-8 | **High** | `src/ingestion/indexing/chroma_store.py` | `ChromaVectorStoreFactory` class-level singleton has no thread lock. Concurrent requests with different configs can race on `_instance`. | Add `threading.Lock` around instance creation, or use an explicit application registry. |
| ARCH-9 | **High** | All routes in `src/app/routes/` | No API versioning (`/v1/`). No standardized error response schema. | Add `/api/v1/` prefix and a unified `ErrorResponse` Pydantic model. |
| ARCH-10 | **Medium** | `src/rag/runtime.py` | Near-duplicate sync/async pairs (`_expand_queries` / `_expand_queries_async`, `retrieve_context_with_trace` / `retrieve_context_with_trace_async`). | Make the pipeline natively async; provide thin sync wrappers only where needed. |
| ARCH-11 | **Medium** | `src/rag/runtime.py` | `configure_runtime_for_experiment()` calls 10+ global setters with hardcoded defaults. Global mutable state anti-pattern. | Return an immutable `ExperimentRuntimeConfig` and pass it explicitly to components. |
| ARCH-12 | **Medium** | `src/infra/llm/qwen_client.py` | `get_client()` creates a new instance on every call. No connection pooling or shared rate-limit state. | Cache the client in the DI container with lifecycle management. |

### Performance & Scalability

| # | Severity | Location | Description | Proposed Fix |
|---|----------|----------|-------------|--------------|
| PERF-1 | **Critical** | `src/infra/storage/file_chat_history_store.py` | Blocking file I/O in async chat path. `stream_chat_message` calls the store without `asyncio.to_thread()`, stalling the event loop. | Wrap file operations in `asyncio.to_thread()` or switch to an async storage backend (e.g., `aiofiles` or Redis). |
| PERF-2 | **Critical** | `src/rag/runtime.py` | `initialize_runtime_index()` → `_build_index_from_sources()` calls `asyncio.run()`, which crashes when invoked from an already-running event loop (e.g., inside `asyncio.to_thread` in evals). | Refactor to async-only entrypoints; never nest `asyncio.run()`. |
| PERF-3 | **Critical** | `src/ingestion/indexing/chroma_store.py` | Entire collection (documents, embeddings, metadatas, term frequencies, keyword indexes) is mirrored in Python RAM. OOM risk as corpus grows. | Stop mirroring everything in RAM. Use ChromaDB's native query API for semantic search and build BM25 on-demand or via a separate service. |
| PERF-4 | **High** | `src/rag/runtime.py` (hot path) | No caching for embeddings, retrieval results, or LLM responses. Identical queries are re-embedded and re-searched on every request. | Add an LRU cache for embeddings (keyed by query text) and a query-result cache with TTL. |
| PERF-5 | **High** | `src/ingestion/indexing/chroma_store.py` | `_search_ranked` builds both semantic and keyword ranked lists regardless of search mode, then discards one when mode is `semantic_only` or `bm25_only`. | Short-circuit: only build the pipelines needed for the active mode. |
| PERF-6 | **High** | `src/app/middleware/rate_limit.py` | SQLite rate limiter is single-instance, single-writer. Will not scale across Uvicorn workers or containers. | Replace with Redis-backed rate limiting, or document the single-worker constraint. |
| PERF-7 | **Medium** | `src/ingestion/indexing/chroma_store.py` | No metadata indexes in ChromaDB. Filtered queries perform full collection scans. | Add metadata indexes for frequently filtered fields (e.g., `source_type`, `page_number`). |
| PERF-8 | **Medium** | `src/config/context.py` | Every property access on `RuntimeState` acquires a lock. High-frequency reads during chunking could contend. | Use `threading.RLock` or immutable config snapshots for read-heavy paths. |

### Code Quality & Maintainability

| # | Severity | Location | Description | Proposed Fix |
|---|----------|----------|-------------|--------------|
| QUAL-1 | **High** | `src/ingestion/indexing/chroma_store.py` | 30 mypy type errors (91% of all errors). Incompatible ChromaDB types, union-attr failures, unpack errors. | Narrow types with `cast()` / `assert` guards, or add ChromaDB type stubs. |
| QUAL-2 | **High** | `src/usecases/chat.py:221,227` | Bare `except Exception` inside generator masks `GeneratorExit` and `CancelledError`. | Explicitly catch `GeneratorExit` / `asyncio.CancelledError` and re-raise before generic `Exception`. |
| QUAL-3 | **High** | `src/app/routes/chat.py:83,97` | Same generator safety issue as QUAL-2 but in the SSE endpoint. | Same fix as QUAL-2. |
| QUAL-4 | **High** | `src/` (70 locations) | Bare `except Exception` is overused. Several swallow errors that should propagate. | Narrow exception types. Where generic catch is required, log structurally and re-raise if unexpected. |
| QUAL-5 | **Medium** | `src/` (23 functions) | Cyclomatic complexity > 10. Worst offenders: `main` in `eval_pipeline.py` (28), `run_assessment` (28), `add_documents` (18), `_diversify_results` (18). | Extract helper functions for nested conditionals and loops. |
| QUAL-6 | **Medium** | `src/` (33 locations) | f-strings in `logger.debug/info/warning` calls. Eager string interpolation even when the log level is disabled. | Convert to `%` formatting: `logger.debug("msg %s", value)`. |
| QUAL-7 | **Medium** | `src/ingestion/indexing/chroma_store.py:28,68` | Duplicate `logger = logging.getLogger(__name__)` declaration. | Remove the second definition on line 68. |
| QUAL-8 | **Low** | `src/` (92 lines) | `E501` line-too-long violations (101–115 chars). Target is 100. | Wrap lines or add strategic ignores. |

### Testing

| # | Severity | Location | Description | Proposed Fix |
|---|----------|----------|-------------|--------------|
| TEST-1 | **High** | `tests/unit/test_eval_error_handling.py:72,114,311` | `except Exception: pass` in tests means they pass even if the code under test crashes. | Replace with `pytest.fail(f"Unexpected error: {e}")` or assert on expected exception type. |
| TEST-2 | **High** | `tests/unit/test_ingestion_error_handling.py:34` | `test_network_timeout_with_retry` has zero assertions — it only sets up mocks without verifying behavior. | Add an assertion that the retry function is called the expected number of times. |
| TEST-3 | **High** | `tests/conftest.py:11` | `os.environ["DASHSCOPE_API_KEY"] = "test-api-key"` runs at import time, permanently mutating process environment. | Move into a `pytest.fixture(scope="session", autouse=True)` with cleanup. |
| TEST-4 | **Medium** | 32 test files | `monkeypatch.setattr(settings, ...)` mutates the global singleton directly. Tests can leak state. | Add an autouse fixture that snapshots and restores `settings` after each test. |
| TEST-5 | **Medium** | `tests/integration/test_eval_api_deepeval.py:39` | Hard `@pytest.mark.skip` with no conditional logic. | Replace with `@pytest.mark.skipif(...)` based on environment or availability. |
| TEST-6 | **Medium** | `tests/e2e/test_backend_e2e_real_apis.py:61-84` | E2E tests depend on global vector store singleton. Parallel runs could collide. | Use monkeypatch to inject an isolated store, or enforce serial execution. |
| TEST-7 | **Medium** | `docs/testing/backend-tests.md` | Docs reference stale paths (`tests/test_settings.py` instead of `tests/unit/test_settings.py`, etc.) and omit the `e2e/` directory. | Refresh paths and add a section on markers (`live_api`, `e2e_real_apis`, `deepeval`). |
| TEST-8 | **Low** | ~38 source files | Minimal or missing docstrings on public APIs and modules. | Add module-level docstrings to `__init__.py` files and docstrings to the 23 complex functions. |

### Dependencies & Configuration

| # | Severity | Location | Description | Proposed Fix |
|---|----------|----------|-------------|--------------|
| DEPS-1 | **Medium** | `pyproject.toml` | `deepeval` is pinned to `<4.0.0`. This is a fast-moving package; the pin may block security fixes. | Evaluate compatibility with latest `deepeval` and relax or bump the upper bound. |
| DEPS-2 | **Low** | `pyproject.toml` | `grpcio` has `no-build-isolation-package` override. This is a workaround that can break on new uv versions. | Document why it is needed, and re-evaluate on each `uv` upgrade. |
| DEPS-3 | **Low** | `pyproject.toml` | `bandit` is in `dev` optional deps but not run in CI (no `.github/workflows/ci.yml` found). | Add bandit to the CI pipeline, or verify it runs in pre-commit. |
| DEPS-4 | **Informational** | `.gitignore` | `.env` and `.env.*` are correctly ignored. No plaintext secrets committed. | No action needed. |

---

## Gaps — Missing Aspects That Should Exist

1. **No CI/CD pipeline file** — There is no `.github/workflows/ci.yml` or equivalent. A project of this size needs automated test, lint, type-check, and bandit runs on every PR.
2. **No integration/SAST in pre-commit** — `bandit` is installed but not wired into `.pre-commit-config.yaml`.
3. **No query/result caching** — The RAG hot path has zero caching, guaranteeing redundant LLM calls and embedding computations.
4. **No structured logging / observability** — Logs are plain text. No request tracing IDs propagated to LLM calls, no metrics on retrieval latency percentiles.
5. **No load tests** — With blocking I/O in async paths and a single-writer SQLite rate limiter, there is no evidence the system has been load-tested.
6. **No API versioning** — Breaking changes to routes will force frontend lockstep deployments.
7. **No dependency vulnerability scanning** — `bandit` covers code, but there is no `pip-audit`, `safety`, or Dependabot integration.
8. **No dead-code analysis** — `vulture` is not installed; god modules likely contain unused helpers.

---

## Next Steps — Prioritized Action Plan

### Week 1: Quick Wins (Low Effort, High Impact)

- [ ] **Fix path traversal** (`SEC-1`): Add regex validation to `experiment_name` in `src/app/routes/experiments.py`.
- [ ] **Fix generator safety** (`QUAL-2`, `QUAL-3`): Re-raise `GeneratorExit` / `CancelledError` before generic `except Exception` in chat paths.
- [ ] **Fix mypy in `chroma_store.py`** (`QUAL-1`): Add `cast()` and `assert` guards for ChromaDB union types. Target: zero errors.
- [ ] **Fix test reliability** (`TEST-1`, `TEST-2`): Replace `except Exception: pass` in tests with `pytest.fail()` or explicit assertions.
- [ ] **Add `# nosec` comments** for intentional MD5 and `random` usage to clean up bandit noise.
- [ ] **Update stale docs** (`TEST-7`, AGENTS.md test count): Correct paths and update test count from 431 to 495.

### Week 2: Structural Improvements

- [ ] **Decompose `src/rag/runtime.py`** (`ARCH-1`): Extract `query_expansion/`, `retrieval/engine.py`, `diversification.py`, and `tracing.py`. Keep `runtime.py` as a facade.
- [ ] **Extract search logic from `ChromaVectorStore`** (`ARCH-2`): Create `RetrievalEngine` for RRF/MMR/reranking; let `ChromaVectorStore` handle only persistence.
- [ ] **Refactor `run_assessment()`** (`ARCH-3`): Group 60+ parameters into `AssessmentOptions` and encapsulate global state mutation.
- [ ] **Add API versioning** (`ARCH-9`): Prefix routes with `/api/v1/` and introduce a standard `ErrorResponse` schema.
- [ ] **Add autouse settings-reset fixture** (`TEST-4`): Prevent test state leakage from `monkeypatch.setattr(settings, ...)`.

### Week 3: Performance & Scalability

- [ ] **Eliminate blocking I/O in async chat** (`PERF-1`): Wrap `FileChatHistoryStore` in `asyncio.to_thread()` or migrate to Redis.
- [ ] **Remove `asyncio.run()` nesting** (`PERF-2`): Refactor `initialize_runtime_index` to async-only.
- [ ] **Add query embedding cache** (`PERF-4`): LRU cache for identical query embeddings (TTL 5–15 minutes).
- [ ] **Short-circuit unused search pipelines** (`PERF-5`): Only build semantic/BM25 rankings needed for the active mode.
- [ ] **Fix SQLite rate-limit race** (`SEC-2`): Use `BEGIN IMMEDIATE` or a `threading.Lock`.

### Week 4: Process & Tooling

- [ ] **Add GitHub Actions CI** (Gap #1): Run `ruff check`, `mypy src/`, `pytest -m "not (live_api or deepeval or e2e_real_apis)"`, and `bandit -r src/` on PRs.
- [ ] **Add `vulture` or `deadcode`** (Gap #8): Run dead-code analysis and delete unused helpers.
- [ ] **Introduce dependency scanning** (Gap #7): Add `pip-audit` or Dependabot alerts.
- [ ] **Document scaling constraints** (`PERF-3`, `PERF-6`): Add an ADR explaining the single-worker, in-memory vector store limitation and the path to Redis + external ChromaDB.
- [ ] **Evaluate CORS strictness** (`SEC-5`): Add startup assertion rejecting wildcards in production.

---

## Confidence & Assumptions

| Finding | Confidence | Assumptions |
|---------|------------|-------------|
| Path traversal (SEC-1) | **Very High** | Read actual source; path construction is direct string concatenation. |
| God modules (ARCH-1, ARCH-2) | **Very High** | Line counts and responsibility counts are objective. |
| Blocking I/O in async (PERF-1, PERF-2) | **High** | Inferred from file store implementation and `asyncio.run()` usage. A runtime trace would confirm 100%. |
| SQLite rate-limit race (SEC-2) | **High** | Standard SQLite behavior under WAL mode without explicit locking. |
| MyPy errors (QUAL-1) | **Very High** | Ran `mypy src/` directly; 33 errors confirmed. |
| Test count discrepancy | **Very High** | Ran `pytest --co -q` directly; 495 vs 431 in AGENTS.md. |
| No CI/CD file | **High** | Searched for `.github/workflows/*.yml` and found none. Assumed repo is hosted on GitHub based on git remote. |
| Entire collection in RAM (PERF-3) | **High** | Based on `chroma_store.py` loading all embeddings/docs into instance attributes. Memory profile would confirm exact footprint. |
| CORS credentials risk (SEC-5) | **Medium** | Depends on operator not misconfiguring origins in production. Code path is correct but lacks a guardrail. |

---

*Report generated by automated tooling (bandit, ruff, mypy, pytest) and manual code review across 144 Python source files and 58 frontend source files.*
