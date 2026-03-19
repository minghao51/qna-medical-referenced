# Implementation Plan: Pipeline Eval/Ingestion Improvements

**Created**: 2026-03-19
**Status**: Ready for Implementation
**Priority**: High → Medium → Low

---

## Overview

This plan addresses identified gaps in the medical RAG pipeline evaluation and ingestion system. The comprehensive review revealed strong test coverage (119 passing) but identified specific areas needing improvement.

**Current State**:
- ✅ 119 tests passing (backend)
- ✅ 34 frontend E2E tests passing
- ✅ Retry logic for DeepEval timeouts
- ✅ Type safety improvements
- ⚠️ No backend E2E tests with real APIs
- ⚠️ Limited error handling tests
- ⚠️ HyDE not implemented

---

## Phase 1: High Priority (Critical Gaps)

### Task 1.1: Backend E2E Test with Real APIs

**Problem**: All backend tests use mocks - no validation of real API integrations.

**Solution**: Create comprehensive E2E test using actual external services.

**Files to Create**:
- `tests/test_backend_e2e_real_apis.py` (new file)

**Implementation Steps**:

1. **Create test fixture setup** (`tests/test_backend_e2e_real_apis.py`)
   ```python
   @pytest.fixture(scope="session")
   def real_api_config():
       """Load real API credentials from environment."""
       return {
           "dashscope_api_key": os.getenv("DASHSCOPE_API_KEY"),
           "wandb_project": os.getenv("WANDB_PROJECT"),
           "enable_real_tests": os.getenv("ENABLE_REAL_API_TESTS") == "1"
       }

   @pytest.fixture
   def skip_without_real_apis(real_api_config):
       """Skip test unless real APIs are explicitly enabled."""
       if not real_api_config["enable_real_apis"]:
           pytest.skip("Set ENABLE_REAL_API_TESTS=1 to run real API tests")
   ```

2. **Test document download & chunking** (L0-L3 stages)
   - Download real PDF from medical guideline URL
   - Verify HTML/Markdown conversion
   - Validate chunking produces reasonable chunks
   - Verify embeddings generated successfully

3. **Test retrieval with real embeddings** (L4-L5 stages)
   - Build vector store with real documents
   - Test semantic search returns relevant results
   - Test hybrid search (semantic + BM25)
   - Verify RRF fusion works correctly

4. **Test answer generation & evaluation** (L6 stage)
   - Generate answer for real medical query
   - Run DeepEval metrics with real API
   - Verify all 6 metrics produce scores
   - Validate W&B logging works

5. **Test end-to-end pipeline**
   - Run complete L0-L6 pipeline
   - Verify all stages complete successfully
   - Check artifact persistence
   - Validate W&B run created

**Acceptance Criteria**:
- [ ] Test can run with `ENABLE_REAL_API_TESTS=1 uv run pytest tests/test_backend_e2e_real_apis.py`
- [ ] All L0-L6 stages validated with real APIs
- [ ] Test completes in <10 minutes
- [ ] Cleanup removes test artifacts

**Estimated Time**: 4-6 hours

---

### Task 1.2: Error Handling & Edge Case Tests

**Problem**: Limited tests for error scenarios and edge cases.

**Solution**: Add comprehensive error handling tests.

**Files to Modify**:
- `tests/test_ingestion_error_handling.py` (new file)
- `tests/test_eval_error_handling.py` (new file)

**Implementation Steps**:

1. **Network failure tests** (`tests/test_ingestion_error_handling.py`)
   - Mock HTTP timeouts during document download
   - Verify retry logic works
   - Test partial download recovery
   - Validate error messages are clear

2. **Malformed document tests**
   - Test with corrupted PDF files
   - Test with HTML that has no content
   - Test with empty Markdown files
   - Verify graceful degradation

3. **Empty dataset tests**
   - Test retrieval with empty vector store
   - Test evaluation with empty query list
   - Test chunking with no documents
   - Verify no crashes, clear errors

4. **API timeout tests** (`tests/test_eval_error_handling.py`)
   - Mock Dashscope API timeouts
   - Verify retry logic triggers
   - Test cache still works during failures
   - Validate partial results returned

5. **Invalid input tests**
   - Test with None/empty queries
   - Test with negative top_k values
   - Test with invalid retrieval options
   - Verify validation errors raised

**Acceptance Criteria**:
- [ ] 20+ new error handling tests
- [ ] All edge cases covered
- [ ] Error messages are actionable
- [ ] No crashes on invalid inputs

**Estimated Time**: 3-4 hours

---

### Task 1.3: HyDE Query Expansion Implementation

**Problem**: HyDE (Hypothetical Document Embeddings) is mentioned in docs but not implemented.

**Solution**: Implement HyDE query expansion with tests.

**Files to Create**:
- `src/rag/hyde.py` (new file)
- `tests/test_hyde.py` (new file)

**Implementation Steps**:

1. **Implement HyDE query generation** (`src/rag/hyde.py`)
   ```python
   async def generate_hypothetical_answer(
       query: str,
       client: LLMClient,
       max_length: int = 200,
   ) -> str:
       """Generate a hypothetical answer to use for query expansion."""
       prompt = f"""Answer this question concisely (max {max_length} words):
       {query}

       Provide a factual, medical answer that would appear in a clinical guideline."""
       return await client.a_generate(prompt=prompt, context="")

   async def expand_query_with_hyde(
       query: str,
       client: LLMClient,
       enable_hyde: bool = True,
   ) -> list[str]:
       """Expand query using HyDE if enabled."""
       if not enable_hyde:
           return [query]

       hypothetical = await generate_hypothical_answer(query, client)
       return [query, hypothetical]
   ```

2. **Integrate with retrieval pipeline** (`src/rag/runtime.py`)
   - Add `enable_hyde` parameter to retrieval functions
   - Use expanded queries for semantic search
   - Aggregate results from all query variants
   - Maintain backward compatibility (default: disabled)

3. **Add configuration support** (`src/config/settings.py`)
   ```python
   hyde_enabled: bool = field(default=False)
   hyde_max_length: int = field(default=200)
   ```

4. **Create tests** (`tests/test_hyde.py`)
   - Test hypothetical answer generation
   - Test query expansion returns original + hypothetical
   - Test HyDE improves retrieval quality
   - Test backward compatibility (disabled by default)
   - Compare HyDE vs non-HyDE retrieval metrics

**Acceptance Criteria**:
- [ ] HyDE generates relevant hypothetical answers
- [ ] Integration with retrieval pipeline works
- [ ] Tests show HyDE improves retrieval (or degrades gracefully)
- [ ] Backward compatible (disabled by default)
- [ ] Configuration via settings

**Estimated Time**: 5-7 hours

---

## Phase 2: Medium Priority (Performance & Scale)

### Task 2.1: Multi-Query Performance Benchmark

**Problem**: Only single-query benchmark exists - no scale testing.

**Solution**: Add a dedicated `scripts/benchmark_deepeval_multi.py` benchmark for multi-query scenarios.

**Files to Modify**:
- `scripts/benchmark_deepeval_multi.py` (new file)

**Implementation Steps**:

1. **Create multi-query benchmark script**
   ```python
   async def benchmark_multi_query(
       queries: list[str],
       top_k: int = 3,
       concurrent: bool = True,
   ) -> dict:
       """Benchmark performance with multiple queries."""
       results = []
       timings = {
           "cold_cache": [],
           "warm_cache": [],
           "total_elapsed_ms": 0,
       }

       # Cold cache run
       start = time.time()
       for query in queries:
           result = await evaluate_single(query, top_k)
           results.append(result)
       timings["cold_cache"].append(...)

       # Warm cache run
       for query in queries:
           result = await evaluate_single(query, top_k)
           results.append(result)
       timings["warm_cache"].append(...)

       return aggregate_metrics(results, timings)
   ```

2. **Use golden_queries.json dataset**
   - Load 21 curated test queries
   - Run benchmark with all queries
   - Measure aggregate performance
   - Compare cold vs warm cache

3. **Add performance metrics**
   - Total time for all queries
   - Average time per query
   - P50, P95, P99 latencies
   - Cache hit rate
   - Memory usage

4. **Generate performance report**
   - Markdown report with tables/charts
   - Comparison to single-query baseline
   - Identify bottlenecks
   - Recommendations for optimization

**Acceptance Criteria**:
- [ ] Script runs all 21 golden queries
- [ ] Generates performance report
- [ ] Identifies bottlenecks
- [ ] Completes in <30 minutes

**Estimated Time**: 3-4 hours

---

### Task 2.2: Concurrent Evaluation Tests

**Problem**: No tests for parallel evaluation - thread safety unverified.

**Solution**: Add concurrent evaluation tests.

**Files to Create**:
- `tests/test_concurrent_evaluation.py` (new file)

**Implementation Steps**:

1. **Test concurrent pipeline runs**
   ```python
   @pytest.mark.asyncio
   async def test_concurrent_pipeline_assessment():
       """Test multiple pipelines can run concurrently."""
       datasets = [
           [{"query": f"Test query {i}"}]
           for i in range(5)
       ]

       results = await asyncio.gather(*[
           run_pipeline_assessment(ds)
           for ds in datasets
       ])

       assert len(results) == 5
       # Verify no data corruption
   ```

2. **Test concurrent metric evaluation**
   - Run 10 queries in parallel
   - Verify all metrics computed
   - Check cache consistency
   - Validate no race conditions

3. **Test concurrent cache access**
   - Multiple processes reading/writing cache
   - Verify cache remains consistent
   - Test cache locking if implemented
   - Validate no corrupted cache entries

4. **Test concurrent artifact writes**
   - Multiple evaluations writing to artifact store
   - Verify no file corruption
   - Test artifact isolation
   - Validate deduplication works

**Acceptance Criteria**:
- [ ] 5+ concurrent tests passing
- [ ] No data corruption or race conditions
- [ ] Cache remains consistent
- [ ] Artifacts properly isolated

**Estimated Time**: 2-3 hours

---

## Phase 3: Low Priority (Nice to Have)

### Task 3.1: Real External Service Integration Tests

**Problem**: No validation against real W&B, Qdrant, Dashscope.

**Solution**: Add integration tests for real external services.

**Files to Create**:
- `tests/test_integration_wandb.py` (new file)
- `tests/test_integration_qdrant.py` (new file)

**Implementation Steps**:

1. **W&B integration tests**
   - Create real W&B project
   - Log metrics and artifacts
   - Verify they appear in UI
   - Test run versioning

2. **Qdrant integration tests** (if using Qdrant)
   - Test real Qdrant collection creation
   - Verify embedding storage
   - Test semantic search
   - Validate filtering

3. **Dashscope integration tests**
   - Test real Qwen model calls
   - Verify streaming responses
   - Test rate limiting
   - Validate error handling

**Acceptance Criteria**:
- [ ] Tests validate real service integrations
- [ ] Require explicit opt-in via environment variables
- [ ] Documented in README

**Estimated Time**: 4-5 hours

---

## Implementation Order

**Recommended Sequence**:

1. **Week 1**: Task 1.1 (Backend E2E) + Task 1.2 (Error Handling)
   - Critical gaps filled first
   - Validates real-world functionality

2. **Week 2**: Task 1.3 (HyDE Implementation)
   - Completes high-priority items
   - Adds new feature capability

3. **Week 3**: Task 2.1 (Multi-Query Benchmark) + Task 2.2 (Concurrent Tests)
   - Performance and scale validation
   - Production readiness

4. **Week 4**: Task 3.1 (Real Service Integration)
   - Nice-to-have completions
   - Full integration validation

---

## Verification Commands

After each task, run:

```bash
# Run new tests
uv run pytest tests/test_<feature>.py -v

# Run full test suite
uv run pytest -v

# Run linter
uv run ruff check .

# Run type checker
uv run mypy src/

# Run benchmark (if applicable)
uv run python scripts/benchmark_<name>.py
```

---

## Success Metrics

**Before Implementation**:
- 119 tests passing
- No real API validation
- Limited error handling
- No HyDE support

**After Implementation**:
- ✅ 150+ tests passing (+30+ new tests)
- ✅ Real API E2E validation
- ✅ Comprehensive error handling
- ✅ HyDE query expansion
- ✅ Performance benchmarks
- ✅ Concurrent safety verified

---

## Notes for Implementation Agent

1. **Environment Variables**: Create `.env.test` file with test API keys
2. **Test Isolation**: Ensure new tests don't require production data
3. **Cleanup**: Add test teardown to remove artifacts
4. **Documentation**: Update README.md with new test instructions
5. **Backward Compatibility**: Maintain existing API contracts
6. **Performance**: Don't slow down existing tests
7. **Error Messages**: Make errors actionable for debugging

---

## Dependencies

**Required**:
- Python 3.13+
- Existing test infrastructure (pytest)
- Mock API responses for non-E2E tests
- Test data fixtures (golden_queries.json)

**Optional**:
- Real API credentials (for E2E tests)
- W&B project access
- Qdrant instance (if using)

---

## Risk Mitigation

**Potential Issues**:
1. Real API tests may be flaky → Add retries and timeouts
2. Concurrent tests may reveal race conditions → Fix immediately
3. HyDE may not improve quality → Keep disabled by default
4. Performance tests may be slow → Run in CI only

**Mitigation**:
- All new tests opt-in via environment variables
- Comprehensive mocking for unit tests
- Clear documentation for test requirements
- Fallback to cached results when possible
