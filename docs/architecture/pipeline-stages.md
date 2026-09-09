# Pipeline Stage Vocabulary

**Source of truth:** stage constants in `src/evals/assessment/l6_contract.py` (`STAGE_*`, `PIPELINE_STAGES`, `STAGE_EVAL_LABELS`). This table mirrors it — keep both in sync.

The ingestion DAG is described with **one canonical name per stage**. Historical vocabularies (numbered component files, L-levels) map onto it as shown below. Do not introduce new vocabularies.

## Canonical stages

| Stage | Hamilton node (Phase 1 rename) | Implementation modules | Eval check | Output label |
|-------|-------------------------------|------------------------|------------|--------------|
| `download` | `nodes/download.py` | `steps/download_web.py`, `steps/download_pdfs.py` | `checks/l0_download.py` | `L0 download` |
| `parse` | `nodes/parse.py` | `steps/convert_html.py`, `steps/load_pdfs.py`, `steps/load_markdown.py` | `checks/l1_html.py`, `checks/l2_pdf.py` | `L1 html` / `L2 pdf` |
| `chunk` | `nodes/chunk.py` | `steps/chunking/*` | `checks/l3_chunking.py` | `L3 chunking` |
| `enrich` | `nodes/enrich.py` | `steps/enrich_chunks.py` | (covered by L3/L4) | `L3 enrich` |
| `reference` | `nodes/reference.py` | `steps/load_reference_data.py` | `checks/l4_reference.py` | `L4 reference` |
| `embedding` | `nodes/embedding.py` | `indexing/embedding.py`, `steps/hypothetical_questions.py` | `checks/l5_index.py` | `L5 index` |

Rules:

- **Code identifiers** (modules, functions, config keys) use the plain stage names: `download`, `parse`, `chunk`, `enrich`, `reference`, `embedding`.
- **L-numbers survive only as output labels** in eval artifacts and reports (`STAGE_EVAL_LABELS`) — never as identifiers.
- Until the Phase 1 rename lands, the Hamilton nodes live in `src/ingestion/components/` as `01_download.py` … `06_embedding.py` (digit-prefixed; importable only via the `importlib` loop in `components/__init__.py`).

## HyPE vs HyDE

Two one-letter-apart techniques with different homes — do not conflate:

- **HyPE** (Hypothetical Prompt Embeddings) — **index time**. Generates hypothetical questions for each chunk during ingestion and indexes them alongside chunk text (`ingestion/steps/hype.py`, renamed `hypothetical_questions.py` in Phase 1). Improves question→chunk recall.
- **HyDE** (Hypothetical Document Embeddings) — **query time**. Generates a hypothetical answer for the user's question, embeds *that*, and uses it to retrieve similar chunks (`rag/hyde.py`).

Note: the runtime settings keys currently live under `settings.hyde.*` even where they configure HyPE; this is reconciled in Phase 3 (roadmap P3.6).
