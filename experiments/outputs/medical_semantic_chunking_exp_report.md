# Feature Addition Experiment Report: medical_semantic_chunking_exp

**Generated:** 2026-04-17T10:55:50.755497Z

## Configuration

- **Primary Metric:** ndcg@5
- **Target Improvement:** 3.0%

## Baseline Results

- **Run Directory:** `data/evals_medical_semantic_chunking_exp/baseline/20260417T013359.499237Z_comprehensive_ablation_baseline`

### Metrics

| Metric | Baseline |
|--------|----------|
| ndcg@5 | 0.6596 |
| mrr | 0.6459 |
| exact_chunk_hit_rate | 0.0526 |
| evidence_hit_rate | 0.0175 |
| latency_p50_ms | 563.0000 |

## Variant Results

### medical_chunking

- **Run Directory:** `data/evals_medical_semantic_chunking_exp/medical_chunking/20260417T020246.763666Z_comprehensive_ablation_medical_chunking`

### Metrics vs Baseline

| Metric | Baseline | Variant | Delta | % Change | Target Met |
|--------|----------|---------|-------|----------|-----------|
| ndcg@5 | 0.6596 | 0.6596 | +0.0000 | +0.00% | ❌ No |
| mrr | 0.6459 | 0.6459 | +0.0000 | +0.00% | N/A |
| exact_chunk_hit_rate | 0.0526 | 0.0526 | +0.0000 | +0.00% | N/A |
| evidence_hit_rate | 0.0175 | 0.0175 | +0.0000 | +0.00% | N/A |
| latency_p50_ms | 563.0000 | 227.0000 | -336.0000 | -59.68% | N/A |

### query_understanding

- **Run Directory:** `data/evals_medical_semantic_chunking_exp/query_understanding/20260417T021944.449978Z_comprehensive_ablation_query_understanding`

### Metrics vs Baseline

| Metric | Baseline | Variant | Delta | % Change | Target Met |
|--------|----------|---------|-------|----------|-----------|
| ndcg@5 | 0.6596 | 0.6596 | +0.0000 | +0.00% | ❌ No |
| mrr | 0.6459 | 0.6459 | +0.0000 | +0.00% | N/A |
| exact_chunk_hit_rate | 0.0526 | 0.0526 | +0.0000 | +0.00% | N/A |
| evidence_hit_rate | 0.0175 | 0.0175 | +0.0000 | +0.00% | N/A |
| latency_p50_ms | 563.0000 | 225.0000 | -338.0000 | -60.04% | N/A |

### both_features

- **Run Directory:** `data/evals_medical_semantic_chunking_exp/both_features/20260417T023628.424595Z_comprehensive_ablation_both_features`

### Metrics vs Baseline

| Metric | Baseline | Variant | Delta | % Change | Target Met |
|--------|----------|---------|-------|----------|-----------|
| ndcg@5 | 0.6596 | 0.6596 | +0.0000 | +0.00% | ❌ No |
| mrr | 0.6459 | 0.6459 | +0.0000 | +0.00% | N/A |
| exact_chunk_hit_rate | 0.0526 | 0.0526 | +0.0000 | +0.00% | N/A |
| evidence_hit_rate | 0.0175 | 0.0175 | +0.0000 | +0.00% | N/A |
| latency_p50_ms | 563.0000 | 223.0000 | -340.0000 | -60.39% | N/A |

## Overall Results

**Winner:** baseline


## Recommendations

❌ **No variants met the target improvement threshold.**

Consider:
- Tuning variant parameters
- Combining successful features from multiple variants
- Investigating why features didn't improve performance
