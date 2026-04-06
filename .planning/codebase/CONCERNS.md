# Codebase Concerns

**Analysis Date:** 2026-04-06

## Tech Debt

**Duplicated `_VALID_SEARCH_MODES` constant:**
- Issue: The set `{"rrf_hybrid", "semantic_only", "bm25_only"}` is defined in both `src/rag/runtime.py:48` and `src/ingestion/indexing/chroma_store.py:39`. If a new search mode is added, both must be updated.
- Files: `src/rag/runtime.py`, `src/ingestion/indexing/chroma_store.py`
- Impact: Risk of inconsistency between runtime and storage layer search mode validation
- Fix approach: Extract to a shared constants module (e.g., `src/config/constants.py`) and import from there

**Module-level global state for configuration:**
- Issue: Multiple modules use `global` variables for runtime configuration (`_html_config`, `SOURCE_CHUNK_CONFIGS_OVERRIDE`, `PDF_EXTRACTOR_STRATEGY`, `INDEX_ONLY_CLASSIFIED_PAGES`, `_reranker_instance`, `_vector_store_initialized`). This makes the code non-thread-safe and hard to test in isolation.
- Files: `src/ingestion/steps/convert_html.py`, `src/ingestion/steps/chunking/config.py`, `src/ingestion/steps/load_pdfs.py`, `src/ingestion/steps/load_markdown.py`, `src/rag/reranker.py`, `src/rag/runtime.py`, `src/infra/di.py`
- Impact: Race conditions in concurrent requests, test pollution between runs, difficult to reason about state
- Fix approach: Use a proper configuration context object or dependency injection for all runtime settings

**Heavy use of `except Exception:` (bare exception catching):**
- Issue: 37+ instances of `except Exception:` across the codebase swallow all errors silently, making debugging difficult and potentially hiding real bugs.
- Files: `src/app/routes/evaluation.py`, `src/evals/assessment/orchestrator.py`, `src/ingestion/steps/convert_html.py`, `src/ingestion/steps/download_web.py`, `src/evals/dataset_builder.py`, `src/app/routes/chat.py`, `src/usecases/chat.py`, `src/evals/assessment/answer_eval.py`, `src/ingestion/steps/load_pdfs.py`, `src/source_metadata.py`, and more
- Impact: Silent failures, hidden bugs, difficult production debugging
- Fix approach: Catch specific exception types; log all caught exceptions at minimum

**`print()` statements in production code:**
- Issue: 245+ `print()` calls scattered across source files instead of using the `logging` module. This includes pipeline steps (`download_web.py`, `convert_html.py`), runtime code (`runtime.py`), and CLI modules.
- Files: `src/ingestion/steps/download_web.py`, `src/ingestion/steps/convert_html.py`, `src/usecases/pipeline.py`, `src/rag/runtime.py`, `src/cli/eval_pipeline.py`, `src/ingestion/indexing/migrate.py`, `scripts/run_variant_clean.py`
- Impact: No log level control, no structured logging, output goes to stdout unconditionally
- Fix approach: Replace all `print()` with `logging.info()`, `logging.debug()`, etc.

**Custom YAML-like parser in `experiments/config.py`:**
- Issue: The file implements a custom scalar parser (`_parse_scalar`, `_strip_comment`) instead of using a proper YAML/JSON library. This is fragile and doesn't handle edge cases.
- Files: `src/experiments/config.py`
- Impact: Parsing bugs with complex values, maintenance burden
- Fix approach: Use PyYAML or keep experiment config as JSON

**`os.environ` mutation at runtime:**
- Issue: The orchestrator mutates `os.environ` directly to pass configuration between pipeline stages (`HYPE_ENABLED`, `HYPE_SAMPLE_RATE`, `COLLECTION_NAME`). This is a side-effect-heavy pattern.
- Files: `src/evals/assessment/orchestrator.py:388-393`, `src/config/settings.py:432-433`
- Impact: Non-deterministic behavior, test interference, thread-unsafe
- Fix approach: Pass configuration explicitly through function parameters or a config context

**Duplicate config dataclasses in `runtime.py`:**
- Issue: `RuntimeRetrievalConfig` (line 52) and `RetrievalDiversityConfig` (line 79) have nearly identical fields (overfetch_multiplier, max_chunks_per_source_page, max_chunks_per_source, mmr_lambda, search_mode, enable_hyde, hyde_max_length, enable_hype). They should be one dataclass or use inheritance.
- Files: `src/rag/runtime.py:52-92`
- Impact: Keeping them in sync is error-prone; confusion about which to use
- Fix approach: Merge into a single dataclass or use inheritance

**63 instances of `except Exception` (higher than previously counted):**
- Issue: Updated count shows 63 bare exception catches across the codebase, not 37. Many lack logging or re-raising, making debugging nearly impossible.
- Files: All modules under `src/`, notably `src/app/routes/evaluation.py:161,171,616,685,956,1024`, `src/usecases/chat.py:129,220,226,239`, `src/evals/assessment/orchestrator.py:53,281,492`
- Impact: Silent failures across the entire application; failures in LLM calls, file I/O, and evaluation steps are invisible
- Fix approach: Catch specific exception types; log all caught exceptions at minimum; use structured error handling

**Duplicate config dataclasses in `runtime.py`:**
- Issue: `RuntimeRetrievalConfig` (line 52) and `RetrievalDiversityConfig` (line 79) have nearly identical fields (overfetch_multiplier, max_chunks_per_source_page, max_chunks_per_source, mmr_lambda, search_mode, enable_hyde, hyde_max_length, enable_hype). They should be one dataclass or use inheritance.
- Files: `src/rag/runtime.py:52-92`
- Impact: Keeping them in sync is error-prone; confusion about which to use
- Fix approach: Merge into a single dataclass or use inheritance

**63 instances of `except Exception` (higher than previously counted):**
- Issue: Updated count shows 63 bare exception catches across the codebase, not 37. Many lack logging or re-raising, making debugging nearly impossible.
- Files: All modules under `src/`, notably `src/app/routes/evaluation.py:161,171,616,685,956,1024`, `src/usecases/chat.py:129,220,226,239`, `src/evals/assessment/orchestrator.py:53,281,492`
- Impact: Silent failures across the entire application; failures in LLM calls, file I/O, and evaluation steps are invisible
- Fix approach: Catch specific exception types; log all caught exceptions at minimum; use structured error handling

## Known Bugs

**`_read_json_if_exists` returns empty dict on any parse error:**
- Symptoms: Corrupted or partially written JSON files are silently treated as empty data, causing downstream code to operate on missing data without warning.
- Files: `src/app/routes/evaluation.py:166-172`
- Trigger: Disk full during write, concurrent write, or manual file edit
- Workaround: None — no alerting on corrupted files

**HyDE sync version is a no-op but doesn't warn:**
- Symptoms: `_expand_queries()` documents that it "does not perform LLM-based HyDE expansion" but callers may not realize they're getting baseline-only results.
- Files: `src/rag/runtime.py:155-184`
- Trigger: Calling `retrieve_context()` with HyDE enabled
- Workaround: Use the async version `retrieve_context_with_trace()` instead

**`pass` statements in error handlers:**
- Symptoms: Several `except` blocks contain only `pass`, completely swallowing errors. Found in `convert_html.py:35,40`, `dataset_builder.py:345`, `chat.py:227`.
- Files: `src/ingestion/steps/convert_html.py:35,40`, `src/evals/dataset_builder.py:345`, `src/usecases/chat.py:227`
- Trigger: Any import failure or runtime error in the protected block
- Workaround: None — errors are completely invisible

## Security Considerations

**Hardcoded test API key in test fixtures:**
- Risk: Test files contain `"test-api-key"` and `"test-key"` strings. While not production secrets, they normalize the pattern of embedding keys in code.
- Files: `tests/conftest.py`, `tests/test_settings.py`, `tests/test_settings_deepeval.py`
- Current mitigation: Keys are clearly test values, not real credentials
- Recommendations: Use a fixture factory or mock objects instead of string literals

**`.env` file in gitignore but `.env.example` in repo:**
- Risk: The `.env.example` file contains placeholder values showing the exact structure of secrets. If a developer accidentally commits `.env`, the pattern is well-known.
- Files: `.env.example`
- Current mitigation: `.env` is in `.gitignore`
- Recommendations: Consider using a secrets manager or pre-commit hook to prevent `.env` commits

**API key authentication uses simple string comparison:**
- Risk: `authenticate_api_key()` in `src/app/middleware/auth.py` does a simple membership check against a comma-separated list of API keys. No rate limiting per key, no key rotation, no audit logging of key usage. Not timing-safe.
- Files: `src/app/middleware/auth.py:48-69`
- Current mitigation: Rate limiting middleware exists separately
- Recommendations: Add per-key rate limiting, key expiration, usage audit logging, and `hmac.compare_digest` for timing-safe comparison

**No input length validation enforced at HTTP middleware level:**
- Risk: While `MAX_MESSAGE_LENGTH` exists in settings, it's not clear that all endpoints enforce it before reading the full request body. Large payloads could cause memory issues or expensive LLM calls.
- Files: `src/app/routes/chat.py`, `src/app/schemas/chat.py`
- Current mitigation: `sanitize_message` validator in chat schemas
- Recommendations: Enforce max length at the HTTP middleware level before request body is fully read

**`src/infra/llm/qwen_client.py` contains a `requests.get` to `api.example.com`:**
- Risk: Line 60 contains `return requests.get("https://api.example.com")` which appears to be placeholder/mock code that could be accidentally executed.
- Files: `src/infra/llm/qwen_client.py:60`
- Current mitigation: Likely in an unreachable code path
- Recommendations: Remove or clearly mark as dead code

**CORS configuration defaults to localhost:**
- Risk: If deployed without updating `CORS_ALLOWED_ORIGINS`, the API may be accessible from any origin.
- Files: `src/app/factory.py`, `.env.example`
- Current mitigation: Default includes localhost dev servers only
- Recommendations: Document this clearly; add startup warning if CORS includes `*`

## Performance Bottlenecks

**Large files (>500 lines) that need refactoring:**
- `src/rag/runtime.py` (1065 lines) — Core retrieval logic, handles indexing, search, HyDE, reranking all in one file
- `src/app/routes/evaluation.py` (1028 lines) — API routes mixed with file I/O, metrics aggregation, and JSON serialization
- `frontend/src/routes/+page.svelte` (894 lines) — Main page component with chat, history, pipeline visualization, and source display
- `src/ingestion/indexing/chroma_store.py` (786 lines) — Vector store with search, embedding, MMR, HyDE question storage
- `frontend/src/lib/components/PipelinePanel.svelte` (772 lines) — Complex UI component with multiple sub-views
- `src/ingestion/steps/download_web.py` (745 lines) — Download logic for 6 different content sources
- `src/evals/dataset_builder.py` (652 lines) — Dataset construction with fixture loading, LLM synthesis, normalization
- `src/evals/assessment/retrieval_eval.py` (605 lines) — Retrieval evaluation with multiple ablation sweeps
- `src/evals/assessment/orchestrator.py` (599 lines) — Orchestration of full evaluation pipeline
- `src/ingestion/steps/convert_html.py` (586 lines) — HTML-to-Markdown conversion with multiple extractor strategies
- `src/experiments/config.py` (519 lines) — Experiment config loading with custom parser

**MMR reranking is O(n²) in the number of candidates:**
- Problem: `_mmr_rerank()` in `src/rag/runtime.py:411-435` compares every remaining candidate against every selected item. With large `top_k` and high `overfetch_multiplier`, this becomes expensive.
- Files: `src/rag/runtime.py:411-435`
- Cause: Greedy MMR algorithm with no early termination or approximation
- Improvement path: Use approximate MMR or cap the candidate pool before reranking

**`_content_similarity` tokenizes both strings on every comparison:**
- Problem: Called inside the inner loop of `_mmr_rerank()`, tokenizing the same content strings repeatedly.
- Files: `src/rag/runtime.py:392-400`
- Cause: No caching of tokenized content
- Improvement path: Pre-tokenize all candidate content before entering the MMR loop

**ChromaDB `_get_all_documents()` loads entire collection into memory on every search:**
- Problem: `_build_keyword_index()`, `_build_term_frequencies()`, and `_keyword_score()` all call `_get_all_documents()` which fetches every document from ChromaDB. This is called on every search when the index is dirty.
- Files: `src/ingestion/indexing/chroma_store.py:221-233`
- Cause: BM25 keyword index is rebuilt from scratch on every dirty state
- Improvement path: Maintain incremental keyword index updates instead of full rebuilds

**Evaluation retrieval runs are fully sequential:**
- Problem: `evaluate_retrieval()` in `src/evals/assessment/retrieval_eval.py` processes each dataset item one at a time, each making a full RAG pipeline call. For datasets with 100+ queries, this is very slow.
- Files: `src/evals/assessment/retrieval_eval.py:136+`
- Cause: No batching or parallelism in the evaluation loop
- Improvement path: Use `asyncio.gather` with controlled concurrency (similar to answer_eval.py pattern)

**Large JSON files read synchronously on every evaluation request:**
- Problem: Evaluation endpoints read `summary.json`, `step_metrics.json`, `manifest.json` from disk on every request with no caching.
- Files: `src/app/routes/evaluation.py` (multiple endpoints)
- Cause: No in-memory cache for evaluation results
- Improvement path: Add LRU cache with TTL for evaluation data; invalidate on new runs

**No database indexes — file-based storage:**
- Problem: All evaluation runs, chat history, and artifacts are stored as JSON files on disk. No indexing means O(n) scans for lookups.
- Files: `src/infra/storage/file_chat_history_store.py`, `src/evals/artifacts.py`, `src/app/routes/evaluation.py`
- Cause: Designed for simplicity, not scale
- Improvement path: Add an index file or migrate to SQLite for runs/history if scale grows

**Batched embedding without async:**
- Problem: `embed_texts` processes texts in batches synchronously (`for i in range(0, len(texts), batch_size)`).
- Files: `src/ingestion/indexing/embedding.py:49`
- Cause: LLM API calls are I/O-bound but processed sequentially
- Improvement path: Use async HTTP client for embedding batches

**`_diversify_results` has a fallback loop that can defeat diversity constraints:**
- Problem: When diversity constraints are too strict and fewer than `top_k` results remain, the fill loop (line 492-502) adds back duplicates by ID only, ignoring source/page limits.
- Files: `src/rag/runtime.py:492-502`
- Cause: Designed to always return `top_k` results, but this undermines the diversity guarantees
- Improvement path: Either accept fewer results or relax constraints more gracefully

**`_diversify_results` has a fallback loop that can defeat diversity constraints:**
- Problem: When diversity constraints are too strict and fewer than `top_k` results remain, the fill loop (line 492-502) adds back duplicates by ID only, ignoring source/page limits.
- Files: `src/rag/runtime.py:492-502`
- Cause: Designed to always return `top_k` results, but this undermines the diversity guarantees
- Improvement path: Either accept fewer results or relax constraints more gracefully

## Fragile Areas

**Runtime index initialization with global state:**
- Files: `src/rag/runtime.py`
- Why fragile: Uses `_vector_store_initialized` and `_vector_store_initialized_signature` globals to prevent re-indexing. If signature computation changes or state gets out of sync, the index may be rebuilt unnecessarily or skipped when it shouldn't be.
- Safe modification: Always reset both globals together; test with `scripts/run_variant_clean.py`
- Test coverage: `tests/test_runtime_index_initialization.py` covers basic cases but not concurrent access

**Optional dependency handling with bare `except Exception: pass`:**
- Files: `src/ingestion/steps/convert_html.py:32-45`, `src/ingestion/steps/load_pdfs.py:23-38`
- Why fragile: If an optional dependency partially installs or has import-time side effects, failures are silently swallowed.
- Safe modification: Log warnings when optional deps fail to import
- Test coverage: No tests for missing optional dependency scenarios

**Custom experiment config parser:**
- Files: `src/experiments/config.py`
- Why fragile: Hand-rolled parser for YAML-like syntax with comment stripping and scalar parsing. Edge cases (nested structures, special characters) may break silently.
- Safe modification: Add comprehensive parser unit tests; consider migrating to JSON
- Test coverage: `tests/test_experiment_config.py` exists but may not cover all edge cases

**ChromaDB factory singleton pattern:**
- Files: `src/ingestion/indexing/chroma_store.py` (ChromaVectorStoreFactory)
- Why fragile: Singleton with `reset()` method for testing. If reset is called during active use, subsequent calls get a fresh instance with lost state.
- Safe modification: Document reset semantics; consider using a factory with explicit lifecycle
- Test coverage: `tests/test_chroma_store.py`, `tests/test_chroma_migration.py`

## Scaling Limits

**File-based chat history:**
- Current capacity: Single JSON file per session
- Limit: File size grows unbounded; no pagination or archival
- Scaling path: Migrate to database-backed storage with TTL-based cleanup

**Evaluation run directory scanning:**
- Current capacity: Scans `data/evals/` directory on every request
- Limit: O(n) filesystem operations per API call; slows with many runs
- Scaling path: Cache run list; use an index file

**In-memory vector store operations:**
- Current capacity: ChromaDB persistent store with in-memory operations for search
- Limit: All documents loaded into memory; large collections will exceed RAM
- Scaling path: Use ChromaDB server mode or migrate to a dedicated vector database

## Dependencies at Risk

**`pypdf>=4.0,<6.0` has an upper bound that may become stale:**
- Risk: Pinning to `<6.0` will eventually block updates. Major PDF library updates often include important security fixes.
- Impact: Unable to receive security patches when pypdf 6.0 is released
- Migration plan: Test against pypdf 6.0 when available and update the constraint

**`deepeval>=2.0.0` is a heavy optional dependency:**
- Risk: DeepEval brings in many transitive dependencies including multiple LLM frameworks. Version conflicts are likely as the ecosystem evolves.
- Impact: `uv sync` may fail or pull incompatible versions
- Migration plan: Pin to a specific minor version and update deliberately

**Frontend dependencies may lack a lockfile:**
- Risk: No `package-lock.json` or `pnpm-lock.yaml` confirmed in the frontend directory. Dependencies may drift between developer machines and CI.
- Impact: Inconsistent builds, "works on my machine" issues
- Migration plan: Commit a lockfile and enforce it in CI

## Missing Critical Features

**No structured logging:**
- Problem: All logging uses `print()` or basic `logging` without structured format (JSON). Makes log aggregation and analysis difficult.
- Blocks: Production observability, alerting, debugging

**No health check for vector store:**
- Problem: No endpoint or mechanism to verify the vector store is operational and populated.
- Blocks: Automated deployment verification, monitoring

**No API versioning:**
- Problem: API routes have no version prefix. Breaking changes will break all clients.
- Blocks: Safe API evolution

## Test Coverage Gaps

**Optional dependency failure scenarios:**
- What's not tested: Behavior when `trafilatura`, `html_to_markdown`, `readability_lxml` are not installed
- Files: `src/ingestion/steps/convert_html.py`, `src/ingestion/steps/load_pdfs.py`
- Risk: Silent degradation in production if optional deps fail to install
- Priority: Medium

**Concurrent access to global state:**
- What's not tested: Multiple simultaneous requests modifying `_html_config`, `_vector_store_initialized`, etc.
- Files: `src/rag/runtime.py`, `src/ingestion/steps/convert_html.py`, `src/ingestion/steps/chunking/config.py`
- Risk: Race conditions in production under load
- Priority: High

**Error paths in evaluation API:**
- What's not tested: Malformed evaluation run directories, corrupted JSON files, missing metrics
- Files: `src/app/routes/evaluation.py`
- Risk: 500 errors on edge cases
- Priority: Medium

**Large-scale retrieval performance:**
- What's not tested: Retrieval with thousands of documents, large query batches
- Files: `src/rag/runtime.py`, `src/ingestion/indexing/chroma_store.py`
- Risk: Performance degradation goes unnoticed
- Priority: Medium

**Frontend error states:**
- What's not tested: API unavailable, malformed responses, network timeouts in Svelte components
- Files: `frontend/src/routes/+page.svelte`, `frontend/src/lib/components/PipelinePanel.svelte`
- Risk: Poor UX on failure
- Priority: Low

---

*Concerns audit: 2026-04-06*
