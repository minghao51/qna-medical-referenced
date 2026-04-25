# Post-Phase-1 Handoff

## Current State

Phase 1 stabilization is complete.

The codebase now has:

- Runtime-owned state in `src/config/context.py` for ingestion toggles, reranker cache, and vector-store initialization status.
- Runtime/index initialization in `src/rag/runtime.py` backed by shared context instead of module-level initialization globals.
- Sliding-window rate limiting in `src/app/middleware/rate_limit.py`.
- Enriched health/runtime visibility from `GET /health`.
- Explicit SSE terminal error payloads for `/chat` including `error_code` and `request_id`.
- Incremental in-memory keyword/BM25 cache maintenance in `src/ingestion/indexing/chroma_store.py` for normal retrieval paths.
- Frontend API error parsing and operational banners on chat/eval pages.
- Formal reset helpers used by tests and clean-run scripts instead of private-global mutation.

## Phase 1 Cleanups Already Done

Do not spend follow-up time redoing these items:

- Removed the remaining compatibility-era runtime/global leaks for HTML, PDF, and markdown ingestion settings.
- Updated tests to use explicit getter APIs instead of importing module globals.
- Tightened maintained-script error handling where Phase 1 touched active workflows.
- Verified focused backend tests, Playwright tests, and frontend production build after the cleanup pass.

## Remaining Work by Phase

### Phase 2: Medical-Grade Retrieval Quality

Primary goal: improve retrieval precision/recall for medical content without reopening Phase 1 infrastructure work.

Recommended order:

1. Semantic medical chunking
   - Extend the chunking pipeline to preserve medical sections, tables, and list semantics more deliberately than the current generic structured-block handling.
   - Prefer evolving `src/ingestion/steps/chunking/core.py` and helpers rather than adding a parallel chunking stack.
   - Add chunk-quality tests around table atomicity, list continuity, and section boundary preservation.

2. Ontology-backed query expansion seam
   - Keep the provider interface feature-flagged and disabled by default first.
   - Add a provider abstraction near `src/rag/runtime.py` query expansion flow rather than hardcoding MeSH/UMLS logic into `_expand_queries`.
   - Start with a pluggable interface returning normalized expansion terms plus provenance.
   - Leave credentialed/UMLS-specific operational details out of the first implementation unless the data source is finalized.

3. Reranking improvements
   - Cross-encoder reranking exists already in `src/rag/reranker.py`; Phase 2 should tune candidate selection, thresholds, and observability rather than reintroducing the feature.
   - Add retrieval-side evaluation coverage for reranker gains and latency tradeoffs.

Definition of done for Phase 2:

- measurable retrieval-quality improvement on the existing evaluation set
- new functionality guarded by configuration flags
- no regression to Phase 1 runtime safety or health visibility

### Phase 3: Scalability and Ops

Primary goal: move persistence and ingestion execution to production-safe patterns.

Recommended order:

1. Storage migration
   - Replace file-backed chat history and evaluation artifacts that need transactional access with SQLite first, then reassess whether PostgreSQL is necessary.
   - Preserve existing route behavior while swapping storage implementations behind interfaces in `src/infra/storage`.

2. Async/queued ingestion
   - Introduce a job-oriented ingestion interface rather than making the existing pipeline partially async in place.
   - Keep current synchronous CLI workflows available for local/dev usage.

3. Continuous evaluation
   - Add sampled production evaluation hooks after storage and job orchestration are stable.
   - Reuse the current evaluation artifact shape where possible so the frontend dashboard can evolve incrementally.

Definition of done for Phase 3:

- storage no longer depends on JSON files for live mutable state
- ingestion can run safely outside request paths
- evaluation sampling is observable and bounded

### Phase 4: Product Completeness

Primary goal: add human-in-the-loop and smarter conversational product features on top of the stabilized platform.

Recommended order:

1. Expert annotation workflow
   - Build this as a separate operational/reviewer surface, not as an overload of the existing patient-facing chat page.
   - Keep review actions structured so they can later seed fine-tuning or eval datasets.

2. Intelligent medical follow-ups
   - Build the intake/follow-up flow after annotation data structures exist, so corrections and clarifications share the same schema patterns when possible.
   - Keep guardrails explicit: clarification should improve retrieval context, not simulate diagnosis.

Definition of done for Phase 4:

- reviewer workflow produces reusable structured corrections
- follow-up experience improves answer quality without degrading citation discipline

## Engineering Notes for the Next Implementer

- Prefer building on the new runtime/context helpers; do not reintroduce module-level mutable state.
- Treat `GET /health` as the canonical lightweight operational endpoint and extend it rather than creating overlapping status routes unless there is a strong product reason.
- Keep frontend error handling centralized in `frontend/src/lib/utils/api.ts`.
- Preserve SSE terminal-event compatibility for `/chat`; additive fields are fine.
- When adding medical-query expansion, keep the expansion provider separate from HyDE/HyPE so each can be toggled and evaluated independently.
- For new persistence work, preserve existing interfaces first and swap implementations second.

## Suggested First Tickets

1. Implement table/list-preserving semantic chunking with focused retrieval-eval coverage.
2. Add a feature-flagged medical query expansion provider interface with a no-op default implementation.
3. Extend reranking evals to compare current cross-encoder behavior against baseline and tuned candidate windows.
4. Design the SQLite migration for chat history and evaluation metadata behind existing storage interfaces.
