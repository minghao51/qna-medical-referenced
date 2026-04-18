# Feature Ablation Findings

## Latest Retrieval Snapshot

**Date**: 2026-04-15  
**Reference variant**: `pymupdf_semantic_hybrid`  
**Expanded dataset**: `tests/fixtures/golden_queries_expanded.json`  
**Query count**: 54  
**Summary bundle**: `data/evals_feature_ablation_summary_expanded/feature_ablation_summary.md`

This note captures the most recent feature-focused ablation results for keyword enrichment, HyPE/HyDE, and reranking on the expanded golden query set.

## Main Takeaways

1. **Keyword enrichment did not improve retrieval quality** on the expanded set.
2. **HyPE/HyDE did not improve retrieval quality** either, though `hype_10pct` was slightly faster than the disabled baseline.
3. **Cross-encoder reranking produced the clearest quality gain** on the larger dataset, at a noticeable latency cost.
4. **Query understanding improved nDCG@5 by +6.3%** (0.6596 → 0.7009), exceeding the 3% target. Medical semantic chunking alone had no measurable effect.

The smaller regression-split run (7 queries) made baseline look dominant overall. The larger 54-query run changes that conclusion: baseline still wins the keyword family, but reranking becomes meaningfully helpful.

## Family Results

### Keyword / Summaries

Retrieval run: `data/evals_keyword_ablation/20260415T100225.254392Z_pymupdf_semantic_hybrid_keyword_ablation_retrieval`

All four keyword variants tied on the tracked retrieval metrics:

| Variant | NDCG@K | MRR | Exact Chunk Hit | Evidence Hit | Latency p50 |
|---|---:|---:|---:|---:|---:|
| `baseline` | 0.6813 | 0.6673 | 0.0556 | 0.0185 | 515.0 ms |
| `keywords_only` | 0.6813 | 0.6673 | 0.0556 | 0.0185 | 520.5 ms |
| `summaries_only` | 0.6813 | 0.6673 | 0.0556 | 0.0185 | 525.5 ms |
| `both` | 0.6813 | 0.6673 | 0.0556 | 0.0185 | 534.5 ms |

**Interpretation**: enrichment adds cost here, but no measurable retrieval lift on this dataset.

### HyPE / HyDE

Retrieval run: `data/evals_hype_ablation/20260415T102345.365521Z_pymupdf_semantic_hybrid_hype_ablation_retrieval`

All HyPE/HyDE variants also tied on retrieval quality metrics:

| Variant | NDCG@K | MRR | Exact Chunk Hit | Evidence Hit | Latency p50 |
|---|---:|---:|---:|---:|---:|
| `hype_disabled` | 0.6813 | 0.6673 | 0.0556 | 0.0185 | 536.0 ms |
| `hype_10pct` | 0.6813 | 0.6673 | 0.0556 | 0.0185 | 520.0 ms |
| `hype_50pct` | 0.6813 | 0.6673 | 0.0556 | 0.0185 | 525.5 ms |
| `hype_100pct` | 0.6813 | 0.6673 | 0.0556 | 0.0185 | 535.0 ms |
| `hyde_only` | 0.6813 | 0.6673 | 0.0556 | 0.0185 | 531.5 ms |
| `hype_plus_hyde` | 0.6813 | 0.6673 | 0.0556 | 0.0185 | 530.0 ms |

**Interpretation**: no evidence of a quality gain from HyPE/HyDE on this expanded retrieval set. `hype_10pct` wins only because it is slightly faster than `hype_disabled`.

### Reranking

Retrieval run: `data/evals_reranking_ablation/20260415T103435.393618Z_pymupdf_semantic_hybrid_reranking_ablation_retrieval`

Reranking is where the larger dataset showed meaningful separation:

| Variant | NDCG@K | MRR | Exact Chunk Hit | Evidence Hit | Latency p50 |
|---|---:|---:|---:|---:|---:|
| `no_reranking` | 0.6813 | 0.6673 | 0.0556 | 0.0185 | 236.5 ms |
| `cross_encoder_only` | 0.7205 | 0.7034 | 0.0741 | 0.1852 | 485.0 ms |
| `mmr_only` | 0.6647 | 0.6682 | 0.0556 | 0.0556 | 538.0 ms |
| `both_reranking` | 0.6647 | 0.6682 | 0.0556 | 0.0556 | 774.0 ms |

`cross_encoder_only` versus `no_reranking`:

- **NDCG@K**: +0.0392
- **MRR**: +0.0361
- **Exact chunk hit rate**: +0.0185
- **Evidence hit rate**: +0.1667
- **Latency p50**: +248.5 ms

**Interpretation**: reranking is the only tested technique that delivered a clear quality improvement on the larger retrieval benchmark, but it roughly doubles p50 latency.

### Medical Semantic Chunking / Query Understanding

**Date**: 2026-04-18  
**Dataset**: `tests/fixtures/golden_queries_all.json`  
**Query count**: 57  
**Report**: `experiments/outputs/medical_semantic_chunking_exp_report.json`

| Variant | NDCG@5 | MRR | Exact Chunk Hit | Evidence Hit | Latency p50 |
|---|---:|---:|---:|---:|---:|
| `baseline` | 0.6596 | 0.6459 | 0.0526 | 0.0175 | 494.0 ms |
| `medical_chunking` | 0.6596 | 0.6459 | 0.0526 | 0.0175 | 231.0 ms |
| `query_understanding` | 0.7009 | 0.6766 | 0.0526 | 0.0526 | 226.0 ms |
| `both_features` | 0.7009 | 0.6766 | 0.0526 | 0.0526 | 225.0 ms |

`query_understanding` versus `baseline`:

- **NDCG@5**: +0.0413 (+6.3%)
- **MRR**: +0.0307
- **Evidence hit rate**: +0.0351 (3× improvement)
- **Hit rate@K**: +0.0526 (0.7368 → 0.7895)
- **Latency p50**: −268.0 ms (reused existing index)

**Interpretation**: medical semantic chunking produced identical retrieval metrics to the baseline `chonkie_semantic` strategy — no measurable quality difference. Query understanding (rule-based query classification → retrieval parameter routing) delivered the only improvement, exceeding the 3% target. The `both_features` variant matched `query_understanding` exactly, confirming medical chunking adds nothing on top. Notably, query understanding variants were faster because they reused the existing vector store index rather than re-embedding.

## Recommendation

- Keep `baseline` as the default for keyword/summaries.
- Treat HyPE/HyDE as optional and not justified by current retrieval evidence.
- Consider `cross_encoder_only` reranking when retrieval quality matters more than latency.
- **Enable query understanding by default** — it improves nDCG@5 by +6.3% at no latency cost.

## Caveat

The expanded 54-query comparison completed in **retrieval-only recovery mode** for the larger sweep. The original full run stalled during winner answer-eval, so the expanded summary is the correct source for retrieval conclusions, but not for final answer-quality conclusions across every feature family.
