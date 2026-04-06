# Step Evaluation Implementation

## Overview

The pipeline quality assessment framework evaluates ingestion pipeline steps L0-L6 and produces structured metrics stored as versioned artifacts.

## Pipeline Steps (L0-L6)

| Step | Name | Description |
|------|------|-------------|
| L0 | Download | HTML files downloaded from web sources |
| L1 | HTML→Markdown | Convert HTML to Markdown |
| L2 | PDF Extraction | Extract text from PDF documents |
| L3 | Chunking | Split documents into chunks for embedding |
| L4 | Reference Data | Load CSV reference ranges |
| L5 | Indexing | Create vector embeddings and store in index |
| L6 | Retrieval | RAG retrieval quality evaluation |

## Evaluation Files

Each evaluation run produces artifacts in `data/evals/<timestamp>/`:

| File | Description |
|------|-------------|
| `manifest.json` | Run configuration, git commit, timestamps |
| `step_metrics.json` | Aggregate metrics for each stage (L0-L5) |
| `step_findings.json` | Warnings and errors by stage |
| `html_metrics.jsonl` | Per-HTML file metrics |
| `pdf_metrics.jsonl` | Per-PDF file metrics |
| `chunk_metrics.jsonl` | Per-chunk metrics |
| `reference_metrics.json` | CSV validation results |
| `index_metrics.json` | Vector index integrity |
| `retrieval_dataset.json` | Test dataset used |
| `retrieval_results.jsonl` | Per-query retrieval results |
| `retrieval_metrics.json` | Aggregate retrieval metrics |
| `summary.json` | High-level summary |
| `summary.md` | Human-readable report |

## Running Evaluations

```bash
# Full evaluation with all checks
uv run python -m src.cli.eval_pipeline

# Quick evaluation (no LLM generation)
uv run python -m src.cli.eval_pipeline --disable-llm-generation --disable-llm-judging

# With custom thresholds
uv run python -m src.cli.eval_pipeline --thresholds-file custom_thresholds.json
```

## Key Metrics

### Retrieval Metrics (L6)
- **hit_rate_at_k**: Fraction of queries with at least one relevant doc in top-k
- **mrr** (Mean Reciprocal Rank): Average of 1/rank of first relevant doc
- **ndcg_at_k**: Normalized Discounted Cumulative Gain
- **source_hit_rate**: Fraction where expected source appears in top-k
- **exact_chunk_hit_rate**: Fraction where exact expected chunk is retrieved
- **evidence_hit_rate**: Fraction where evidence phrase is found
- **latency_p50_ms / p95_ms**: Retrieval latency percentiles

### Answer Quality Metrics (L6)

L6 stage also evaluates the quality of generated answers using DeepEval's LLM-as-a-judge framework.

Six metrics are evaluated:

1. **Factual Accuracy** (heavyweight model): Groundedness in retrieved context
2. **Completeness** (heavyweight model): Coverage of question aspects
3. **Clinical Relevance** (heavyweight model): Medical appropriateness
4. **Clarity** (lightweight model): Readability and structure
5. **Answer Relevancy** (lightweight model): Directly addresses question
6. **Faithfulness** (heavyweight model): No hallucinations

#### Output Files

- `l6_answer_quality.jsonl`: Per-query detailed results with scores and reasoning
- `l6_answer_quality_metrics.json`: Aggregate answer-quality metrics
- `summary.json`: Aggregate answer-quality metrics in `l6_answer_quality_metrics`

#### Example

```json
{
  "l6": {
    "factual_accuracy": {"mean": 0.85, "count": 100},
    "completeness": {"mean": 0.78, "count": 100},
    "clinical_relevance": {"mean": 0.82, "count": 100},
    "clarity": {"mean": 0.88, "count": 100},
    "answer_relevancy": {"mean": 0.90, "count": 100},
    "faithfulness": {"mean": 0.83, "count": 100}
  }
}
```

### Step Metrics
- **duplicate_chunk_rate**: Duplicate content in chunks (target: <5%)
- **empty_page_rate**: PDF pages with no extracted text (target: <20%)
- **markdown_empty_rate**: Empty/too-small markdown files (target: <10%)
- **embedding_dim_consistent**: All vectors same dimension

## Thresholds

Default thresholds in `src/evals/pipeline_assessment.py`:

```python
DEFAULT_THRESHOLDS = {
    "l1.markdown_empty_rate": {"op": "max", "value": 0.10},
    "l2.empty_page_rate": {"op": "max", "value": 0.20},
    "l3.duplicate_chunk_rate": {"op": "max", "value": 0.05},
    "l5.embedding_dim_consistent": {"op": "min", "value": 1.0},
    "l6.hit_rate_at_k_high_conf": {"op": "min", "value": 0.70},
    "l6.mrr_high_conf": {"op": "min", "value": 0.40},
    "l6.exact_chunk_hit_rate": {"op": "min", "value": 0.40},
    "l6.evidence_hit_rate": {"op": "min", "value": 0.50},
    "l6.duplicate_source_ratio_mean": {"op": "max", "value": 0.60},
}
```

## Frontend Integration

The evaluation dashboard is available at `/eval` and displays:
- Latest evaluation run summary
- Step-by-step quality status (L0-L5)
- Retrieval metrics with threshold indicators
- Pass/fail status for key thresholds

API endpoints:
- `GET /api/evaluation/latest` - Latest evaluation summary
- `GET /api/evaluation/runs` - List all evaluation runs
