# Implementation Plan Summary - Quick Reference

**File**: `docs/reports/2026-03/20260319-implementation-plan.md` (full details)
**Status**: Ready for handoff to another agent
**Total Estimated Time**: 21-29 hours across 4 weeks

---

## 🎯 High Priority Tasks (Week 1-2)

### 1. Backend E2E Test with Real APIs (4-6 hours)
- **File**: `tests/test_backend_e2e_real_apis.py` (new)
- **What**: Test L0-L6 pipeline with actual external services
- **Why**: All current tests use mocks - need real API validation
- **Trigger**: `ENABLE_REAL_API_TESTS=1 uv run pytest`

### 2. Error Handling Tests (3-4 hours)
- **Files**: `tests/test_ingestion_error_handling.py`, `tests/test_eval_error_handling.py` (new)
- **What**: 20+ tests for network failures, malformed docs, empty datasets
- **Why**: Limited edge case coverage currently
- **Coverage**: Timeouts, corruption, empty inputs, invalid data

### 3. HyDE Query Expansion (5-7 hours)
- **Files**: `src/rag/hyde.py`, `tests/test_hyde.py` (new)
- **What**: Implement Hypothetical Document Embeddings for query expansion
- **Why**: Mentioned in docs but not implemented
- **Config**: `hyde_enabled: bool = False` (disabled by default)

---

## 🔧 Medium Priority Tasks (Week 3)

### 4. Multi-Query Performance Benchmark (3-4 hours)
- **File**: `scripts/benchmark_deepeval_multi.py` (new)
- **What**: Benchmark with all 21 golden_queries.json queries
- **Why**: Only single-query benchmark exists
- **Metrics**: P50/P95/P99 latency, cache hit rate, memory usage

### 5. Concurrent Evaluation Tests (2-3 hours)
- **File**: `tests/test_concurrent_evaluation.py` (new)
- **What**: Test 5+ parallel evaluations for thread safety
- **Why**: No validation of concurrent access
- **Coverage**: Cache consistency, artifact isolation, race conditions

---

## 📋 Low Priority Tasks (Week 4)

### 6. Real External Service Integration (4-5 hours)
- **Files**: `tests/test_integration_wandb.py`, `tests/test_integration_qdrant.py` (new)
- **What**: Validate real W&B, Qdrant, Dashscope integrations
- **Why**: No testing against actual production services
- **Trigger**: Opt-in via environment variables

---

## 📊 Success Metrics

**Before**:
- 119 tests passing
- No real API validation
- Limited error handling
- No HyDE support

**After**:
- ✅ **150+ tests passing** (+30 new)
- ✅ Real API E2E validation
- ✅ Comprehensive error handling
- ✅ HyDE query expansion
- ✅ Performance benchmarks
- ✅ Concurrent safety verified

---

## 🚀 Quick Start for Agent

```bash
# Clone and setup
git clone <repo>
cd qna_medical_referenced
uv sync

# Start with High Priority Task 1
# Create tests/test_backend_e2e_real_apis.py
# Follow implementation steps in full plan

# Run new tests
uv run pytest tests/test_backend_e2e_real_apis.py -v

# Verify no regressions
uv run pytest -v
```

---

## 📝 Key Implementation Notes

1. **All new tests are opt-in** via environment variables
2. **Backward compatibility required** - don't break existing APIs
3. **HyDE disabled by default** - add feature, don't change behavior
4. **Real API tests isolated** - shouldn't affect regular test suite
5. **Performance targets** - don't slow down existing tests
6. **Error messages** - make them actionable for debugging

---

## 🎁 Deliverables

Each task produces:
- ✅ Working code with type hints
- ✅ Comprehensive tests
- ✅ Documentation (docstrings, comments)
- ✅ Verification commands tested
- ✅ No regressions in existing tests

---

## 📖 Full Details

See `docs/reports/2026-03/20260319-implementation-plan.md` for:
- Detailed implementation steps
- Code examples
- Acceptance criteria
- Risk mitigation
- Test data requirements
- Configuration options
