# Pipeline Quality Assessment Framework (L0-L6 + RAG)

## Summary

- The real pipeline orchestration is `src/ingestion/pipeline.py`.
- Current pipeline executes L0-L6 successfully but only reports counts/timing; it does not produce structured quality metrics, regression baselines, or preserved evaluation artifacts.
- Implement a new evaluation subsystem and CLI that assesses each stage (download, HTML conversion, PDF extraction, chunking, reference loading, indexing, retrieval, optional answer generation) and writes versioned artifacts to disk.
- Use a hybrid evaluation dataset strategy (user-selected): merge existing deterministic golden queries (`tests/fixtures/golden_queries.json`) with Gemini-generated synthetic queries/QA pairs, while preserving all generated artifacts and raw judge outputs.

## Current Code Review Findings (What Exists / Gaps)

- `src/ingestion/pipeline.py`: runs L0-L6 sequentially and prints summary, but no structured metrics capture or quality thresholds.
- `src/ingestion/indexing/vector_store.py`: already exposes `similarity_search_with_trace()` with useful retrieval score decomposition and timings.
- `src/rag/runtime.py`: already exposes `retrieve_context_with_trace()` suitable for retrieval evaluation artifacts.
- `tests/test_retrieval.py` and `tests/fixtures/golden_queries.json`: good starting point for retrieval metrics but not a reusable evaluation pipeline and not artifact-preserving.

## Research Basis (Quality Assessment Best Practices to Apply)

- Task-specific evals and versioned test sets should be treated as core product infrastructure, not ad hoc spot checks ([OpenAI eval design guide](https://platform.openai.com/docs/guides/evals)).
- Retrieval should be measured with ranked IR metrics (Hit/Recall@k, MRR, MAP/nDCG where labels allow), not only “looks good” manual checks ([Haystack evaluation docs](https://docs.haystack.deepset.ai/docs/evaluation), [BEIR benchmark paper](https://arxiv.org/abs/2104.08663)).
- RAG quality should be decomposed into retrieval quality, context quality, and generation quality/groundedness rather than a single score ([NVIDIA RAG evaluation metrics](https://docs.nvidia.com/rag/2.3.0/evaluation/metrics.html), [Ragas metrics docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)).
- Chunking quality should be evaluated via downstream retrieval impact plus chunk-level heuristics (size/overlap/boundary integrity); chunk size/overlap materially affects retrieval quality ([Azure AI Search chunking guidance](https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents)).
- HTML extraction quality should include content-retention and boilerplate-removal checks, not just “conversion succeeded” ([BeautifulSoup parsing/text extraction docs](https://www.crummy.com/software/BeautifulSoup/bs4/doc/), [Trafilatura documentation and extraction benchmark references](https://trafilatura.readthedocs.io/)).
- PDF text extraction has known layout/quality limitations; page-level extraction coverage and empty-page rates should be tracked explicitly ([pypdf text extraction docs](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)).

## Scope (Locked)

- Full-stack evaluation for L0-L6 plus RAG retrieval and optional answer generation metrics.
- Hybrid LLM mode by default:
- Deterministic base dataset from fixture(s).
- Optional Gemini-generated synthetic questions/QA pairs enabled by default.
- CLI flag to disable all LLM-based generation/judging for offline runs.

## Public Interfaces / CLI Changes

- Add new CLI entrypoint: `python -m src.cli.eval_pipeline`
- Add new module-level runner function: `src.evals.pipeline_assessment.run_assessment(...)`
- No required changes to existing ingestion CLI behavior (`src.cli.ingest`) in first pass

### Proposed CLI arguments (decision-complete)
- `--artifact-dir` (default: `data/evals`)
- `--name` (optional run label)
- `--dataset-path` (optional JSON dataset; if absent, auto-build from fixture + synthetic generation)
- `--top-k` (default: `5`)
- `--max-synthetic-questions` (default: `40`)
- `--disable-llm-generation` (disable synthetic question generation)
- `--disable-llm-judging` (disable answer faithfulness/relevance judging)
- `--include-answer-eval` (default on if Gemini key present; off otherwise)
- `--sample-docs-per-source-type` (default: `10`)
- `--seed` (default: `42`)
- `--fail-on-thresholds` (non-zero exit if key metrics fall below thresholds)
- `--thresholds-file` (optional JSON overrides)

## Implementation Plan (Files and Responsibilities)

### 1) Create evaluation package
- Add `src/evals/__init__.py`
- Add `src/evals/pipeline_assessment.py`
- Add `src/evals/artifacts.py`
- Add `src/evals/schemas.py`
- Add `src/evals/metrics.py`
- Add `src/evals/dataset_builder.py`
- Add `src/evals/llm_judges.py`
- Add `src/evals/step_checks.py`
- Add `src/cli/eval_pipeline.py`

### 2) Artifact model and preservation (always-on)
- Write all outputs to `data/evals/<timestamp>_<slug>/`
- Persist:
- `manifest.json` (run config, repo info if available, timestamps, versions)
- `step_metrics.json` (L0-L6 aggregate metrics)
- `step_findings.json` (warnings/failures by stage)
- `html_metrics.jsonl` (per HTML file)
- `pdf_metrics.jsonl` (per PDF/page aggregate file metrics)
- `chunk_metrics.jsonl` (per chunk and aggregate summaries)
- `reference_metrics.json` (CSV/reference checks)
- `index_metrics.json` (embedding/index integrity)
- `retrieval_dataset.json` (final dataset actually used, including generated items)
- `retrieval_dataset_generation.jsonl` (raw generation attempts + validation outcomes)
- `retrieval_results.jsonl` (per query retrieved docs, scores, trace)
- `retrieval_metrics.json` (aggregate retrieval metrics)
- `rag_results.jsonl` (per query answer outputs + context + judge scores, if enabled)
- `rag_metrics.json` (aggregate answer metrics, if enabled)
- `summary.md` (human-readable report)
- `latest` pointer file or symlink replacement file `data/evals/latest_run.txt` containing path (portable text, not symlink)

### 3) Stage-by-stage quality checks (L0-L6)

#### L0 Download quality (`src/ingestion/steps/download_web.py` outputs already on disk)
- Measure file inventory quality from `data/raw/*.html`:
- File count by source family (ACE/HealthHub/HPP/MOH via filename/url map heuristics)
- Empty/small file rate (e.g., `< 2 KB`)
- Duplicate-content rate (hash duplicates)
- HTML parseability rate (BeautifulSoup parse succeeds)
- Optional marker presence (contains `<html`, `<body`, or meaningful visible text)
- If download logs are unavailable, classify as “post-download content audit” (explicitly labeled)

#### L1 HTML -> Markdown quality (`src/ingestion/steps/convert_html.py`)
- Per-file metrics:
- HTML visible-text chars vs markdown chars (retention ratio)
- Markdown emptiness/triviality rate
- Boilerplate suspicion score (repeated nav/footer terms ratio)
- Structural preservation counts (headings, lists, links tables if present)
- Non-content artifact ratio (e.g., repeated menu tokens)
- Aggregate metrics:
- Median retention ratio
- % files below minimum retention threshold
- % markdown files with near-empty output
- Emit warnings for outliers for manual inspection

#### L2 PDF extraction quality (`src/ingestion/steps/load_pdfs.py`)
- Per-PDF metrics:
- Page count
- Extracted pages count / total pages
- Empty page rate
- Characters per page distribution (min/median/max)
- OCR-needed suspicion (very high empty-page rate or low char density)
- Encoding anomalies (replacement char count, excessive whitespace ratio)
- Aggregate:
- Total pages, extraction coverage %, empty-page %

#### L3 Chunking quality (`src/ingestion/steps/chunk_text.py`)
- Per-chunk metrics:
- length chars, source, page, chunk id
- overlap observed vs configured overlap (approximate suffix/prefix comparison)
- boundary quality heuristic (ends mid-token/mid-sentence)
- duplicate chunk content hash
- metadata completeness (`id/source/page`)
- Aggregate:
- Chunk length histogram summary
- Duplicate chunk rate
- Boundary-cut rate
- Coverage estimate (sum unique chars/chunks per source vs extracted text chars)
- Recommendation block if chunk size/overlap looks poor

#### L4 Reference CSV quality (`src/ingestion/steps/load_reference_data.py`)
- Schema validation reuse existing required columns
- Row completeness rate by field
- Duplicate `test_name` rate
- Empty/placeholder notes rate
- Numeric/range parseability heuristic for `normal_range`
- Document conversion count consistency (`rows == docs generated`)

#### L5 Indexing / embedding store quality (`src/ingestion/indexing/vector_store.py`)
- Integrity checks:
- `ids`, `contents`, `embeddings`, `metadatas` array length equality
- Embedding dimension consistency across all vectors
- Duplicate content/hash rate and dedupe effect
- Source distribution in index
- Empty/short content unexpectedly indexed
- Retrieval readiness checks:
- Random spot-query latency (trace timing)
- Semantic fallback detection rate (embedding failures)
- Persistence file size and loadability
- Index coverage:
- Expected docs (`chunks + ref_docs`) vs stored docs delta (dedupe explained)

#### L6 Retrieval / RAG quality (`src/rag/runtime.py`, `src/usecases/chat.py`)
- Retrieval metrics (ranked IR):
- HitRate@k
- Recall@k
- Precision@k (for labeled positives)
- MRR
- nDCG@k (binary relevance initially)
- Source hit rate (expected source appears in top-k)
- Latency p50/p95 using `retrieve_context_with_trace()`
- Context quality metrics:
- Context precision/recall proxies from labeled positives
- Context token/char length distribution
- Duplicate source chunk rate in top-k
- Answer generation quality (optional):
- Answer relevance (LLM judge)
- Faithfulness/groundedness to retrieved context (LLM judge)
- Citation/source coverage heuristic (answer references retrieved facts/sources)
- Safety proxy checks (contains diagnosis certainty language, missing care-provider disclaimer)

## Dataset Strategy (Deterministic + LLM-generated)

### Deterministic seed set
- Load and normalize `tests/fixtures/golden_queries.json`
- Convert existing `expected_keywords` and `expected_sources` into initial labels
- Add explicit `query_id` and metadata fields during normalization

### Synthetic dataset generation (Gemini; preserved artifacts)
- Sample contexts stratified by source type:
- PDF chunks
- HTML-derived markdown chunks (if indexed)
- CSV reference docs
- For each sampled context, ask Gemini to produce JSON:
- `question`
- `answer`
- `answer_span_or_quote` (short evidence phrase)
- `expected_keywords`
- `difficulty`
- `source_hint`
- Validate generated item locally before acceptance:
- JSON parse succeeds
- Evidence phrase appears in context
- Question is non-trivial and medically relevant
- Avoid near-duplicates by semantic-lite hash / normalized text hash
- Save all attempts, accepted items, and rejection reasons
- Merge accepted synthetic items with deterministic seeds into `retrieval_dataset.json`

### Labeling for retrieval metrics
- Primary positive labels:
- Source/file match (`expected_sources`)
- For synthetic items, source/page/chunk id from generation seed context
- Secondary weak labels:
- keyword overlap threshold in retrieved chunk
- Evidence phrase containment
- Mark label confidence (`high` for source/chunk exact, `medium` for source-only, `low` for keyword-only) and compute metrics separately for high-confidence subset

## LLM Judge Design (Answer Eval)

- Implement strict JSON-only prompts in `src/evals/llm_judges.py` using existing Gemini client stack (no new dependency)
- Judge outputs per query:
- `relevance_score` (1-5)
- `faithfulness_score` (1-5)
- `grounded_claim_ratio` (0-1 estimate)
- `has_medical_disclaimer` (bool)
- `notes`
- Store raw prompt, raw response, parsed JSON, and parse failure info
- If judge parse fails:
- retry up to existing retry policy style
- mark query as `judge_error`
- continue run (do not abort)
- Aggregate metrics exclude judge errors but report judge error rate

## Thresholds and Regression Policy

- Add default thresholds in code (overridable via JSON):
- L1 markdown empty rate `<= 10%`
- L2 PDF empty-page rate `<= 20%`
- L3 duplicate chunk rate `<= 5%`
- L5 embedding dimension consistency `== 100%`
- L6 HitRate@5 on high-confidence set `>= 0.7`
- L6 MRR on high-confidence set `>= 0.4`
- L6 retrieval p95 latency target reported (warn-only first pass)
- `--fail-on-thresholds` exits non-zero on threshold failures and writes failures to `step_findings.json`

## Testing Plan (Implementation Verification)

### Unit tests
- `tests/test_eval_metrics.py`
- Validate Recall@k, MRR, nDCG implementations with small deterministic fixtures
- `tests/test_eval_artifacts.py`
- Ensure timestamped run dir and all expected files are created
- `tests/test_step_checks_html_pdf_chunk.py`
- Heuristic metrics on synthetic HTML/PDF/chunk inputs
- `tests/test_dataset_builder.py`
- Fixture normalization and synthetic generation validation/parsing (mocked Gemini outputs)
- `tests/test_llm_judges.py`
- JSON parse success/failure and retry handling with mocked client

### Integration tests (offline)
- `tests/test_pipeline_assessment_smoke.py`
- Run evaluator against a tiny local fixture corpus / mocked vector store and assert report artifacts + metric keys exist

### Optional live tests (skip without key)
- `tests/test_pipeline_assessment_live.py`
- Gemini-backed synthetic generation and/or judge path using existing skip pattern (`GEMINI_API_KEY` absent)

## Implementation Sequence (Order of Work)

1. Build schemas + artifact writer + metrics library (pure Python, no new deps).
2. Implement deterministic dataset loading from `tests/fixtures/golden_queries.json`.
3. Implement retrieval evaluation using existing `retrieve_context_with_trace()` / `similarity_search_with_trace()`.
4. Implement stage checks for L1-L5 from current local files and index JSON.
5. Implement L0 post-download audit and L6 aggregate report.
6. Add Gemini synthetic dataset generation (hybrid mode) with strict artifact preservation.
7. Add optional Gemini answer judging.
8. Add CLI entrypoint and documentation snippet in `README.md`.
9. Add tests and threshold gating.

## Assumptions and Defaults (Locked for First Pass)

- Use existing Gemini infrastructure (`google-genai`) and current `.env` key if available.
- No new heavy dependencies (e.g., `ragas`, `pandas`, `numpy`) in first pass; implement metrics and artifact logic in stdlib Python.
- Evaluation runs will not mutate indexed corpus by default; they read existing `data/raw` and `data/vectors/medical_docs.json`.
- Generated synthetic questions and judge outputs are always preserved to disk (even if low quality or rejected).
- If Gemini is unavailable, evaluation still runs in offline mode using deterministic dataset and heuristic metrics.
- First-pass RAG answer evaluation is optional and non-blocking; retrieval metrics are the primary release gate.
