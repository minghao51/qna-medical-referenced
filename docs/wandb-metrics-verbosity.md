# Wandb Metrics Verbosity Levels

This document describes the three verbosity levels for wandb metrics logging.

## Configuration

Set the verbosity level in your experiment config:

```yaml
tracking:
  wandb:
    enabled: true
    metrics_verbosity: standard  # Options: critical, standard, debug
```

## Verbosity Levels

### `critical` - Minimal Metrics (~10 metrics)

Best for: High-level run comparison and spotting key differences

**Metrics logged:**
- `retrieval/hit_rate` - Overall retrieval success rate
- `retrieval/mrr` - Mean Reciprocal Rank
- `retrieval/ndcg` - Normalized Discounted Cumulative Gain
- `retrieval/latency_p50_ms` - Median query latency
- `summary/duration_s` - Total pipeline duration
- `summary/failed_thresholds` - Number of failed thresholds

**Use case:** Quick comparison between runs without clutter

---

### `standard` - Recommended (~50 metrics)

Best for: Day-to-day experimentation and analysis

**Includes all `critical` metrics plus:**
- Secondary retrieval metrics:
  - `retrieval/precision_at_k`
  - `retrieval/recall_at_k`
  - `retrieval/source_hit_rate`
  - `retrieval/exact_chunk_hit_rate`
  - `retrieval/evidence_hit_rate`
  - `retrieval/latency_p95_ms`

- Difficulty breakdowns:
  - `retrieval/by_difficulty/easy/hit_rate`
  - `retrieval/by_difficulty/medium/hit_rate`
  - `retrieval/by_difficulty/hard/hit_rate`

- Category breakdowns:
  - `retrieval/by_category/anchor/hit_rate`
  - `retrieval/by_category/adversarial/hit_rate`
  - `retrieval/by_category/paraphrase/hit_rate`

- L6 answer quality (if enabled):
  - `l6_answer_quality/factual_accuracy_mean`
  - `l6_answer_quality/completeness_mean`
  - `l6_answer_quality/clinical_relevance_mean`
  - And more...

**Use case:** Standard experimentation - enough detail for analysis without overwhelming noise

---

### `debug` - Verbose Logging (1000+ metrics)

Best for: Deep debugging and detailed analysis

**Includes all `standard` metrics plus:**
- All nested breakdowns (by_task_type, by_expected_source_type, by_semantic_case)
- Contribution analysis (semantic vs BM25 vs fused contributions)
- Step metrics (L0-L5 pipeline steps with detailed stats)
- Quality histograms
- Deduplication effects
- Page classification distributions

**Use case:** Debugging pipeline issues, analyzing retrieval contributions, or investigating specific query patterns

## Example: Comparing Runs

### Using `critical` mode:
You'll see a clean table like:
```
Run                    | hit_rate | mrr  | ndcg   | latency_p50
-----------------------|----------|------|--------|-------------
baseline               | 1.0      | 1.0  | 0.982  | 663
chunk_small            | 1.0      | 0.93 | 0.952  | 558
rrf_mmr_tuned          | 1.0      | 1.0  | 0.979  | 1078
```

### Using `standard` mode:
You'll see additional breakdowns:
```
Run                    | hit_rate | exact_chunk | evidence_hit | latency_p50 | by_difficulty/easy/hit_rate
-----------------------|----------|-------------|--------------|-------------|------------------------------
baseline               | 1.0      | 0.57        | 0.43         | 663         | 1.0
chunk_small            | 1.0      | 0.71        | 0.57         | 558         | 1.0
rrf_mmr_tuned          | 1.0      | 0.43        | 0.43         | 1078        | 1.0
```

## Recommendation

**Start with `standard`** - it provides the right balance of detail without overwhelming clutter. Switch to `critical` when you need to quickly compare many runs, or `debug` when investigating specific issues.

## Migration

To update existing experiment configs, simply add:

```yaml
tracking:
  wandb:
    enabled: true
    metrics_verbosity: standard  # Add this line
```

If `metrics_verbosity` is not specified, it defaults to `standard`.
