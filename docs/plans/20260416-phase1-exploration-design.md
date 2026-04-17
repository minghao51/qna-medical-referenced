# Phase 1 Exploration Design: Medical Semantic Chunking & Query Understanding

**Date:** 2026-04-16
**Status:** Design Validated
**Type:** Exploration (Scope-boxed, depth over breadth)

---

## Overview

**Goal:** Explore two retrieval improvements and validate via offline evaluation.

**Approach:** Ablation-style exploration. Build each feature as a toggleable variant, run evaluation pipeline, compare against baseline.

**Success Criterion:** nDCG@5 improvement ≥ 3% over baseline

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              EXPLORATION VALIDATION PIPELINE                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Baseline (current) ────┐                                   │
│                         ├──► Evaluation ───► Metrics         │
│  Variant A (chunking) ───┤              (nDCG@5, etc.)       │
│                         │                                    │
│  Variant B (query) ──────┤                                    │
│                         │                                    │
│  Variant A+B (both) ─────┘                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Feature 1: Medical Semantic Chunking

### Hypothesis
Medical documents have unique structure (clinical sections, drug dosing tables, lab reference ranges) that domain-aware chunking can preserve better than generic semantic chunking.

### Implementation

**New strategy:** `medical_semantic` - layers on top of existing `chonkie_semantic`

1. **Preprocessing:** Detect and preserve medical-specific structures
   - Lab value tables (don't split mid-table)
   - Drug dosing sections (keep dosage + administration together)
   - Clinical note headers (SOAP, history sections)

2. **Boundary hints:** Pass medical structure hints to chonkie
   - Section boundaries from markdown headers
   - Table/list boundaries as hard breaks
   - Medical entity boundaries (drug names, conditions)

3. **New files:**
   - `src/ingestion/steps/chunking/medical_semantic.py` - Strategy class
   - `src/ingestion/steps/chunking/medical_entity_detector.py` - spaCy/scispaCy entity boundaries
   - `src/ingestion/steps/chunking/medical_structure_rules.py` - Heuristics for tables/dosing

4. **Toggle:** Strategy selection via config (extend `RECOMMENDED_STRATEGIES`)

### Evaluation
Run chunking variant → re-index → eval retrieval quality vs baseline

---

## Feature 2: Query Understanding Module

### Hypothesis
Different query types need different retrieval approaches. "What is hypertension?" benefits from focused similarity search; "Compare Type 1 vs Type 2 diabetes" needs multi-document aggregation.

### Implementation

**Classification:** Rule-based + LLM fallback hybrid

1. **Query types:**
   - definition: "What is X?"
   - comparison: "X vs Y"
   - reference_range: "Normal BP range"
   - symptom_query: "Symptoms of anemia"
   - treatment: "Treatment for high cholesterol"
   - risk_factor: "Risk factors for heart disease"
   - follow_up: Context-dependent
   - complex: Multi-part

2. **Retrieval routing:**
   - Definition → high similarity threshold, top-3 only
   - Comparison → multi-source, explicit contrast
   - Reference range → table-weighted retrieval
   - Complex → multi-query decomposition

3. **New files:**
   - `src/rag/query_understanding/__init__.py`
   - `src/rag/query_understanding/classifier.py` - Rule + LLM hybrid
   - `src/rag/query_understanding/router.py` - Type → retrieval params
   - `src/rag/query_understanding/strategies.py` - Type-specific logic
   - Integration into `src/rag/runtime.py`

4. **Toggle:** Feature flag in runtime config

### Evaluation
Classify eval queries, apply type-specific retrieval, measure nDCG@5 per type

---

## Experimentation Framework

### Approach
Extend existing `feature_ablation_runner.py` to support "feature addition" mode.

### Implementation

1. **Experiment configs (YAML):**
   ```yaml
   name: semantic_chunking_exp
   baseline:
     chunking_strategy: chonkie_semantic
     query_understanding: false
   variants:
     - name: medical_chunking
       chunking_strategy: medical_semantic
       query_understanding: false
     - name: query_understanding
       chunking_strategy: chonkie_semantic
       query_understanding: true
     - name: both
       chunking_strategy: medical_semantic
       query_understanding: true
   metrics:
     primary: ndcg@5
     target_improvement: 0.03
   ```

2. **New files:**
   - `src/experiments/feature_addition_runner.py` - Addition runner
   - `src/experiments/experiment_config.py` - YAML schema
   - `src/experiments/comparison_report.py` - Diff reports
   - CLI: `uv run python -m experiments.run_addition <exp_name>`

3. **Execution flow:**
   - For each variant: re-index (if chunking changed) → run retrieval → evaluate
   - Collect metrics per variant
   - Generate comparison report

### Output
Comparison report showing nDCG@5 for each variant, highlighting which beats baseline by ≥3%

---

## Implementation Order

```
medical_semantic (independent)
    │
    ├──► feature_addition_runner (needs chunking variant)
    │
query_understanding (independent)
    │
    └──► feature_addition_runner (needs query variant)
          │
          └──► comparison_report (needs runner results)
```

### Timeline

**Week 1-2:** Medical Semantic Chunking
- Day 1-2: Medical entity detector (spaCy/scispaCy)
- Day 3-4: Medical structure rules (tables, dosing)
- Day 5-7: Integrate with chonkie_semantic adapter
- Day 8-10: Unit tests, manual validation

**Week 2-3:** Query Understanding
- Day 1-2: Rule-based classifier
- Day 3-4: LLM fallback + caching
- Day 5-6: Retrieval routing logic
- Day 7-8: Integration with runtime.py
- Day 9-10: Unit tests, query type distribution analysis

**Week 3-4:** Experimentation Framework
- Day 1-3: Feature addition runner (extend ablation)
- Day 4-5: Experiment config schema
- Day 6-7: Comparison report generation
- Day 8-10: End-to-end testing, golden set validation

**Week 5:** Validation
- Run full experiment suite
- Analyze results
- Document findings

---

## Success Criteria

- Primary metric: nDCG@5 improvement ≥ 3%
- Secondary metrics tracked but not gated
- Decision point after Week 5: which variant(s) to keep, which to discard

---

## Next Steps

Ready to set up for implementation?
