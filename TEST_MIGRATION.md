# Test Migration Guide

**Date:** 2026-04-20  
**Purpose:** Document the test restructuring from monolithic `tests/` to organized `tests/unit/`, `tests/integration/`, and `tests/e2e/` directories.

## Overview

This document tracks the migration of tests from the root `tests/` directory to a more structured layout following pytest-tagging best practices.

## Deleted Test Files

The following test files were deleted during the restructuring:

### Moved to `tests/unit/`

| Original File | New Location | Notes |
|--------------|--------------|---------|
| `tests/test_ablation_full_results.py` | `tests/unit/test_ablation_full_results.py` | Unchanged |
| `tests/test_answer_eval_cache.py` | `tests/unit/test_answer_eval_cache.py` | Unchanged |
| `tests/test_answer_eval_deepeval_async.py` | `tests/unit/test_answer_eval_deepeval_async.py` | Added `@pytest.mark.slow` |
| `tests/test_chunker.py` | `tests/unit/test_chunker.py` | Unchanged |
| `tests/test_configuration.py` | `tests/unit/test_configuration.py` | Unchanged |
| `tests/test_dataset_builder.py` | `tests/unit/test_dataset_builder.py` | Added `@pytest.mark.slow` |
| `tests/test_deepeval_models.py` | `tests/unit/test_deepeval_models.py` | Added `@pytest.mark.slow` |
| `tests/test_deepeval_models_litellm.py` | `tests/unit/test_deepeval_models_litellm.py` | Unchanged |
| `tests/test_di_container.py` | `tests/unit/test_di_container.py` | Unchanged |
| `tests/test_download_pdfs_manifest.py` | `tests/unit/test_download_pdfs_manifest.py` | Unchanged |
| `tests/test_download_web_manifest.py` | `tests/unit/test_download_web_manifest.py` | Unchanged |
| `tests/test_embedding_cache.py` | `tests/unit/test_embedding_cache.py` | Unchanged |
| `tests/test_eval_artifacts.py` | `tests/unit/test_eval_artifacts.py` | Unchanged |
| `tests/test_eval_error_handling.py` | `tests/unit/test_eval_error_handling.py` | Updated for new validation |
| `tests/test_eval_metrics.py` | `tests/unit/test_eval_metrics.py` | Unchanged |
| `tests/test_eval_metrics_utils.py` | `tests/unit/test_eval_metrics_utils.py` | Unchanged |
| `tests/test_eval_pipeline_cli.py` | `tests/unit/test_eval_pipeline_cli.py` | Unchanged |
| `tests/test_eval_retrieval_metrics_extended.py` | `tests/unit/test_eval_retrieval_metrics_extended.py` | Unchanged |
| `tests/test_evaluation_routes.py` | `tests/unit/test_evaluation_routes.py` | Unchanged |
| `tests/test_experiment_config.py` | `tests/unit/test_experiment_config.py` | Unchanged |
| `tests/test_experiment_manifest.py` | `tests/unit/test_experiment_manifest.py` | Unchanged |
| `tests/test_feature_ablation_runner.py` | `tests/unit/test_feature_ablation_runner.py` | Unchanged |
| `tests/test_hyde.py` | `tests/unit/test_hyde.py` | Updated error handling |
| `tests/test_ingestion_error_handling.py` | `tests/unit/test_ingestion_error_handling.py` | Unchanged |
| `tests/test_litellm_client.py` | `tests/unit/test_litellm_client.py` | Unchanged |
| `tests/test_medical_chunking.py` | `tests/unit/test_medical_chunking.py` | Unchanged |
| `tests/test_medical_metrics.py` | `tests/unit/test_medical_metrics.py` | Unchanged |
| `tests/test_orchestrator_deepeval.py` | `tests/unit/test_orchestrator_deepeval.py` | Added `@pytest.mark.slow` |
| `tests/test_pipeline_assessment_smoke.py` | `tests/unit/test_pipeline_assessment_smoke.py` | Unchanged |
| `tests/test_pipeline_quality_upgrades.py` | `tests/unit/test_pipeline_quality_upgrades.py` | Unchanged |
| `tests/test_production_profile.py` | `tests/unit/test_production_profile.py` | Unchanged |
| `tests/test_reranker.py` | `tests/unit/test_reranker.py` | Unchanged |
| `tests/test_retrieval_reranking_modes.py` | `tests/unit/test_retrieval_reranking_modes.py` | Unchanged |
| `tests/test_runtime_index_initialization.py` | `tests/unit/test_runtime_index_initialization.py` | Unchanged |
| `tests/test_runtime_retrieval_diversity.py` | `tests/unit/test_runtime_retrieval_diversity.py` | Unchanged |
| `tests/test_settings.py` | `tests/unit/test_settings.py` | Unchanged |
| `tests/test_settings_deepeval.py` | `tests/unit/test_settings_deepeval.py` | Unchanged |
| `tests/test_storage_history.py` | `tests/unit/test_storage_history.py` | Unchanged |
| `tests/test_synthetic_generator.py` | `tests/unit/test_synthetic_generator.py` | Unchanged |
| `tests/test_thresholds.py` | `tests/unit/test_thresholds.py` | Unchanged |
| `tests/test_thresholds_deepeval.py` | `tests/unit/test_thresholds_deepeval.py` | Unchanged |
| `tests/test_wandb_history.py` | `tests/unit/test_wandb_history.py` | Unchanged |
| `tests/test_wandb_tracking.py` | `tests/unit/test_wandb_tracking.py` | Unchanged |

### Moved to `tests/integration/`

| Original File | New Location | Notes |
|--------------|--------------|---------|
| `tests/test_answer_eval_deepeval.py` | `tests/integration/test_answer_eval_deepeval.py` | Real API tests |
| `tests/test_app_security.py` | `tests/integration/test_app_security.py` | Full app integration |
| `tests/test_chat_multi_turn.py` | `tests/integration/test_chat_multi_turn.py` | Multi-turn conversations |
| `tests/test_chat_sources.py` | `tests/integration/test_chat_sources.py` | Source verification |
| `tests/test_chroma_migration.py` | `tests/integration/test_chroma_migration.py` | Database migration |
| `tests/test_chroma_search.py` | `tests/integration/test_chroma_search.py` | Vector store search |
| `tests/test_chroma_store.py` | `tests/integration/test_chroma_store.py` | Vector store operations |
| `tests/test_concurrent_access.py` | `tests/integration/test_concurrent_access.py` | Concurrency testing |
| `tests/test_embedding.py` | `tests/integration/test_embedding.py` | Real embedding calls |
| `tests/test_eval_api_deepeval.py` | `tests/integration/test_eval_api_deepeval.py` | API integration |
| `tests/test_eval_deepeval.py` | `tests/integration/test_eval_deepeval.py` | Evaluation integration |
| `tests/test_eval_multi_turn.py` | `tests/integration/test_eval_multi_turn.py` | Multi-turn evaluation |
| `tests/test_keyword_index.py` | `tests/integration/test_keyword_index.py` | Index operations |
| `tests/test_pdf_loader.py` | `tests/integration/test_pdf_loader.py` | Real PDF loading |
| `tests/test_retrieval.py` | `tests/integration/test_retrieval.py` | Full retrieval pipeline |
| `tests/test_source_metadata_pipeline.py` | `tests/integration/test_source_metadata_pipeline.py` | Metadata handling |

### Moved to `tests/e2e/`

| Original File | New Location | Notes |
|--------------|--------------|---------|
| `tests/test_backend_e2e_real_apis.py` | `tests/e2e/test_backend_e2e_real_apis.py` | Full e2e with real APIs |

## New Test Files

The following test files were newly created:

### `tests/unit/test_search.py`
**Purpose:** Test search and ranking functions  
**Coverage:** `src/ingestion/indexing/search.py`  
**Tests:**
- Cosine similarity calculations
- Source prior weighting
- Document ranking (keyword-only, semantic, hybrid)
- Input validation for mismatched document counts
- Metadata padding with None
- Reciprocal rank fusion

## Test Marker Improvements

The following test files now include `@pytest.mark.slow` for better test categorization:

- `tests/unit/test_answer_eval_deepeval_async.py`
- `tests/unit/test_deepeval_models.py`
- `tests/unit/test_orchestrator_deepeval.py`
- `tests/unit/test_dataset_builder.py`

## Configuration Changes

### `pyproject.toml`
Added pytest configuration following pytest-tagging best practices:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = ["--strict-markers", "-ra", "--durations=10", "--import-mode=importlib"]
markers = [
    "unit: fast isolated tests (no I/O, no external deps)",
    "integration: tests with DB, filesystem, or service stack",
    "e2e: full end-to-end workflow tests",
    "slow: >1s tests",
    # ... other markers
]
```

### `.github/workflows/ci.yml`
Updated CI pipeline to:
1. Run lint separately
2. Execute unit tests in parallel with `-n auto`
3. Run integration tests independently
4. Add frontend tests and build steps
5. Add smoke tests after other jobs complete

## Running Tests by Category

```bash
# Run only unit tests
pytest tests/unit/ -m "not slow"

# Run only integration tests
pytest tests/integration/

# Run only e2e tests
pytest tests/e2e/

# Run fast unit tests in parallel
pytest tests/unit/ -m "not slow" -n auto

# Run slow tests explicitly
pytest -m slow

# Run smoke tests
pytest -m smoke
```

## Migration Checklist

- ✅ All tests moved to appropriate directories
- ✅ Test markers registered in pyproject.toml
- ✅ Auto-marking by directory implemented
- ✅ CI pipeline updated for new structure
- ✅ New tests added for search validation
- ✅ Slow tests marked with `@pytest.mark.slow`
- ✅ Migration documentation created
- ✅ Conftest files organized by scope
- ✅ Frontend tests added to CI
- ✅ Parallel execution enabled in CI

## Remaining Work

- Consider adding `pytest-xdist` to integration tests (with care for shared resources)
- Add test coverage reporting (`--cov=src`)
- Update CI to run smoke tests on every PR, not just after other jobs
- Monitor test execution times and adjust slow markers as needed

---

**Last Updated:** 2026-04-20