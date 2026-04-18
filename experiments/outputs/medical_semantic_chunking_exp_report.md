# Feature Addition Experiment Report: medical_semantic_chunking_exp

**Generated:** 2026-04-18T03:11:29.595480Z

## Configuration

- **Primary Metric:** ndcg@5
- **Target Improvement:** 3.0%

## Baseline Results

- **Run Directory:** `data/evals_medical_semantic_chunking_exp/baseline/20260417T183204.354165Z_comprehensive_ablation_baseline`

### Metrics

| Metric | Baseline |
|--------|----------|
| ndcg@5 | 0.6596 |
| mrr | 0.6459 |
| exact_chunk_hit_rate | 0.0526 |
| evidence_hit_rate | 0.0175 |
| latency_p50_ms | 494.0000 |

## Variant Results

### medical_chunking

- **Run Directory:** `data/evals_medical_semantic_chunking_exp/medical_chunking/20260417T183347.382117Z_comprehensive_ablation_medical_chunking`

### Metrics vs Baseline

| Metric | Baseline | Variant | Delta | % Change | Target Met |
|--------|----------|---------|-------|----------|-----------|
| ndcg@5 | 0.6596 | 0.6596 | +0.0000 | +0.00% | ❌ No |
| mrr | 0.6459 | 0.6459 | +0.0000 | +0.00% | N/A |
| exact_chunk_hit_rate | 0.0526 | 0.0526 | +0.0000 | +0.00% | N/A |
| evidence_hit_rate | 0.0175 | 0.0175 | +0.0000 | +0.00% | N/A |
| latency_p50_ms | 494.0000 | 231.0000 | -263.0000 | -53.24% | N/A |

### query_understanding

- **Run Directory:** `data/evals_medical_semantic_chunking_exp/query_understanding/20260417T183423.016259Z_comprehensive_ablation_query_understanding`

### Metrics vs Baseline

| Metric | Baseline | Variant | Delta | % Change | Target Met |
|--------|----------|---------|-------|----------|-----------|
| ndcg@5 | 0.6596 | 0.7009 | +0.0413 | +6.26% | ✅ Yes |
| mrr | 0.6459 | 0.6766 | +0.0307 | +4.75% | N/A |
| exact_chunk_hit_rate | 0.0526 | 0.0526 | +0.0000 | +0.00% | N/A |
| evidence_hit_rate | 0.0175 | 0.0526 | +0.0351 | +200.00% | N/A |
| latency_p50_ms | 494.0000 | 226.0000 | -268.0000 | -54.25% | N/A |

### both_features

- **Run Directory:** `data/evals_medical_semantic_chunking_exp/both_features/20260417T185134.219911Z_comprehensive_ablation_both_features`

### Metrics vs Baseline

| Metric | Baseline | Variant | Delta | % Change | Target Met |
|--------|----------|---------|-------|----------|-----------|
| ndcg@5 | 0.6596 | 0.7009 | +0.0413 | +6.26% | ✅ Yes |
| mrr | 0.6459 | 0.6766 | +0.0307 | +4.75% | N/A |
| exact_chunk_hit_rate | 0.0526 | 0.0526 | +0.0000 | +0.00% | N/A |
| evidence_hit_rate | 0.0175 | 0.0526 | +0.0351 | +200.00% | N/A |
| latency_p50_ms | 494.0000 | 225.0000 | -269.0000 | -54.45% | N/A |

## Overall Results

**Winner:** query_understanding

**Improvement over baseline:** 6.26%

## Recommendations

✅ **One or more variants met the target improvement threshold.**

Consider deploying the winning variant to production.
