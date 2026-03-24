# Nuke & Regenerate Eval Data

## Full Reset Sequence

### 1. NUKE everything

```bash
# Remove raw source files
rm -rf data/raw/*.html data/raw/*.pdf data/raw/*.md

# Remove processed data
rm -rf data/processed/*

# Remove vector stores
rm -rf data/vectors/*.json

# Remove download manifest
rm -f data/raw/download_manifest.json

# Remove eval artifacts (optional, if you want a clean slate)
rm -rf data/evals/
rm -rf data/evals_expanded/
```

### 2. Rebuild with new sources (768-dim embeddings)

```bash
uv run python -m src.cli.ingest --force
```

This downloads ~39 HTML pages + ~7 PDFs and embeds them at 768-dim.

### 3. Verify vector store

```bash
python -c "
import json
d = json.load(open('data/vectors/medical_docs_expanded_768dim.json'))
print(f'Vectors: {len(d[\"ids\"])}, Dim: {len(d[\"embeddings\"][0]) if d[\"embeddings\"] else \"N/A\"}')"
```

Expected output: `Vectors: 5000-8000, Dim: 768`

### 4. Run eval pipeline with HyDE + DeepEval

#### Option A: Single variant with HyDE + answer eval

```bash
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/baseline_expanded_768dim.yaml \
  --name "expanded_768dim_hyde" \
  --enable-hyde \
  --include-answer-eval
```

#### Option B: All 4 variants with HyDE + answer eval

```bash
uv run python -m src.cli.eval_pipeline \
  --config experiments/v1/baseline_expanded_768dim.yaml \
  --all-variants \
  --name "expanded_768dim_all_variants" \
  --enable-hyde \
  --include-answer-eval
```

## Variant List (baseline_expanded_768dim.yaml)

| Variant | Description |
|---------|-------------|
| `best_combined` | chunk_small + combined_best (pymupdf+camelot+html2md) |
| `rrf_mmr_tuned` | Higher MMR lambda (0.9) for more diverse results |
| `chonkiesemantic` | Semantic chunking for comparison |
| `html_fullcascade` | Full HTML extraction cascade |

## What Gets Generated

| Stage | Output |
|-------|--------|
| Ingestion | `data/vectors/medical_docs_expanded_768dim.json` |
| Eval artifacts | `data/evals_expanded/` |
| HyDE queries | Computed on-the-fly (no pre-generation needed) |
| Golden queries | Reused from `tests/fixtures/golden_queries.json` |

## Notes

- **HyDE is computed on-the-fly** — no pre-generation needed, just pass `--enable-hyde`
- **Golden queries are reused** — `enable_llm_generation: false` in the config
- **DeepEval requires API access** — ensure `DASHSCOPE_API_KEY` is set
- **~10-20 min runtime** with HyDE + DeepEval enabled
