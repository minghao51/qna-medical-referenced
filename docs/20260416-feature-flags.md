# Feature Flags Reference

Toggleable features in the RAG pipeline, configurable via environment variables or `settings.py`. Each flag supports ablation study and gradual rollout.

## Retrieval Feature Flags

### `ENABLE_RERANKING` (default: `false`)

Cross-encoder reranking of retrieval candidates. When enabled, the pipeline overfetches candidates and re-scores them with a cross-encoder model before returning top-k.

| Setting | Key | Default |
|---------|-----|---------|
| Enable | `ENABLE_RERANKING` | `false` |
| Model | `RERANKER_MODEL` | `BAAI/bge-reranker-base` |
| Batch size | `RERANKER_BATCH_SIZE` | `16` |
| Device | `RERANKER_DEVICE` | `cpu` |
| Top-K override | `RERANK_TOP_K` | `null` (auto) |
| Score threshold | `RERANK_SCORE_THRESHOLD` | `null` |
| Mode | `RERANKING_MODE` | `cross_encoder` |

**Ablation impact**: Measures whether cross-encoder re-scoring improves retrieval precision vs. raw hybrid search scores. Disabling isolates BM25+semantic contribution.

**Enable for production**:
```bash
ENABLE_RERANKING=true
RERANKER_MODEL=BAAI/bge-reranker-base
```

---

### `HYDE_ENABLED` (default: `false`)

Hypothetical Document Embeddings (HyDE). Generates a hypothetical answer via LLM, then embeds that answer for retrieval instead of the raw query.

| Setting | Key | Default |
|---------|-----|---------|
| Enable | `HYDE_ENABLED` | `false` |
| Max answer length | `HYDE_MAX_LENGTH` | `200` |

**Ablation impact**: Measures whether LLM-generated hypothetical documents improve semantic retrieval over raw query embeddings.

**Enable**:
```bash
HYDE_ENABLED=true
HYDE_MAX_LENGTH=200
```

---

### `MEDICAL_EXPANSION_ENABLED` (default: `false`)

Expands user queries with medical synonyms and terminology. Requires a medical expansion provider.

| Setting | Key | Default |
|---------|-----|---------|
| Enable | `MEDICAL_EXPANSION_ENABLED` | `false` |
| Provider | `MEDICAL_EXPANSION_PROVIDER` | `noop` |

**Provider options**:
- `noop` — No expansion (passthrough)
- (Future: dictionary-based, LLM-based)

**Ablation impact**: Measures whether medical term expansion improves recall for clinical queries.

---

## Indexing Feature Flags

### `HYPE_ENABLED` (default: `false`)

Hypothetical Prompt Embedding (HyPE). During indexing, generates hypothetical questions for each chunk and stores them alongside the chunk text. At query time, matches user queries against these generated questions.

| Setting | Key | Default |
|---------|-----|---------|
| Enable | `HYPE_ENABLED` | `false` |
| Sample rate | `HYPE_SAMPLE_RATE` | `0.1` |
| Max chunks | `HYPE_MAX_CHUNKS` | `500` |
| Questions per chunk | `HYPE_QUESTIONS_PER_CHUNK` | `2` |

**Requires re-ingestion**: Changing this flag requires rebuilding the vector index.

**Ablation impact**: Measures whether HyPE questions improve retrieval hit rate for question-style queries.

**Enable**:
```bash
HYPE_ENABLED=true
HYPE_QUESTIONS_PER_CHUNK=3
```

---

### `ENABLE_KEYWORD_EXTRACTION` (default: `false`)

Extracts keywords from each chunk during indexing and stores them as metadata. Used by BM25 search for improved keyword matching.

| Setting | Key | Default |
|---------|-----|---------|
| Enable | `ENABLE_KEYWORD_EXTRACTION` | `false` |

**Requires re-ingestion**: Changing this flag requires rebuilding the vector index.

---

### `ENABLE_CHUNK_SUMMARIES` (default: `false`)

Generates short summaries for each chunk during indexing. Stored as metadata for retrieval context.

| Setting | Key | Default |
|---------|-----|---------|
| Enable | `ENABLE_CHUNK_SUMMARIES` | `false` |

**Requires re-ingestion**: Changing this flag requires rebuilding the vector index.

---

## Ablation Study Integration

Feature flags map to ablation families in `src/experiments/feature_ablation_runner.py`:

| Family | Flags | Re-ingestion required |
|--------|-------|----------------------|
| Keyword | `ENABLE_KEYWORD_EXTRACTION`, `ENABLE_CHUNK_SUMMARIES` | Yes |
| HyPE/HyDE | `HYPE_ENABLED`, `HYDE_ENABLED` | Yes (HyPE only) |
| Reranking | `ENABLE_RERANKING` | No |

Run ablations via:
```bash
uv run python scripts/run_feature_ablations.py
```

Reference config: `experiments/v1/comprehensive_ablation.yaml`
