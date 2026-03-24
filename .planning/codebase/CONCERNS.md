# Codebase Concerns and Technical Debt

**Generated:** 2026-03-22
**Status:** Active Analysis

## Overview

This document catalogs known concerns, technical debt, and areas requiring attention in the qna-medical-referenced codebase. Items are categorized by severity and type.

---

## 1. Large Files Requiring Refactoring

### Backend (Python)

#### `src/rag/runtime.py` (991 lines)
- **Issue:** Monolithic RAG runtime module
- **Concerns:**
  - Multiple responsibilities: query expansion, retrieval orchestration, MMR diversification, HyDE/HyPE integration
  - Global state management for vector store initialization
  - Complex retrieval logic with multiple search modes (rrf_hybrid, semantic_only, bm25_only)
- **Recommendation:** Split into separate modules for query expansion, retrieval orchestration, and diversification

#### `src/app/routes/evaluation.py` (891 lines)
- **Issue:** Large API route module
- **Concerns:**
  - Multiple endpoints in single file (latest, runs, history, steps, debug)
  - Complex file I/O and data transformation logic
  - Mixed concerns: routing, data access, serialization
- **Recommendation:** Extract data access layer to separate service module

#### `src/ingestion/steps/download_web.py` (745 lines)
- **Issue:** Complex web download orchestration
- **Concerns:**
  - Manifest generation and URL management mixed with download logic
  - Multiple retry strategies and error handling patterns
  - Hardcoded URL lists (recently extracted to config but legacy code remains)
- **Recommendation:** Separate manifest management from download execution

#### `src/evals/dataset_builder.py` (658 lines)
- **Issue:** Heavy dataset construction logic
- **Concerns:**
  - Complex synthetic data generation orchestration
  - Multiple transformation strategies in single module
- **Recommendation:** Consider strategy pattern for different dataset types

### Frontend (Svelte/TypeScript)

#### `frontend/src/routes/+page.svelte` (894 lines)
- **Issue:** Massive monolithic chat interface component
- **Concerns:**
  - Chat UI, pipeline visualization, source display all in one file
  - Complex state management for messages, sources, pipeline steps
  - Multiple concerns: UI, API calls, data transformation, event handling
- **Recommendation:** Extract to separate components (ChatInterface, SourcePanel, PipelineVisualization)

#### `frontend/src/lib/components/PipelinePanel.svelte` (772 lines)
- **Issue:** Large pipeline visualization component
- **Concerns:**
  - Complex flow diagram rendering mixed with data fetching
  - Multiple visualization modes (flow, timing, metrics)
- **Recommendation:** Split into visualization-specific components

#### `frontend/src/lib/components/IngestionTab.svelte` (454 lines)
- **Issue:** Large tab component with complex state
- **Concerns:**
  - Multiple data sources and aggregation logic
  - Complex filtering and sorting logic
- **Recommendation:** Extract data fetching and transformation to separate modules

---

## 2. Global State Management

### Backend Global Variables

Multiple modules use module-level global state, which complicates testing and creates implicit dependencies:

1. **`src/rag/runtime.py`**
   - `_vector_store_initialized`
   - `_vector_store_initialized_signature`
   - Concern: Initialization state tracked globally, complicates testing

2. **`src/ingestion/indexing/vector_store.py`**
   - `_vector_store`
   - `_vector_store_runtime_config`
   - `_vector_store_runtime_signature`
   - Concern: Singleton pattern prevents concurrent testing

3. **`src/ingestion/steps/load_pdfs.py`**
   - `PDF_EXTRACTOR_STRATEGY`
   - `PDF_TABLE_EXTRACTOR`
   - Concern: Runtime configuration via globals

4. **`src/ingestion/steps/convert_html.py`**
   - `HTML_EXTRACTOR_STRATEGY`
   - `PAGE_CLASSIFICATION_ENABLED`
   - `HTML_EXTRACTOR_MODE`
   - Concern: Multiple global config flags

5. **`src/ingestion/steps/chunking/config.py`**
   - `STRUCTURED_CHUNKING_ENABLED`
   - `SOURCE_CHUNK_CONFIGS_OVERRIDE`
   - Concern: Override mechanism creates hidden state

6. **`src/ingestion/steps/load_markdown.py`**
   - `INDEX_ONLY_CLASSIFIED_PAGES`
   - Concern: Feature flag as global variable

**Recommendation:** Implement dependency injection or configuration objects passed to functions rather than module-level globals.

---

## 3. Error Handling Concerns

### Broad Exception Catching

Multiple instances of bare `except Exception:` or overly broad exception handling:

- **`src/usecases/chat.py`**: Lines 129, 220, 226, 239
- **`src/rag/runtime.py`**: Line 181
- **`src/rag/hyde.py`**: Lines 95, 302
- **`src/experiments/wandb_tracking.py`**: Lines 25, 260, 339, 352
- **`src/ingestion/steps/convert_html.py`**: Lines 130, 153 (for optional dependency handling)

**Concerns:**
- Swallows unexpected errors
- Makes debugging difficult
- May hide critical failures

**Recommendation:** Catch specific exceptions, use domain-specific exceptions (see `AGENTS.md`), ensure all exceptions are logged before being caught.

---

## 4. Type Safety Issues

### Type Ignore Comments

Multiple `# type: ignore` comments indicating type checking issues:

- **`src/rag/runtime.py:208`**: `# type: ignore[no-any-return]`
- **`src/app/routes/evaluation.py:170`**: `# type: ignore[no-any-return]`
- **`src/ingestion/steps/chunking/core.py`**: Lines 361-364 (multiple `# type: ignore[call-overload]`)
- **`src/evals/deepeval_models.py:33`**: `# type: ignore[assignment]`
- **`src/evals/synthetic/generator.py`**: Lines 39, 42 (call-arg issues)

**Concerns:**
- Type safety is being bypassed
- May indicate incorrect type annotations
- Increases runtime error risk

**Recommendation:** Fix underlying type issues rather than suppressing them.

### Any Types in Frontend

Frontend code uses `any` and `unknown` types extensively:
- `frontend/src/lib/types.ts:35`: `details: Record<string, unknown>`
- Multiple uses of `any` in component props

**Recommendation:** Define proper interfaces for data structures.

---

## 5. Configuration and Hardcoded Values

### Hardcoded Localhost URLs

Multiple hardcoded localhost references:
- **`src/config/settings.py:42`**: CORS origins hardcoded
- **`frontend/src/routes/+page.svelte:14`**: `API_URL` defaults to localhost
- **`frontend/src/routes/eval/+page.svelte`**: Same API_URL pattern

**Concerns:**
- Deployment requires code changes
- Environment-specific values in source code
- Frontend rebuild needed for different environments

**Recommendation:** Use environment variables consistently (partially done with `VITE_API_URL`, but needs improvement).

### Magic Numbers

- **`src/rag/runtime.py`**:
  - `_RETRIEVAL_OVERFETCH_MULTIPLIER = 4`
  - `_MAX_CHUNKS_PER_SOURCE_PAGE = 2`
  - `_MAX_CHUNKS_PER_SOURCE = 3`
  - `_MMR_LAMBDA = 0.75`

**Concerns:** Tuning parameters not in configuration files

**Recommendation:** Move to YAML configuration for easier experimentation.

---

## 6. Deprecated Code

### Deprecated Endpoints

- **`src/app/routes/history.py`**: Lines 38, 49
  - Legacy `session_id` paths marked as deprecated
  - Anonymous session support being phased out

**Concerns:** Deprecated code increases maintenance burden

**Recommendation:** Set timeline for removal of deprecated features.

---

## 7. Performance Concerns

### Sleep Calls in Async Code

Multiple `sleep()` calls that may indicate blocking operations:
- **`src/evals/assessment/answer_eval.py`**: Retry delays with `asyncio.sleep()`
- **`src/infra/llm/qwen_client.py`**: Rate limiting with `time.sleep()` and `asyncio.sleep()`

**Concerns:**
- May block event loops if not properly async
- Could indicate missing rate limiting middleware

**Recommendation:** Implement proper rate limiting libraries, ensure all I/O is non-blocking.

### Large File Processing

- PDF and HTML processing loads entire documents into memory
- No streaming or chunked processing for large files

**Concerns:** Memory-intensive operations may fail on large documents

**Recommendation:** Implement streaming processing for large files.

---

## 8. Security Concerns

### API Key Management

- **`src/config/settings.py`**: API keys stored in settings with empty defaults
  - `dashscope_api_key: str = ""`
  - `wandb_api_key: str = ""`

**Concerns:**
- Empty defaults may cause runtime errors
- No validation that required keys are present

**Recommendation:** Implement startup validation for required credentials, fail fast if missing.

### CORS Configuration

- Hardcoded CORS origins in settings
- No wildcard for development

**Concerns:** Deployment requires configuration changes

**Recommendation:** Environment-based CORS configuration with sensible defaults.

---

## 9. Code Smells and Anti-Patterns

### Optional Dependency Handling

**`src/ingestion/steps/convert_html.py`**:
```python
try:
    import trafilatura  # type: ignore[assignment]
except Exception:  # pragma: no cover - optional dependency
    trafilatura = None
```

**Concerns:**
- Silent failures for optional dependencies
- Multiple optional deps with same pattern
- Difficult to debug when optional deps are missing

**Recommendation:** Use explicit feature flags or dependency injection.

### Inconsistent Return Types

Multiple functions return different types based on runtime conditions:
- JSON parsing may return dict, list, or None
- Union types not always properly annotated

**Recommendation:** Use proper type annotations and consider Result types for fallible operations.

---

## 10. Testing Gaps

### Test Coverage

Based on file analysis:
- Large files like `runtime.py` (991 lines) need comprehensive test coverage
- Frontend components have limited test coverage
- E2E tests exist but may not cover all edge cases

**Recommendation:**
- Increase unit test coverage for complex modules
- Add integration tests for RAG pipeline
- Expand frontend component testing

### Test Artifacts

- `.pytest_cache/` and `__pycache__` present in source tree
- `.mypy_cache/` contains cache files

**Concerns:** Build artifacts not properly excluded

**Recommendation:** Ensure `.gitignore` is comprehensive (currently looks good, but verify).

---

## 11. Documentation Issues

### Missing Docstrings

- Some complex functions lack comprehensive docstrings
- Type hints present but parameter descriptions missing

**Recommendation:** Complete docstring coverage for public APIs.

### Outdated Documentation

- Some plans and reports reference old patterns
- Code review remediation docs indicate completed tasks

**Recommendation:** Archive completed plans, update architecture docs to reflect current state.

---

## 12. Dependency Management

### Version Pinning

**`pyproject.toml`**:
- `pypdf` uses `>=4.0,<6.0` (wide range)
- Some dependencies use `>=` without upper bounds

**Concerns:** Future versions may introduce breaking changes

**Recommendation:** Consider more conservative version ranges for critical dependencies.

### Optional Dependencies

Multiple optional dependency groups:
- `dev`, `evaluation`, `chunkers`, `extraction`, `test`

**Concerns:** Complex dependency matrix may cause confusion

**Recommendation:** Document which features require which optional deps.

---

## 13. Frontend-Specific Concerns

### Component Complexity

- **DrillDownModal.svelte** (306 lines): Complex modal with drill-down logic
- **ThresholdEditor.svelte** (338 lines): Complex form with validation
- **DocumentInspector.svelte** (419 lines): Large inspector component

**Recommendation:** Extract sub-components to reduce complexity.

### Type Safety

- Extensive use of `unknown` and `any` types
- Some components use `Record<string, unknown>` for props

**Recommendation:** Define proper TypeScript interfaces.

### State Management

- Multiple components use local `$state` without state management library
- Complex parent-child state passing

**Recommendation:** Consider state management library for complex flows (Svelte stores or similar).

---

## 14. Infrastructure Concerns

### Vector Store Management

- Global singleton pattern for vector store
- No connection pooling management
- Runtime config changes may cause inconsistencies

**Recommendation:** Implement proper lifecycle management, connection pooling.

### Chat History Storage

- File-based storage (`file_chat_history_store.py`)
- No migration path for production

**Recommendation:** Implement database-backed storage for production use.

---

## Summary by Priority

### High Priority (Address Soon)
1. Global state management - affects testability and concurrency
2. Large file refactoring - impacts maintainability
3. Error handling improvements - affects reliability
4. Type safety fixes - prevents runtime errors

### Medium Priority (Plan for Next Sprint)
1. Configuration management - improves deployment flexibility
2. Performance optimizations - better resource utilization
3. Testing coverage expansion - prevents regressions
4. Security hardening - production readiness

### Low Priority (Technical Debt)
1. Documentation updates
2. Deprecated code removal
3. Code style consistency
4. Dependency version management

---

## Maintenance Recommendations

1. **Establish refactoring cadence** - Tackle one large file per sprint
2. **Implement dependency injection** - Reduce global state usage
3. **Strengthen type checking** - Fix type ignore comments
4. **Improve error handling** - Use domain-specific exceptions
5. **Expand test coverage** - Focus on complex modules
6. **Configuration as code** - Move magic numbers to config
7. **Security audit** - Review API key management and CORS setup
8. **Performance monitoring** - Add metrics for slow operations

---

**Last Updated:** 2026-03-22
**Next Review:** 2026-04-22
