# W&B Tracking Best Practices

**Date**: 2025-03-13
**Purpose**: Guide for organizing metrics in Weights & Biases for optimal dashboard usability

## Overview

This document covers best practices for W&B tracking implementation, focusing on metric organization, UI configuration, and common pitfalls. Following these practices ensures clean, navigable dashboards that scale with your experimentation.

## Core Principles

1. **Hierarchical Organization**: Use `/` separator for metric namespacing
2. **Metric Prioritization**: Distinguish between primary, secondary, and debug metrics
3. **UI Configuration**: Use `define_metric()` to control chart behavior
4. **Config vs Metrics**: Store hyperparameters in config, evaluation results in metrics

## Metric Namespacing

### Use `/` Separator

W&B's UI recognizes `/` as a hierarchy delimiter, creating grouped charts automatically.

```python
# GOOD - Creates grouped charts
metrics = {
    "retrieval/hit_rate": 0.9,
    "retrieval/mrr": 0.8,
    "retrieval/latency_p50_ms": 150,
}

# BAD - Flat structure, no grouping
metrics = {
    "retrieval.hit_rate": 0.9,
    "retrieval.mrr": 0.8,
    "retrieval.latency_p50_ms": 150,
}
```

### Recommended Hierarchy

```
retrieval/
├── hit_rate          # Primary metrics
├── mrr
├── ndcg
├── latency_p50_ms
├── by_difficulty/    # Breakdowns
│   ├── easy/hit_rate
│   └── hard/hit_rate
└── by_task_type/     # Secondary metrics
    ├── clinical/hit_rate
    └── procedural/hit_rate

rag/
├── faithfulness_mean
├── relevance_mean
└── groundedness_mean

steps/
├── chunking/quality_histogram/high
├── retrieval/page_distribution
└── synthesis/dedupe_effect_estimate

summary/
├── duration_s
└── failed_thresholds
```

## Tiered Metrics Approach

Organize metrics by importance to reduce dashboard clutter:

### Primary Metrics

**Purpose**: Key indicators for experiment comparison
**Count**: ~5-10 metrics
**UI**: Prominent display, summary statistics enabled

```python
def _extract_primary_metrics(retrieval, rag, summary):
    metrics = {}

    # Retrieval quality
    metrics["retrieval/hit_rate"] = retrieval["hit_rate_at_k"]
    metrics["retrieval/mrr"] = retrieval["mrr"]
    metrics["retrieval/ndcg"] = retrieval["ndcg_at_k"]

    # Latency
    metrics["retrieval/latency_p50_ms"] = retrieval["latency_p50_ms"]

    # RAG quality
    if rag.get("status") != "skipped":
        metrics["rag/faithfulness_mean"] = rag["faithfulness_score_mean"]
        metrics["rag/relevance_mean"] = rag["relevance_score_mean"]

    # Pipeline health
    metrics["summary/duration_s"] = summary["duration_s"]
    metrics["summary/failed_thresholds"] = summary["failed_thresholds_count"]

    return metrics
```

### Secondary Metrics

**Purpose**: Detailed analysis without cluttering main view
**Count**: ~50-100 metrics
**UI**: Visible in charts, but not prominent

```python
def _extract_secondary_metrics(retrieval):
    metrics = {}

    # Additional retrieval metrics
    for key in ["precision_at_k", "recall_at_k", "source_hit_rate"]:
        if key in retrieval:
            metrics[f"retrieval/{key}"] = retrieval[key]

    # Breakdowns (aggregated values only)
    by_difficulty = retrieval.get("by_difficulty", {})
    for difficulty, metrics_dict in by_difficulty.items():
        if "hit_rate_at_k" in metrics_dict:
            metrics[f"retrieval/by_difficulty/{difficulty}/hit_rate"] = \
                metrics_dict["hit_rate_at_k"]

    return metrics
```

### Debug Metrics

**Purpose**: Internal diagnostics, hidden from charts
**Count**: ~500-1000 metrics
**UI**: Hidden from auto-generated charts, accessible in run history

```python
def _extract_debug_metrics(retrieval, step_metrics):
    metrics = {}

    # Query counts and detailed stats
    for breakdown_type in ["by_difficulty", "by_task_type"]:
        breakdown = retrieval.get(breakdown_type, {})
        for category, metrics_dict in breakdown.items():
            for metric_name, value in metrics_dict.items():
                if metric_name != "hit_rate_at_k":  # Already in secondary
                    if isinstance(value, (int, float, bool)):
                        metrics[f"retrieval/{breakdown_type}/{category}/{metric_name}"] = value

    return metrics
```

## Using `define_metric()`

Configure metric behavior for better UI organization:

### Summary Statistics

Mark metrics that should show summary statistics (min, max, mean) in project view:

```python
run.define_metric("retrieval/hit_rate", summary="max")
run.define_metric("retrieval/mrr", summary="max")
run.define_metric("retrieval/latency_p50_ms", summary="min")
```

### Hide Debug Metrics

Prevent clutter by hiding metrics from auto-generated charts:

```python
# Hide query counts
run.define_metric("retrieval/by_difficulty/*/query_count", hidden=True)

# Hide detailed breakdowns
run.define_metric("retrieval/by_task_type/*", hidden=True)
run.define_metric("retrieval/by_expected_source_type/*", hidden=True)

# Hide step-level diagnostics
run.define_metric("steps/*/_*", hidden=True)
run.define_metric("steps/*/source_distribution", hidden=True)
```

**Note**: Hidden metrics are still stored and accessible in run history, just not in charts.

## Config vs Metrics

### Config (Hyperparameters)

Store experimental configuration in `config` parameter of `wandb.init()`:

```python
run = wandb.init(
    project="my-project",
    config={
        "experiment": {
            "variant_name": "baseline",
            "metadata": {"name": "baseline"},
        },
        "manifest": {
            "chunking_strategy": "fixed_size",
            "chunk_size": 512,
            "chunk_overlap": 50,
        },
    }
)
```

**What goes in config:**
- Experiment metadata
- Hyperparameters (chunk size, overlap, model settings)
- Pipeline configuration
- Dataset versions

### Metrics (Evaluation Results)

Log evaluation results via `run.log()`:

```python
run.log({
    "retrieval/hit_rate": 0.9,
    "retrieval/mrr": 0.8,
    "summary/duration_s": 150,
})
```

**What goes in metrics:**
- Evaluation scores (hit rate, MRR, NDCG)
- Latency measurements
- Quality assessments
- Threshold results
- Breakdown analyses

## Handling Nested Structures

### Histograms

Flatten histograms into separate metrics:

```python
# GOOD - Flat structure
chunk_quality_histogram = {
    "high": 450,
    "medium": 300,
    "low": 50,
}
for quality_level, count in chunk_quality_histogram.items():
    metrics[f"steps/chunking/quality_histogram/{quality_level}"] = count

# BAD - Nested dict (not logged)
metrics["steps/chunking/quality_histogram"] = chunk_quality_histogram
```

### Distributions

For distribution data, log summary statistics instead of raw values:

```python
# GOOD - Summary statistics
metrics["steps/retrieval/latency_p50_ms"] = np.percentile(latencies, 50)
metrics["steps/retrieval/latency_p95_ms"] = np.percentile(latencies, 95)
metrics["steps/retrieval/latency_mean_ms"] = np.mean(latencies)

# AVOID - Raw lists (clutters dashboard)
metrics["steps/retrieval/all_latencies"] = latencies  # Don't do this
```

## Artifact Usage Patterns

### Logging Artifacts

Store outputs and intermediate results as artifacts:

```python
artifact = wandb.Artifact(
    name=f"{run_path.name}-artifacts",
    type="evaluation-run",
    metadata={
        "run_dir": run_path.name,
        "status": summary.get("status"),
        "failed_thresholds_count": len(failed_thresholds),
    },
)
artifact.add_dir(str(run_path))
run.log_artifact(artifact)
```

### Best Practices

1. **Use descriptive types**: `evaluation-run`, `dataset`, `model`
2. **Include metadata**: Store summary stats in artifact metadata
3. **Version control**: W&B automatically versions artifacts
4. **Reference by alias**: Use `latest`, `best` for easy retrieval

## Common Pitfalls

### 1. Too Many Metrics

**Problem**: Logging 700+ metrics makes dashboard unusable
**Solution**: Use tiered approach, hide debug metrics

### 2. Flat Naming

**Problem**: Using `.` separator doesn't group metrics in UI
**Solution**: Use `/` separator for hierarchical organization

### 3. Nested Dicts in Metrics

**Problem**: Logging nested dicts creates weird chart structures
**Solution**: Flatten to `parent/child/key` format

### 4. Config in Metrics

**Problem**: Logging hyperparameters as metrics clutters comparison
**Solution**: Use `config` parameter for hyperparameters

### 5. Not Using define_metric

**Problem**: All metrics shown equally, hard to find key indicators
**Solution**: Mark primary metrics with `summary`, hide debug metrics

### 6. Query Counts as Primary Metrics

**Problem**: Query counts vary by dataset size, not comparable
**Solution**: Put query counts in debug/hidden metrics

## Migration Guide: `.` to `/` Naming

Migrating from `.` separator to `/` separator requires updating:

### 1. Update Flattening Function

```python
# OLD
def _flatten_numeric(prefix: str, value: Any, output: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten_numeric(child_prefix, child, output)
        return
    # ...

# NEW
def _flatten_for_wandb(prefix: str, value: Any, output: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}/{key}" if prefix else str(key)
            _flatten_for_wandb(child_prefix, child, output)
        return
    # ...
```

### 2. Update Tests

Update test assertions to use `/` separator:

```python
# OLD
assert metrics["retrieval.hit_rate_at_k"] == 0.9

# NEW
assert metrics["retrieval/hit_rate"] == 0.9  # Note: _at_k suffix removed
```

### 3. Update Dashboard Queries

If you have saved dashboard queries, update metric names:

- `retrieval.hit_rate` → `retrieval/hit_rate`
- `summary.duration_s` → `summary/duration_s`
- `steps.chunking.aggregate.markdown_empty_rate` → `steps/chunking/markdown_empty_rate`

### 4. Backward Compatibility

Old runs remain accessible. New runs use optimized format. No breaking changes to API.

## Code Example: Complete Implementation

```python
import logging
from typing import Any

logger = logging.getLogger(__name__)

def log_assessment_to_wandb(*, experiment, summary, manifest, step_metrics,
                            retrieval_metrics, rag_metrics, run_dir, failed_thresholds):
    tracking_cfg = experiment.get("tracking", {}).get("wandb", {})
    if not tracking_cfg.get("enabled"):
        return {"enabled": False, "status": "disabled"}

    run = wandb.init(
        project=tracking_cfg.get("project"),
        config={
            "experiment": experiment,
            "manifest": manifest,
        },
    )

    # Configure UI
    _define_wandb_metrics(run)

    # Extract metrics in tiers
    metrics = {}
    metrics.update(_extract_primary_metrics(retrieval_metrics, rag_metrics, summary))
    metrics.update(_extract_secondary_metrics(retrieval_metrics))
    metrics.update(_extract_debug_metrics(retrieval_metrics, step_metrics))

    run.log(metrics)
    run.finish()

    return {"status": "logged", "run_id": run.id}


def _define_wandb_metrics(run):
    """Configure metric behavior for UI."""
    # Primary metrics with summary stats
    run.define_metric("retrieval/hit_rate", summary="max")
    run.define_metric("retrieval/mrr", summary="max")
    run.define_metric("rag/faithfulness_mean", summary="max")

    # Hide debug metrics
    run.define_metric("retrieval/by_difficulty/*/query_count", hidden=True)
    run.define_metric("steps/*/_*", hidden=True)


def _extract_primary_metrics(retrieval, rag, summary):
    """Extract key metrics for experiment comparison."""
    metrics = {}
    metrics["retrieval/hit_rate"] = retrieval["hit_rate_at_k"]
    metrics["retrieval/mrr"] = retrieval["mrr"]
    metrics["summary/duration_s"] = summary["duration_s"]
    return metrics


def _extract_secondary_metrics(retrieval):
    """Extract detailed analysis metrics."""
    metrics = {}
    by_difficulty = retrieval.get("by_difficulty", {})
    for difficulty, metrics_dict in by_difficulty.items():
        if "hit_rate_at_k" in metrics_dict:
            metrics[f"retrieval/by_difficulty/{difficulty}/hit_rate"] = \
                metrics_dict["hit_rate_at_k"]
    return metrics


def _extract_debug_metrics(retrieval, step_metrics):
    """Extract debug metrics (hidden from charts)."""
    metrics = {}
    for step_name, step_data in step_metrics.items():
        aggregate = step_data.get("aggregate", {})
        for metric_name, value in aggregate.items():
            if isinstance(value, (int, float, bool)) and not isinstance(value, dict):
                metrics[f"steps/{step_name}/{metric_name}"] = value
    return metrics
```

## Verification Checklist

After implementing W&B tracking:

- [ ] Primary metrics appear prominently in project view
- [ ] Debug metrics are hidden from auto-generated charts
- [ ] `/` namespacing creates proper metric groups
- [ ] Config contains hyperparameters only
- [ ] Metrics contain evaluation results only
- [ ] Histograms are flattened into separate metrics
- [ ] Summary statistics enabled for key metrics
- [ ] Tests pass with new metric names
- [ ] Dashboard is navigable with <100 visible metrics

## Further Reading

- [W&B Documentation: Define Metrics](https://docs.wandb.ai/guides/track/advanced/define-metrics)
- [W&B Documentation: Artifacts](https://docs.wandb.ai/guides/artifacts)
- [W&B Best Practices: Guide](https://docs.wandb.ai/guides/track/log)
