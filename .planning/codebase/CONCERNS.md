# Codebase Concerns

## Validation Summary

This file was re-validated against the current codebase on 2026-04-15.

### Confirmed

- **Hardcoded API key in local `.env`**: valid. `.env` contains a real-looking `DASHSCOPE_API_KEY`, so the secret-exposure concern is real even if the file is gitignored.
- **Large monolithic files**: valid. Current line counts still match the original concern:
  - `src/rag/runtime.py` - 1,207 lines
  - `src/app/routes/evaluation.py` - 1,035 lines
  - `src/ingestion/indexing/chroma_store.py` - 873 lines
- **Synchronous I/O inside request paths**: valid. `src/app/routes/evaluation.py` does repeated `Path.read_text()` / `open()` work inside async-facing API handlers, and `src/app/middleware/rate_limit.py` uses synchronous SQLite access on every request.
- **No general embedding cache**: mostly valid. There is caching for some evaluation metrics in `src/evals/assessment/answer_eval.py`, but there is no general cache for repeated embedding requests in the retrieval/indexing path.
- **Inconsistent logging**: valid. The codebase mixes `logger.*` usage with many `print(...)` calls in CLI/ingestion/runtime paths such as `src/usecases/pipeline.py`, `src/cli/eval_pipeline.py`, `src/ingestion/steps/download_web.py`, and `src/rag/runtime.py`.
- **Runtime global state**: valid. `src/config/context.py` maintains a mutable process-global singleton, and `src/infra/di.py` also keeps a module-level container singleton.
- **Limited test confidence around core runtime changes**: directionally valid. There are security tests present, but the current environment could not run them because `uv` fails building `grpcio` through `chromadb`, so verification is fragile in practice.
- **Magic numbers and threshold scattering**: valid. Retrieval/evaluation thresholds and heuristics are spread across modules like `src/evals/assessment/thresholds.py`, `src/evals/checks/l1_html.py`, `src/evals/checks/l2_pdf.py`, `src/evals/checks/l3_chunking.py`, and `src/rag/runtime.py`.
- **Architecture still tightly coupled across `evals/`, `rag/`, and `ingestion/`**: valid. `src/rag/runtime.py` imports directly from ingestion internals, and `src/evals/assessment/orchestrator.py` and `src/evals/assessment/retrieval_eval.py` also reach directly into runtime/ingestion internals.

### Partially Confirmed / Reframed

- **Authentication disabled by default**: partially valid, but the original wording is stale. There is no `ENABLE_API_KEY_AUTH=false` flag anymore. Instead, auth is effectively optional because `settings.api_keys` / `settings.api_keys_json` default to empty and `src/app/middleware/auth.py` allows requests through when no keys are configured. `src/app/security.py` does enforce keys outside development mode.
- **Weak password hashing**: outdated as written. `src/app/security.py` now defaults to bcrypt with salt. The remaining concern is narrower: the module still supports legacy unsalted SHA256 hashes for backward compatibility.
- **No rate limiting**: outdated as written. `src/app/middleware/rate_limit.py` exists and is wired in via `src/app/factory.py`. The better concern is that rate limiting is synchronous SQLite-backed middleware and may become a bottleneck under load.
- **Frequent vector rebuilds**: partially valid, but the code is better than the original concern suggests. `src/ingestion/indexing/chroma_store.py` incrementally updates in-memory indexes on insert. The remaining issue is that `_rebuild_index_if_needed()` still reloads/rebuilds collection-derived structures in several paths, and force rebuild remains available in runtime/pipeline flows.
- **Service layer missing**: partially outdated. A new `src/services/` package exists with `RAGService` and `VectorStoreService`, but routes do not meaningfully use it yet, so the service layer is present but not integrated.
- **No dependency injection**: partially outdated. `src/infra/di.py` now provides a container, but it is itself a global singleton and adoption is incomplete.
- **Layering violations**: still directionally valid, but the main problem is file-system/data-access logic in route handlers rather than classic SQL code in routes. `src/app/routes/evaluation.py` directly reads evaluation artifacts from disk and shapes domain responses there.

### Weak / Not Yet Proven

- **Code duplication in evaluation modules**: plausible, but not yet strongly proven from a quick inspection. There are repeated helper patterns (`_float_metric`, metric aggregation shapes, artifact-reading flows), but this needs a dedicated duplication pass before treating it as a high-confidence fix item.
- **Over-complex configuration**: plausible. `src/config/settings.py` is 546 lines and carries many environment toggles, but complexity alone is not enough to call it broken without identifying concrete failure modes.
- **Missing type hints**: weak as a priority concern. There are still some `Any`-heavy interfaces, but most core modules already have meaningful type annotations.
- **Large test files use excessive temporary directories**: unverified.
- **Limited documentation / missing docstrings**: weak as a top concern. Many key modules already have docstrings; this is better treated as selective cleanup while refactoring.
- **Inconsistent naming (snake_case vs camelCase imports)**: weak. There are some mixed naming artifacts from external concepts (for example HyDE/HyPE terminology), but this is not currently a major maintainability risk.

## Additional Concern Found During Verification

- **Broken service package export**: `src/services/__init__.py` exports `EvaluationService`, but there is no `src/services/evaluation_service.py` in the repository. If anything imports `src.services`, that package import will fail.

## Proposed Fix Plan

### Phase 1: Security and correctness

1. Remove the live-looking secret from local `.env`, rotate it outside the repo, and keep `.env.example` as the only template with placeholders.
2. Tighten the security messaging and defaults in docs/config so development convenience does not read like a production-safe setup.
3. Decide on a deprecation path for legacy SHA256 API-key hashes:
   - keep verification temporarily
   - add explicit warning logs / docs
   - migrate stored hashes to bcrypt-only
4. Fix the broken `src/services/__init__.py` export so the package is internally consistent.

### Phase 2: Request-path performance hot spots

1. Extract evaluation artifact loading out of `src/app/routes/evaluation.py` into a dedicated reader/service module.
2. Replace synchronous per-request SQLite rate limiting with one of:
   - a lighter in-memory backend for single-process dev/test
   - a proper shared backend for production
   - or `asyncio.to_thread` wrapping as a minimal interim step
3. Identify repeated embedding calls and add a bounded cache at the embedding client boundary where inputs are stable.

### Phase 3: Untangle architecture incrementally

1. Split `src/rag/runtime.py` by responsibility:
   - retrieval config
   - query expansion
   - candidate retrieval
   - trace assembly / formatting
2. Split `src/app/routes/evaluation.py` into:
   - route declarations
   - artifact loading
   - response shaping / aggregation helpers
3. Split `src/ingestion/indexing/chroma_store.py` into:
   - storage client lifecycle
   - indexing/upsert logic
   - search/ranking logic
4. Move route/business logic onto the existing service layer instead of importing runtime/indexing internals directly from routes.
5. Reduce global-singleton coupling by passing container/runtime dependencies explicitly where practical.

### Phase 4: Cleanup after structural work

1. Standardize logging conventions by reserving `print(...)` for explicit CLI UX and using structured logging elsewhere.
2. Consolidate duplicated metric/helper patterns only after the evaluation modules are split, so we do not abstract the current large-file shape into shared complexity.
3. Centralize thresholds/constants that are meant to be tuned, while leaving obviously local constants close to their call sites.
4. Re-run backend tests once the Python/dependency environment is fixed enough to build `chromadb` dependencies reliably.

## Recommended Execution Order

If we turn this into implementation work, the highest-value order is:

1. Secret cleanup + service export fix
2. Evaluation route extraction
3. Rate-limit backend cleanup
4. `runtime.py` split
5. `chroma_store.py` split
6. Logging / constants / follow-up cleanup

