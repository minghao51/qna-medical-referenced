# Comprehensive Ablation Study

## Overview

Systematic ablation of each ingestion component to reveal optimal configuration for medical RAG retrieval quality.

**Config**: `experiments/v1/comprehensive_ablation.yaml`  
**Results**: `data/evals_comprehensive_ablation/`  
**Status**: In Progress (8/22 variants completed, running in background)

---

## Experiment Design

### Dimensions

| Dimension | Variants | What Changes |
|-----------|----------|-------------|
| **Baseline** | 1 | Reference configuration |
| **PDF Extraction** | 2 | pypdf vs pymupdf vs pymupdf+camelot |
| **HTML Extraction** | 3 | trafilatura vs html2md vs readability vs full_cascade |
| **Chunking Strategy** | 4 | custom_recursive vs chonkie_recursive vs chonkie_semantic vs chonkie_late |
| **Chunk Size** | 3 | 384 vs 650 vs 1024 tokens |
| **Retrieval** | 4 | rrf_hybrid vs semantic_only vs bm25_only vs MMR tuning |
| **Combined Best** | 4 | Stacked optimal findings |

### Base Configuration

- **Embedding**: `text-embedding-v4` (768-dim)
- **Chunking**: recursive, 650 tokens, 80 overlap
- **PDF Extractor**: `pypdf_pdfplumber` + heuristic tables
- **HTML Extractor**: `trafilatura_bs`
- **Retrieval**: RRF hybrid (semantic 0.6, keyword 0.2, boost 0.2)
- **Diversification**: MMR λ=0.75, overfetch=4
- **Dataset**: 21 golden queries (lipid + diabetes focus, regression split) — see [Golden Query Datasets](#golden-query-datasets) for full suite

---

## Golden Query Datasets

### Available Datasets

| Dataset | File | Queries | Source Families | Topics | Categories | Use Case |
|---------|------|---------|-----------------|--------|------------|----------|
| **Original** | `golden_queries.json` | 21 | 2 (lipid, diabetes) | 6 | anchor, adversarial, paraphrase | Baseline regression testing |
| **Expanded** | `golden_queries_expanded.json` | 54 | 15 | 23 | anchor, adversarial, paraphrase | Comprehensive ablation study |
| **Diverse** | `golden_queries_diverse.json` | 20 | 13 | 13 | anchor | Cross-domain diversity test |
| **Comprehensive** | `golden_queries_comprehensive.json` | 35 | 14 | 22 | anchor | Full corpus coverage |

### Dataset Coverage

**Original (21 queries)**: Focused on lipid management and pre-diabetes. Good for regression testing but limited scope.

**Expanded (54 queries)**: Full coverage across all major clinical domains:
- **Diabetes** (T2 management, complications, insulin, foot care)
- **Cardiovascular** (hypertension, CVD risk, coronary syndrome, VTE)
- **Mental Health** (anxiety, depression)
- **Respiratory** (COPD, asthma)
- **Musculoskeletal** (osteoporosis)
- **Screening & Preventive** (health screening, smoking cessation)
- **Neurology** (stroke rehabilitation)
- **Nutrition** (dietary advice, cholesterol management)

**Diverse (20 queries)**: One query per source family, balanced across difficulty levels. Tests cross-domain retrieval quality.

**Comprehensive (35 queries)**: Broad coverage with emphasis on clinical accuracy. Includes complex multi-step questions.

### Running with Different Datasets

```bash
# Use original dataset (default)
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --all-variants

# Use expanded dataset (recommended for ablation)
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --all-variants \
  --dataset-path tests/fixtures/golden_queries_expanded.json

# Use diverse dataset (quick cross-domain check)
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --all-variants \
  --dataset-path tests/fixtures/golden_queries_diverse.json

# Use comprehensive dataset (full coverage)
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --all-variants \
  --dataset-path tests/fixtures/golden_queries_comprehensive.json
```

---

## Results

### Retrieval Metrics

| Variant | HR@K | MRR | NDCG@K | Prec@K | Recall@K | Exact Hit | Evidence Hit | Latency p50 | Chunks | Dups |
|---------|------|-----|--------|--------|----------|-----------|--------------|-------------|--------|------|
| **baseline** | 1.000 | 1.000 | 0.9768 | 0.7143 | 1.000 | 0.4286 | 0.2857 | 1263ms | 1907 | 340 |
| **pdf_pymupdf** | 1.000 | 1.000 | 0.9951 | 0.6857 | 1.000 | 0.1429 | 0.1429 | 1467ms | 1750 | 402 |
| **pdf_pymupdf_camelot** | 1.000 | 1.000 | 0.9951 | 0.6857 | 1.000 | 0.1429 | 0.1429 | 1264ms | 1750 | 402 |

### L6 Answer Quality

| Variant | Factual Acc | Completeness | Clinical Rel | Clarity | Answer Rel | Faithfulness |
|---------|-------------|--------------|--------------|---------|------------|--------------|
| **baseline** | 0.7429 | 0.9857 | 0.8571 | 0.9571 | 0.9373 | 0.0000 |
| **pdf_pymupdf** | 0.9286 | 0.9833 | 0.9857 | 0.9857 | 0.9002 | 0.0000 |
| **pdf_pymupdf_camelot** | 0.8714 | 0.9857 | 0.9857 | 0.9714 | 0.9524 | 1.0000 |

### Retrieval Strategy Ablations (within each run)

| Strategy | Baseline NDCG | pymupdf NDCG | pymupdf+camelot NDCG |
|----------|---------------|--------------|---------------------|
| **rrf_hybrid** | 0.9801 | 0.9866 | 0.9866 |
| **rrf_hybrid_mmr** | 0.9768 | 0.9951 | 0.9951 |
| **semantic_only** | 0.9841 | 0.9929 | 0.9929 |
| **bm25_only** | 0.8997 | 0.9049 | 0.9049 |

### Ingestion Statistics

| Variant | Chunks Attempted | Inserted | Duplicates | Duration |
|---------|-----------------|----------|------------|----------|
| **baseline** | 1907 | 1567 | 340 | ~7.5 min |
| **pdf_pymupdf** | 1750 | 1348 | 402 | ~7.9 min |
| **pdf_pymupdf_camelot** | 1750 | 1348 | 402 | ~7.1 min |

---

## Key Findings (Preliminary)

### PDF Extraction
- **PyMuPDF improves NDCG** by 1.9% (0.9768 → 0.9951)
- **Factual accuracy jumps 25%** (0.74 → 0.93) with PyMuPDF
- **Camelot tables add faithfulness** (0.0 → 1.0) but slightly reduce factual accuracy
- PyMuPDF extracts less text (1750 vs 1907 chunks) but higher quality

### Retrieval Strategy
- **BM25 consistently weakest** (MRR=0.8571, NDCG~0.90)
- **Semantic-only competitive** with hybrid in this small dataset
- **MMR diversification** helps PyMuPDF variants (NDCG 0.9866 → 0.9951)

### Caveats
- **Only 7 queries** — results may not be statistically significant
- All variants achieve perfect hit rate and MRR — ceiling effect
- Exact chunk hit and evidence hit rates are low across all variants

---

## Pending Variants

| Group | Variant | Status |
|-------|---------|--------|
| HTML | `html_html2md` | Pending |
| HTML | `html_readability` | Pending |
| HTML | `html_fullcascade` | Pending |
| Chunking | `chunk_custom_recursive_512` | Pending |
| Chunking | `chunk_chonkie_recursive_512` | Pending |
| Chunking | `chunk_chonkie_semantic_512` | Pending |
| Chunking | `chunk_chonkie_late_512` | Pending |
| Size | `chunksize_384` | Pending |
| Size | `chunksize_650` | Pending |
| Size | `chunksize_1024` | Pending |
| Retrieval | `retrieval_semantic_only` | Pending |
| Retrieval | `retrieval_bm25_only` | Pending |
| Retrieval | `retrieval_mmr_tuned` | Pending |
| Retrieval | `retrieval_no_diversification` | Pending |
| Combined | `combined_best_extraction` | Pending |
| Combined | `combined_best_extraction_chunking` | Pending |
| Combined | `combined_all_best` | Pending |
| Combined | `combined_small_chunks_best_extraction` | Pending |

---

## Performance Optimizations Applied

### 1. Increased Embedding Batch Size ✅

**Change**: `embedding_batch_size: 10` → `50` in `comprehensive_ablation.yaml`

**Impact**: ~5× fewer API round trips for embedding stage (4-5 min → ~1 min estimated)

### 2. Index Reuse Logic ✅ (Already Existed)

**Mechanism**: `index_config_hash` comparison in `orchestrator.py:284-286`

**How it works**:
- Each variant computes a hash of its ingestion + embedding config
- If hash matches existing vector file, skips rebuild
- Variants with same ingestion config share index automatically

**Impact**: Retrieval-only variants skip 4-5 min index rebuild

### 3. ProcessPoolExecutor Parallelism ✅

**Added**: `--parallel` and `--max-workers` flags to `eval_pipeline.py`

**Implementation**:
```python
# Run variants in separate processes (isolates global state)
with ProcessPoolExecutor(max_workers=max_workers) as executor:
    futures = {executor.submit(_run_single_variant, kwargs): i 
               for i, spec in enumerate(specs)}
```

**Why processes, not threads**:
- Each process gets its own memory space → no global singleton conflicts
- ChromaDB PersistentClient created fresh per process
- Dashscope API clients are process-isolated

**Caveat**: Memory limits on local machine may restrict parallelism. Background execution recommended.

### 4. File Locking for Artifacts ✅

**Added**: `fcntl.flock` in `artifacts.py` for `latest_run.txt` and `run_index.json`

**Impact**: Prevents corruption when multiple variants write artifacts simultaneously

### Estimated Speedup

| Scenario | Before | After (batch=50) | After (parallel ×4) |
|----------|--------|------------------|---------------------|
| Index rebuild | ~5 min | ~1 min | ~1 min (shared) |
| Retrieval eval | ~1 min | ~1 min | ~0.25 min |
| L6 answer eval | ~1-2 min | ~1-2 min | ~0.5 min |
| **Per variant** | **~7-8 min** | **~3-4 min** | **~1-2 min** |
| **22 variants** | **~2.5-3 hrs** | **~1-1.5 hrs** | **~15-30 min** |

---

## Running the Study

```bash
# Run all variants (sequential, with batch optimization)
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --all-variants \
  --include-answer-eval

# Run all variants in parallel (4 workers)
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --all-variants \
  --parallel \
  --max-workers 4 \
  --include-answer-eval

# Run a single variant
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --variant pdf_pymupdf \
  --include-answer-eval

# Skip LLM evaluation (faster, retrieval metrics only)
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --all-variants
```

---

## Bug Fixes Applied

### ChromaDB Metadata Serialization

**Issue**: `source_chunk_configs` (nested dict) passed to `collection.modify(metadata=...)` which only accepts primitive types.

**Fix**: Serialize to JSON string in `src/rag/runtime.py:373`:
```python
"source_chunk_configs": json.dumps(get_source_chunk_configs()),
```

**Fix**: Deserialize when reading back in `src/evals/assessment/orchestrator.py:505`:
```python
"source_chunk_configs": (
    (lambda v: json.loads(v) if isinstance(v, str) else v)(
        index_metadata.get("source_chunk_configs")
    )
),
```

---

*Last updated: 2026-04-02*
