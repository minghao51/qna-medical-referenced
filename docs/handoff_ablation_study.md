# Handoff: Run Full Ablation Study & Present Findings

## Context

This handoff is for continuing the comprehensive ablation study on the medical RAG ingestion pipeline. The study evaluates how different ingestion configurations affect retrieval quality across multiple clinical domains.

## Current State

### Completed Work
- ✅ Created 4 golden query datasets (original 21, expanded 54, diverse 20, comprehensive 35 queries)
- ✅ Created `experiments/v1/comprehensive_ablation.yaml` with 22 variants across 6 dimensions
- ✅ Fixed ChromaDB metadata serialization bug (`source_chunk_configs` nested dict)
- ✅ Added file locking for parallel artifact writes (`artifacts.py`)
- ✅ Added `--parallel` and `--max-workers` flags to `eval_pipeline.py`
- ✅ Increased embedding batch size from 10 → 50
- ✅ Ran 8/22 variants (baseline, pdf_pymupdf, pdf_pymupdf_camelot × 2 runs each)
- ✅ Documented preliminary findings in `docs/ablation_study.md`

### Pending Work
- ❌ Run remaining 14 variants with expanded dataset
- ❌ Run variants with all 4 golden datasets for comparison
- ❌ Compile comprehensive findings
- ❌ Create presentation/summary for stakeholders

## Key Files

### Experiment Configs
- `experiments/v1/comprehensive_ablation.yaml` - Main ablation config (22 variants)
- `experiments/v1/baseline.yaml` - Original baseline
- `experiments/v1/chunking_strategies.yaml` - Chunking-specific variants
- `experiments/v1/extraction_strategies.yaml` - Extraction-specific variants

### Golden Datasets
- `tests/fixtures/golden_queries.json` - Original (21 queries, lipid+diabetes)
- `tests/fixtures/golden_queries_expanded.json` - Expanded (54 queries, 15 source families)
- `tests/fixtures/golden_queries_diverse.json` - Diverse (20 queries, 13 source families)
- `tests/fixtures/golden_queries_comprehensive.json` - Comprehensive (35 queries, 14 source families)

### Results
- `data/evals_comprehensive_ablation/` - All evaluation artifacts
- `docs/ablation_study.md` - Running documentation with results

## How to Run

### Run All Variants with Expanded Dataset (Recommended)

```bash
cd /Users/minghao/Desktop/personal/qna_medical_referenced

# Run all 22 variants with expanded dataset (54 queries, 15 source families)
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --all-variants \
  --dataset-path tests/fixtures/golden_queries_expanded.json \
  --include-answer-eval \
  > data/evals_comprehensive_ablation/run_expanded_$(date +%Y%m%d_%H%M%S).log 2>&1 &

echo "PID: $!"
```

### Run with Different Datasets

```bash
# Quick cross-domain check (20 queries, 13 source families)
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --all-variants \
  --dataset-path tests/fixtures/golden_queries_diverse.json \
  --include-answer-eval

# Full coverage (35 queries, 14 source families)
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --all-variants \
  --dataset-path tests/fixtures/golden_queries_comprehensive.json \
  --include-answer-eval
```

### Run Individual Variants

```bash
# Run a specific variant
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --variant html_html2md \
  --dataset-path tests/fixtures/golden_queries_expanded.json \
  --include-answer-eval
```

### Parallel Execution (if memory allows)

```bash
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/comprehensive_ablation.yaml \
  --all-variants \
  --dataset-path tests/fixtures/golden_queries_expanded.json \
  --parallel \
  --max-workers 4 \
  --include-answer-eval
```

## Variant Matrix

| Group | Variant | What Changes | Expected Impact |
|-------|---------|-------------|-----------------|
| **Baseline** | `baseline` | Reference config | Control |
| **PDF Extraction** | `pdf_pymupdf` | PyMuPDF vs pypdf | +NDCG, +factual accuracy |
| | `pdf_pymupdf_camelot` | +Camelot tables | +faithfulness |
| **HTML Extraction** | `html_html2md` | html2md cascade | Better HTML→MD |
| | `html_readability` | Readability-based | Cleaner text |
| | `html_fullcascade` | All extractors | Max coverage |
| **Chunking Strategy** | `chunk_custom_recursive_512` | Custom recursive | Baseline chunker |
| | `chunk_chonkie_recursive_512` | Chonkie recursive | Better boundaries |
| | `chunk_chonkie_semantic_512` | Chonkie semantic | Semantic breaks |
| | `chunk_chonkie_late_512` | Chonkie late | Post-hoc breaks |
| **Chunk Size** | `chunksize_384` | Small chunks | More granular |
| | `chunksize_650` | Medium chunks | Original size |
| | `chunksize_1024` | Large chunks | More context |
| **Retrieval** | `retrieval_semantic_only` | No BM25 | Test semantic value |
| | `retrieval_bm25_only` | No embeddings | Test keyword value |
| | `retrieval_mmr_tuned` | MMR λ=0.9 | More diverse |
| | `retrieval_no_diversification` | No MMR | Pure top-k |
| **Combined Best** | `combined_best_extraction` | Best PDF+HTML | Stack wins |
| | `combined_best_extraction_chunking` | +best chunking | Full stack |
| | `combined_all_best` | +tuned retrieval | Optimal config |
| | `combined_small_chunks_best_extraction` | Small+best extract | Granularity test |

## Preliminary Findings (from 8 completed runs)

### PDF Extraction
- **PyMuPDF improves NDCG** by 1.9% (0.9768 → 0.9951)
- **Factual accuracy jumps 25%** (0.74 → 0.93) with PyMuPDF
- **Camelot tables add faithfulness** (0.0 → 1.0) but slightly reduce factual accuracy
- PyMuPDF extracts less text (1750 vs 1907 chunks) but higher quality

### Retrieval Strategy
- **BM25 consistently weakest** (MRR=0.8571, NDCG~0.90)
- **Semantic-only competitive** with hybrid in small dataset
- **MMR diversification** helps PyMuPDF variants (NDCG 0.9866 → 0.9951)

### Caveats
- Only 7 queries in original dataset — results may not be statistically significant
- All variants achieve perfect hit rate and MRR — ceiling effect
- Expanded dataset (54 queries, 15 source families) will provide more discriminative results

## Next Steps

1. **Run full ablation with expanded dataset** (54 queries)
   - This will take ~1-2 hours with batch size=50 optimization
   - Run in background with `> log 2>&1 &`

2. **Run with diverse dataset** (20 queries, 13 source families)
   - Quick cross-domain validation
   - ~30-45 minutes

3. **Compile results across datasets**
   - Compare metrics across dataset sizes
   - Identify which variants perform consistently vs dataset-dependent

4. **Create findings presentation**
   - Summary table of all variants
   - Key insights per dimension
   - Recommended optimal configuration
   - Dataset size impact analysis

## How to Extract Results

```bash
# Extract metrics from all completed runs
for dir in data/evals_comprehensive_ablation/202604*/; do
  name=$(basename "$dir" | sed 's/^[^Z]*Z_//')
  if [ -f "$dir/retrieval_metrics.json" ]; then
    echo "=== $name ==="
    python3 -c "
import json
d = json.load(open('$dir/retrieval_metrics.json'))
print(f\"  HR@K: {d.get('hit_rate_at_k'):.4f} | MRR: {d.get('mrr'):.4f} | NDCG: {d.get('ndcg_at_k'):.4f}\")
print(f\"  Precision: {d.get('precision_at_k'):.4f} | Recall: {d.get('recall_at_k'):.4f}\")
print(f\"  Exact Hit: {d.get('exact_chunk_hit_rate'):.4f} | Evidence: {d.get('evidence_hit_rate'):.4f}\")
"
  fi
done
```

## Environment Notes

- **API Key**: Valid DashScope API key required (already configured in `.env`)
- **Memory**: Parallel execution may hit memory limits; sequential is safer
- **Time**: Each variant takes ~3-4 minutes with batch size=50
- **Storage**: Results in `data/evals_comprehensive_ablation/`

## Contact

For questions about the experiment design or codebase, refer to:
- `docs/ablation_study.md` - Comprehensive documentation
- `src/cli/eval_pipeline.py` - CLI entrypoint
- `src/evals/assessment/orchestrator.py` - Assessment orchestration
- `src/experiments/config.py` - Experiment config loading
