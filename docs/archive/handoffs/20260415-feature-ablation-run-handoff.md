# Feature Ablation Run Handoff

## Goal

Run the newly implemented feature ablation workflow end-to-end and verify that it produces:

- populated keyword/summaries ablation results
- populated HyPE ablation results
- populated reranking ablation results
- winner-only answer-eval reruns
- a final human-readable comparison summary

## What Is Already Implemented

The code changes are already in place for:

- index-time HyPE rebuilds during ablations
- index-time keyword/summaries rebuilds during ablations
- reranking ablations against the reference pipeline
- winner selection by `ndcg_at_k`, then `exact_chunk_hit_rate`, then `evidence_hit_rate`, then latency
- summary generation across all three families

Primary entrypoint:

```bash
uv run python scripts/run_feature_ablations.py
```

Wrapper script:

```bash
./scripts/run_missing_ablations.sh
```

## Important Environment Note

Local verification of tests had to use:

```bash
./.venv/bin/pytest ...
```

instead of `uv run pytest ...` because this environment currently hits a `grpcio` build issue involving missing `pkg_resources`.

That issue may also affect `uv run` for the ablation command itself. If it does, try:

```bash
./.venv/bin/python scripts/run_feature_ablations.py
```

before changing any code.

## Reference Configuration

- Config: `experiments/v1/comprehensive_ablation.yaml`
- Reference variant: `pymupdf_semantic_hybrid`
- Dataset: regression split from the existing experiment config

## Expected Output Locations

- `data/evals_keyword_ablation/`
- `data/evals_hype_ablation/`
- `data/evals_reranking_ablation/`
- `data/evals_feature_ablation_summary/feature_ablation_summary.md`
- `data/evals_feature_ablation_summary/feature_ablation_summary.json`

## Execution Steps

### 1. Run the full retrieval-only + winner-answer-eval workflow

Preferred command:

```bash
uv run python scripts/run_feature_ablations.py
```

Fallback if `uv run` fails in this environment:

```bash
./.venv/bin/python scripts/run_feature_ablations.py
```

### 2. If runtime or API cost is a concern, use the retrieval-only dry pass first

```bash
uv run python scripts/run_feature_ablations.py --skip-winner-answer-eval
```

Fallback:

```bash
./.venv/bin/python scripts/run_feature_ablations.py --skip-winner-answer-eval
```

If this succeeds, rerun without `--skip-winner-answer-eval`.

### 3. Inspect the generated run directories

Find the latest runs under each artifact root and inspect:

- `manifest.json`
- `summary.json`
- `keyword_ablations.json` or `hype_ablations.json` or `reranking_ablations.json`

## Verification Checklist

### Keyword / Summaries

Confirm the latest run under `data/evals_keyword_ablation/` has:

- `manifest.json` with `"run_keyword_ablations": true`
- non-empty `keyword_ablations.json`
- variant keys:
  - `baseline`
  - `keywords_only`
  - `summaries_only`
  - `both`
- per-variant metrics present, especially:
  - `ndcg_at_k`
  - `mrr`
  - `exact_chunk_hit_rate`
  - `evidence_hit_rate`
- distinct `collection_name` values across variants

### HyPE

Confirm the latest run under `data/evals_hype_ablation/` has:

- `manifest.json` with `"run_hype_ablations": true`
- non-empty `hype_ablations.json`
- variant keys:
  - `hype_disabled`
  - `hype_10pct`
  - `hype_50pct`
  - `hype_100pct`
  - `hyde_only`
  - `hype_plus_hyde`
- per-variant metrics present
- distinct `collection_name` values across variants

### Reranking

Confirm the latest run under `data/evals_reranking_ablation/` has:

- `manifest.json` with `"run_reranking_ablations": true`
- non-empty `reranking_ablations.json`
- variant keys:
  - `no_reranking`
  - `cross_encoder_only`
  - `mmr_only`
  - `both_reranking`
- per-variant metrics present

### Winner Answer Eval

For each family, confirm there is a separate winner rerun with:

- `l6_answer_quality_metrics.json`
- non-skipped status in answer-eval metrics
- a distinct run name ending in `_answer_eval`

### Final Summary

Confirm both files exist:

- `data/evals_feature_ablation_summary/feature_ablation_summary.md`
- `data/evals_feature_ablation_summary/feature_ablation_summary.json`

Confirm the Markdown summary includes:

- winning variant per family
- deltas versus the family baseline for:
  - `ndcg_at_k`
  - `mrr`
  - `exact_chunk_hit_rate`
  - `evidence_hit_rate`
  - `latency_p50_ms`

## If Something Fails

### If `uv run` fails before execution

- try the `.venv` Python fallback first
- do not change dependency files unless absolutely necessary

### If a family JSON is empty

- check the corresponding `manifest.json` flag first
- check whether the run reused an old run unexpectedly
- rerun with the same command after confirming the latest run was not from a stale artifact directory

### If index-time variants look identical

- inspect per-variant `collection_name`
- inspect `index_preparation`
- inspect `index_metadata` for:
  - `enable_hype`
  - `enable_keyword_extraction`
  - `enable_chunk_summaries`

## Final Deliverable From The Next Agent

Report back with:

1. the latest successful run dir for each family
2. the winner for each family
3. whether winner answer eval completed for each family
4. the path to the final summary Markdown
5. any failures, skips, or environment workarounds used
