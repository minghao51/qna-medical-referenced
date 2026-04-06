# Comprehensive Ablation Study

## Overview

Systematic ablation of each ingestion component to reveal optimal configuration for medical RAG retrieval quality.

**Config**: `experiments/v1/comprehensive_ablation.yaml`  
**Results**: `data/evals_comprehensive_ablation/`  
**Status**: ✅ Complete (12 focused variants, clean-state)  
**Runner**: `scripts/run_variant_clean.py` — guarantees full isolation between variants

---

## Experiment Design

### Dimensions

| Dimension | Variants | What Changes |
|-----------|----------|-------------|
| **Baseline** | 1 | Reference configuration |
| **PDF Extraction** | 2 | pypdf vs pymupdf vs pymupdf+camelot |
| **HTML Extraction** | 1 | trafilatura vs html2md (others fall back to BS) |
| **Chunking Strategy** | 2 | chonkie_recursive vs chonkie_semantic |
| **Chunk Size** | 2 | 384 vs 1024 tokens |
| **Retrieval** | 3 | semantic_only vs bm25_only vs MMR tuning |
| **Combined** | 1 | pymupdf + semantic chunking + hybrid RRF |

### Base Configuration

- **Embedding**: `text-embedding-v4` (768-dim)
- **Chunking**: recursive, 650 tokens, 80 overlap
- **PDF Extractor**: `pypdf_pdfplumber` + heuristic tables
- **HTML Extractor**: `trafilatura_bs`
- **Retrieval**: RRF hybrid (semantic 0.6, keyword 0.2, boost 0.2)
- **Diversification**: MMR λ=0.75, overfetch=4
- **Dataset**: 7 golden queries (regression split)

---

## Results (Clean-State, 2026-04-04)

### Ranked by NDCG

| Rank | Variant | Chunks | HR@K | MRR | NDCG@K | Δ vs Baseline |
|------|---------|--------|------|-----|--------|---------------|
| 1 | **pymupdf_semantic_hybrid** | 1966 | 1.000 | 1.000 | **0.9976** | +1.75% |
| 2 | chunk_chonkie_semantic_512 | 2113 | 1.000 | 1.000 | 0.9874 | +0.73% |
| 3 | pdf_pymupdf | 1750 | 1.000 | 1.000 | 0.9841 | +0.40% |
| 4 | pdf_pymupdf_camelot | 1750 | 1.000 | 1.000 | 0.9841 | +0.40% |
| 5 | chunksize_384 | 2509 | 1.000 | 1.000 | 0.9841 | +0.40% |
| 6 | chunk_chonkie_recursive_512 | 2102 | 1.000 | 1.000 | 0.9827 | +0.26% |
| 7 | baseline | 1907 | 1.000 | 1.000 | 0.9801 | — |
| 8 | html_html2md | 1907 | 1.000 | 1.000 | 0.9801 | — |
| 9 | retrieval_mmr_tuned | 1907 | 1.000 | 1.000 | 0.9801 | — |
| 10 | chunksize_1024 | 1488 | 1.000 | 1.000 | 0.9728 | −0.73% |
| 11 | retrieval_semantic_only | 1907 | 1.000 | 0.886 | 0.8988 | −8.14% |
| 12 | retrieval_bm25_only | 1907 | 1.000 | 0.833 | 0.8891 | −9.13% |

### Analysis by Dimension

#### PDF Extraction (+0.4% NDCG)
- **PyMuPDF** outperforms pypdf (baseline): 0.9801 → 0.9841
- Camelot tables add **zero benefit** — identical metrics
- Fewer chunks (1750 vs 1907) but higher quality extraction

**Recommendation**: Use `pymupdf_pdfplumber` + heuristic tables

#### HTML Extraction (No Impact)
- `html_html2md` produces identical NDCG to baseline (0.9801)
- Root cause: `_should_use_fallback()` returns `True` for `trafilatura_bs` and `readability_bs`, cascading to BeautifulSoup for all strategies
- Only `html2md_trafilatura_bs` and `full_cascade` avoid fallback, but the resulting content doesn't change retrieval quality on this query set

**Recommendation**: Keep `trafilatura_bs` (fastest); no benefit from switching

#### Chunking Strategy (+0.7% NDCG)
- **Chonkie Semantic @ 512** is the best: 0.9874 (+0.7% over baseline)
- Chonkie Recursive @ 512: 0.9827 (+0.3%)
- More chunks (2100+) but better semantic boundaries

**Recommendation**: Use `chonkie_semantic` @ 512 tokens

#### Chunk Size (−0.7% to +0.4%)
- 384 tokens: 0.9841 (+0.4%) — more granular, slightly better
- 1024 tokens: 0.9728 (−0.7%) — too much context per chunk hurts precision
- Sweet spot: **384–512 tokens**

#### Retrieval Method (−9% for single-method)
- **Hybrid RRF** (baseline): 0.9801 — best overall
- Semantic-only: 0.8988 (−8.3%)
- BM25-only: 0.8891 (−9.3%)
- MMR tuned (λ=0.9): 0.9801 — no gain over baseline λ=0.75

**Recommendation**: Keep `rrf_hybrid` with MMR λ=0.75, overfetch=4

#### Combined: PyMuPDF + Semantic Chunking + Hybrid RRF
- **0.9976 NDCG** — the single best configuration
- Gains are additive: PyMuPDF (+0.4%) + Semantic chunking (+0.7%) + Hybrid RRF (baseline) ≈ +1.1%
- Not quite additive (expected 0.9912, got 0.9976) — positive interaction effect

---

## Optimal Pipeline

**`pymupdf_semantic_hybrid`** — NDCG=0.9976

| Dimension | Optimal Setting | Δ vs Baseline |
|-----------|----------------|---------------|
| PDF extraction | `pymupdf_pdfplumber` | +0.4% NDCG |
| HTML extraction | `trafilatura_bs` (baseline) | No gain from changing |
| Chunking | `chonkie_semantic` @ 512 | +0.7% NDCG |
| Chunk size | 384-512 tokens | Sweet spot |
| Retrieval | `rrf_hybrid` (λ=0.75) | +9% vs single-method |
| MMR tuning | λ=0.75 (baseline) | λ=0.9 provides no gain |

---

## Caching Bug (Resolved)

### What Happened
All pre-2026-04-04 runs in `data/evals_comprehensive_ablation/` shared the same ChromaDB collection and cached `.md` files. The `ChromaVectorStoreFactory` singleton persisted across variants, and HTML `.md` files were not regenerated with the correct strategy. This compressed all NDCG scores to 0.63–0.70, masking real signal.

### Fix
`scripts/run_variant_clean.py` ensures isolation by:
1. Resetting `ChromaVectorStoreFactory` singleton
2. Deleting the ChromaDB collection on disk
3. Deleting cached `.md` files and HTML artifacts
4. Forcing HTML re-conversion with the correct strategy
5. Running assessment with `force_rerun=True`

### Before vs After

| Variant | Cached (buggy) | Clean (fixed) | Δ |
|---------|---------------|---------------|---|
| baseline | 0.9768 | 0.9801 | +0.3% |
| pdf_pymupdf | 0.9951 | 0.9841 | −1.1% |
| html_html2md | 0.6380 | 0.9801 | **+34.2%** |
| chunk_chonkie_semantic_512 | 0.6997 | 0.9874 | **+28.8%** |
| retrieval_semantic_only | 0.7621 | 0.8988 | +13.7% |
| retrieval_bm25_only | 0.7735 | 0.8891 | +11.6% |

### Double-Suffix Bug (Resolved)
A bug in `src/experiments/config.py:_derive_collection_name()` caused collection names to be double-suffixed (e.g., `medical_docs_comprehensive_ablation_comprehensive_ablation`). Fixed by making the function idempotent — it now strips any existing suffix before re-deriving.

---

## Running the Study

```bash
# Run a single variant with clean state
uv run python scripts/run_variant_clean.py --variant baseline

# Run all variants (sequential, with clean state)
for variant in baseline pdf_pymupdf pdf_pymupdf_camelot html_html2md \
  chunk_chonkie_semantic_512 chunk_chonkie_recursive_512 \
  chunksize_384 chunksize_1024 retrieval_semantic_only \
  retrieval_bm25_only retrieval_mmr_tuned pymupdf_semantic_hybrid; do
  uv run python scripts/run_variant_clean.py --variant $variant
done

# Skip LLM evaluation (faster, retrieval metrics only)
uv run python scripts/run_variant_clean.py --variant baseline --no-answer-eval
```

---

## Production Deployment

The optimal config (`pymupdf_semantic_hybrid`) is wired into production via the `PRODUCTION_PROFILE` environment variable:

```bash
PRODUCTION_PROFILE=pymupdf_semantic_hybrid uv run python -m src.cli.serve
```

This applies PyMuPDF extraction, Chonkie Semantic chunking @ 512, and Hybrid RRF retrieval at startup.

---

*Last updated: 2026-04-04*
