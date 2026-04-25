# Phase 2 Follow-Up Handoff

## Current State

This handoff picks up after the first implementation pass of Phase 2 retrieval-quality work.

The following landed:

- Medical-aware structured chunking improvements in `src/ingestion/steps/chunking/core.py` and `src/ingestion/steps/chunking/helpers.py`.
- A provider-backed medical query-expansion seam with a no-op default in `src/rag/medical_expansion.py`, wired through `src/rag/runtime.py`.
- Reranker candidate-window and score-threshold controls in `src/rag/reranker.py` and `src/rag/runtime.py`.
- Expanded retrieval-trace/eval observability in `src/evals/assessment/retrieval_eval.py`.
- New and updated focused tests for chunking, retrieval metrics, reranking, and config defaults.

What is intentionally still incomplete:

- No real ontology-backed provider exists yet; only the `noop` provider is implemented.
- No regression-split benchmark/evaluation artifact has been run yet to prove measurable retrieval improvement.
- No tuning pass has been done yet on rerank thresholds/candidate windows beyond adding the controls and trace fields.
- No docs/configuration write-up has been added for the new retrieval flags.

## Files Touched In This Pass

- `src/ingestion/steps/chunking/core.py`
- `src/ingestion/steps/chunking/helpers.py`
- `src/rag/medical_expansion.py`
- `src/rag/runtime.py`
- `src/rag/reranker.py`
- `src/config/settings.py`
- `src/evals/assessment/retrieval_eval.py`
- `tests/test_medical_chunking.py`
- `tests/test_retrieval_reranking_modes.py`
- `tests/test_eval_retrieval_metrics_extended.py`
- `tests/test_reranker.py`
- `tests/test_configuration.py`

## What Was Implemented

### 1. Medical-aware chunking

- Structured lists are now grouped on whole bullet-item boundaries rather than arbitrary character splits.
- Structured tables are now grouped by rows with header repetition when a table must be split.
- Heading blocks remain non-retrievable and continue to act as hard section boundaries because chunks are emitted per structured block and retain `section_path`.
- Existing chunk metadata shape was preserved; neighbor links and `content_type` continue to be maintained.

### 2. Medical expansion seam

- Added `MedicalExpansion` and a provider contract in `src/rag/medical_expansion.py`.
- Added `NoopMedicalExpansionProvider` as the default provider.
- Query expansion flow in runtime is now:
  1. lexical/base expansion
  2. provider-backed medical expansion
  3. HyDE expansion, when enabled
  4. HyPE extension, when enabled
- Retrieval trace now records:
  - `enable_medical_expansion`
  - `medical_expansion_provider`
  - `medical_expansion_terms`
  - `medical_expansion_term_count`

### 3. Reranker controls and observability

- Added runtime/config support for:
  - `rerank_top_k`
  - `rerank_score_threshold`
  - existing `reranking_mode`
- Cross-encoder reranker now supports filtering out low-scoring results via `min_score`.
- Retrieval trace/eval now records:
  - reranker enabled state
  - rerank timing
  - candidates requested/available/reranked
  - rerank output count
  - rerank filtered-out count
  - returned document count

## Verification Completed

These focused tests passed:

```bash
./.venv/bin/pytest tests/test_medical_chunking.py tests/test_retrieval_reranking_modes.py tests/test_eval_retrieval_metrics_extended.py tests/test_reranker.py tests/test_configuration.py
./.venv/bin/pytest tests/test_pipeline_quality_upgrades.py -k 'test_chunker_preserves_section_and_neighbor_metadata or test_chunker_preserves_ingestion_source_metadata'
./.venv/bin/pytest tests/test_hyde.py -k 'test_should_enable_hyde_config_setting or test_validate_hyde_config_valid or test_validate_hyde_config_clamps_max_length'
```

Important caveat:

- `uv run pytest ...` currently fails before test execution because `grpcio==1.60.1` fails to build under the current Python 3.13 environment with `ModuleNotFoundError: No module named 'pkg_resources'`.
- Because of that blocker, verification was done with the existing `.venv` test runner instead of `uv run`.

## Remaining Tasks For The Next Agent

### 1. Prove Phase 2 retrieval gains on the regression split

Run the existing evaluation pipeline against `dataset_split=regression` and capture baseline vs enabled variants using the new retrieval flags.

Recommended first commands to inspect:

- `src/cli/eval_pipeline.py`
- `scripts/run_variant_clean.py`

Suggested evaluation goals:

- baseline current retrieval
- medical-aware chunking enabled path compared against prior/default ingestion config
- no-op medical expansion vs stub/real provider-backed expansion
- reranker off vs reranker on with tuned `rerank_top_k` and `rerank_score_threshold`

Deliverables:

- one eval run or set of runs showing whether `hit_rate_at_k`, `mrr`, `exact_chunk_hit_rate`, and `evidence_hit_rate` improved on `regression`
- a concise recommendation for default candidate window / threshold settings

### 2. Add a real provider implementation or a stronger test/stub seam

The provider seam exists but is still `noop`-only.

Next step options:

- implement a local synonym/terminology provider using curated medical mappings already in repo, if any are available
- or add a more capable in-repo stub/fake provider for evaluation experiments if the real ontology source is still undecided

Constraints:

- keep the provider feature-flagged and disabled by default
- do not entangle it with HyDE or HyPE toggles
- preserve the normalized output shape (`term`, `source`, optional `relation`)

### 3. Tune reranking and ablation coverage

The retrieval eval now reports reranker metrics, but the ablation space is still shallow.

Recommended follow-up:

- extend `reranking_ablation_configs()` with explicit candidate-window/threshold variants
- compare latency and quality deltas, not just hit-rate deltas
- confirm whether thresholding causes undesirable emptying of candidate sets for some queries

Suggested additions:

- `cross_encoder_topk_small`
- `cross_encoder_topk_large`
- `cross_encoder_threshold_low`
- `cross_encoder_threshold_high`

Keep the outputs additive and comparable with current eval artifacts.

### 4. Close the docs/config loop

The new flags were added to settings, but user/operator-facing docs were not updated yet.

Update whichever docs are the canonical config references in the current repo state, likely including:

- `docs/configuration.md`
- any eval or experiment docs that describe retrieval options

Document:

- `medical_expansion_enabled`
- `medical_expansion_provider`
- `rerank_score_threshold`
- how these relate to existing `enable_reranking`, `rerank_top_k`, `reranking_mode`, `hyde_enabled`, and `hype_enabled`

## Risks / Watchouts

- The repo has an already-dirty worktree outside this Phase 2 slice; do not revert unrelated user changes.
- `src/rag/runtime.py` was already modified before this pass for Phase 1/runtime-state work. Read diffs carefully before large follow-up edits.
- The new sync retrieval path uses `_prepare_expanded_queries()` while async retrieval additionally passes through HyDE. Keep those paths behaviorally aligned.
- The current retrieval-trace shape is intentionally additive; do not break `/chat` consumers or tests that expect existing fields.
- If you change ingestion settings and rebuild the vector store for experiments, preserve the runtime-state reset behavior added in Phase 1.

## Suggested Next Ticket

If picking up immediately, start here:

1. Run a regression-split eval baseline.
2. Run reranking ablations with a few `rerank_top_k` and `rerank_score_threshold` variants.
3. Summarize whether Phase 2 already shows measurable gains or whether a real medical provider is required before the gains are visible.
