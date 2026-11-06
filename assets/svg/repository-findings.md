# Repository findings
## Evidence discipline and delegation
**Verified** means inspected source or non-sensitive local artifact; **reported** means a claim in repository documentation; **inference** means product interpretation; **proposal** means future behavior.

Integration discovery found local OpenCode and Codex CLIs, but no matching dedicated MCP tools. `opencode models` listed `opencode-go/deepseek-v4-flash`, not DeepSeek V4.1 Flash. Codex's model cache listed `gpt-5.6-luna`, not GPT Luna 6.0. Explicit fallbacks were announced. OpenCode with that listed model failed twice before investigation with an unexpected server error; Sol performed backend/data investigation directly. Codex `gpt-5.6-luna` completed a read-only frontend investigation. Its claim that `.planning/codebase` was absent was contradicted by Sol's direct reads; that claim is rejected. Findings below reflect verified source, not uncritically copied agent output.

Initial worktree was clean on `main`; design work uses `design/evidence-led-redesign`. No nested project AGENTS files were found outside dependencies. Scope is restricted to `assets/svg/`; application code is unchanged. Credentials and private chat records were not inspected.

## Product and audiences
**Verified:** README describes an ingestion/evaluation/retrieval/RAG testbed with a medical Q&A frontend. The current landing page is chat, not a patient-record dashboard. There is no verified lab-report upload, longitudinal patient dataset, personal-risk prediction or clinical decision engine.
**Verified in refinement:** `docs/plans/migration/decisions.md` D01 selects a private research lab; D02 limits data to public/synthetic; D07 excludes clinical-suitability claims; D09 keeps execution CLI/YAML-first; D10 selects Pydantic Evals + primary Logfire UI. The first pass's public-reader framing was overreach and is superseded.
**Proposal:** research-first workspace, evaluation/feature/dataset inspection and a private Q&A workbench. Public rollout or patient-facing clinical positioning is not part of this design.

## Architecture and functionality
| Area | Verified implementation / evidence | Status |
|---|---|---|
| App lifecycle | `src/app/factory.py:create_app, lifespan` | Constructs LLM/history/store dependencies, applies production profile, warms index without building |
| Runtime | `src/rag/runtime.py:retrieve_context_with_trace_async, _build_pipeline_trace`; `src/rag/retrieval.py`; `src/rag/diversification.py` | Query expansion, candidate retrieval, fusion/reranking options, context and trace assembly |
| Chat | `src/app/routes/chat.py:chat, chat_stream_generator`; `src/usecases/chat.py:stream_chat_message` | POST /chat SSE; optional pipeline in terminal event; per-session admission/cancellation/persistence behavior |
| Sessions | `src/app/session.py`; `src/infra/storage/file_chat_history_store.py:save_turn, get_history, clear_history` | Server-issued cookie; atomic completed user/assistant pair; history cleared per session |
| History data | `FileChatHistoryStore._save_messages` | Persists role/content/timestamp, not citations or traces. Reload cannot recover full turn evidence |
| Chunk browser | `src/app/routes/documents.py:list_documents, get_document`; `src/ingestion/indexing/listing.py:DocumentListingMixin` | Read-only, type-filtered pagination and full chunk lookup |
| Evaluation | `src/app/routes/evaluation.py`, `frontend/src/routes/eval/+page.svelte` | Results/history/run/drilldown UI wired; artifacts and dependencies determine availability |
| Experiments | `src/app/routes/experiments.py`, `frontend/src/routes/experiments/+page.svelte` | Config/result inspection; not proof all experiment result bundles are present |
| Ingestion | `src/cli/ingest.py`; `src/ingestion/nodes/`; `src/ingestion/steps/` | Offline download/parse/chunk/enrich/embed stages; do not trigger from public UI |
| Reference loading | `src/ingestion/steps/load_reference_data.py:ReferenceDataLoader` | Validates five CSV columns and renders each row into text |

Frontend: Svelte 5, SvelteKit 2, TypeScript, Vite 7, Chart.js 4; see `frontend/package.json`. Existing markdown/highlight/Mermaid rendering, centralized API and safe URL utilities are useful. No framework replacement is justified by observed functionality.

## Routes and navigation
Current frontend routes: `/`, `/documents`, `/eval`, `/eval/ablation`, `/experiments`, `/health`, `/settings`, `/help`, `/docs/pipeline`. Inspect corresponding `frontend/src/routes/**/+page.svelte`.
- `AppShell.svelte` / `AppNav.svelte`: shared framing.
- `/settings` is read-only configuration, not a functioning settings editor.
- Help/pipeline pages are static documentation.
- Ablation page mixes API-fed results with hardcoded dated findings; label those independently.
- Frontend `api.ts` sends cookies, not an operator API-key login flow.
- **Important access constraint:** `src/app/middleware/auth.py:EXEMPT_PATHS` contains only /, /health, /docs, /openapi.json. When keys exist, /chat, /history, /documents and research APIs require X-API-Key. Do not assume the documented anonymous deployment contract is already implemented by this middleware.
- Preserve the private-lab boundary. Authentication/role policy still needs clarification for operator UI; do not infer a public deployment or embed an admin key in VITE variables/shipped JS. Evaluation routes additionally call `_require_authenticated_request`, even when no configured middleware keys are present.

## Actual local data inventory
Sol queried SQLite with `mode=ro`, Parquet through DuckDB, YAML and the public reference CSV. No embedding/model/network calls were needed.

| Artifact | Verified local content | Semantics / caveat |
|---|---|---|
| `config/sources.yaml` | 53 web URLs + 10 PDF URLs | Current configured download inventory, not indexed coverage |
| `data/chroma-d11/chroma.sqlite3` | medical_docs, 2,473 embeddings/chunks | Frozen served index according to README production contract; deployment may override |
| D11 source_type | pdf 1,306; html 597; reference_csv 460; markdown 110 | Sum = 2,473; counts are chunks, not publications or prevalence |
| D11 labels | 60 distinct source strings / logical names | Not a verified deduplicated publication count |
| D11 source_class | guideline_pdf 1,306; reference_csv 460; hpp_guideline 335; healthhub_html 282; guideline_html 86; international_html 4 | Source class and source type are different dimensions |
| D11 metadata | source_url on 2,013 chunks; missing on 460 reference chunks | Reference rows do not have a document URL; DOI/license live in CSV notes |
| D11 pages | present on 2,013 chunks; values 1–34 | All 707 HTML/Markdown chunks carry page 1. Do not imply those are actual print page locations |
| D11 hashes | 2,473 distinct content_hash values | No repeated hash values here; overlapping and near-duplicate text still possible |
| D11 quality_score | 0.65–1.0 | Processing diagnostic, not a clinical quality measure |
| `data/03_gold/chunks/raw_chunks.parquet` | 2,141 rows | Not the D11 chunk total |
| `data/03_gold/chunks/enriched_chunks.parquet` | 2,141 rows | Do not join by row number; inspect IDs/hash lineage |
| `data/03_gold/chunks/reference_data.parquet` | 471 rows | Differs from 460 served reference chunks |
| `data/raw/LabQAR/reference_ranges.csv` | 471 rows, 5 required columns, no blank required fields | test_name, normal_range, unit, category, notes. Notes encode specimen/sex/age/provenance as text |
| `experiments/outputs/medical_semantic_chunking_exp_report.json` | Present locally | Separate experiment; do not pool with 54-query reranking snapshot |

Why intermediate and frozen counts differ was not established. Do not sum 2,141 + 471 and present that as served coverage. The D11 SQLite query is a local artifact observation, not proof a deployed API uses it.

## Schema, joins, dates and units
- Chunk identity: API `id` / SQLite `embedding_id`. `source` often is a filename; `logical_name` / canonical/display labels are presentation/provenance fields, not immutable publication keys.
- Raw Parquet: id, source, page, content, content_type, section_path, chunk_index, char spans/counts, token_count_estimate, quality_score, parent_block_ids, extractor, nested metadata, previous/next_chunk_id and section_sibling_rank.
- Neighbor IDs exist in stored metadata, but list API does not expose them; detail metadata may. Do not invent adjacency endpoints.
- Page and chunk_index are distinct. Display chunk index 1 as “chunk 1” in these assets, not “second publication.”
- Reference units are heterogeneous text (e.g. nmol/L in the inspected public example); normal_range is a string with qualifiers, not a universally comparable numeric interval.
- CSV loader flattens reference facts into retrieval text. No normalized lab-value interpretation API or patient measurements were found.
- Current source documentation records a 2026-10-24 URL refresh; that is not proof frozen chunks were refreshed. Source publication, ingestion, config change and benchmark dates must remain separate.
- Time metrics are milliseconds; total displayed 1.80 s is synthetic 1,800 ms. Characters are Python/JS text lengths, not tokens; token estimates are not exact usage.

## Actual trace contract and limits
`src/rag/trace_models.py` defines RetrievalStep, RetrievedDocument, RetrievalStage, ContextStage, GenerationStage and PipelineTrace.
- Retrieval stage: query, original length/truncation flag, top_k, documents, score_weights (includes non-weight metadata), timing_ms, steps.
- Steps emitted by async runtime: query_expansion, semantic_search, keyword_search, score_fusion, reranking. Each has name/timing_ms/skipped/details.
- In current async code, keyword_search and score_fusion timing_ms are literal zero placeholders; semantic_search timing wraps the broader retrieval function. Zero must not be styled as a measured instantaneous independent call.
- Documents: rank/id/content/source/page; semantic/keyword/source_prior/source_boost/combined values; optional semantic/BM25/fused ranks, fused score, chunk_quality_score; source metadata.
- Context: total_chunks, total_chars, source labels, **preview truncated to 200 characters**. Not a complete prompt/context transcript.
- Generation: model/timing_ms/tokens_estimate. Runtime initializes token estimate to None; not provider usage.
- Total and stage times are not a start/end event ledger. Step durations do not necessarily partition total time.
- Terminal SSE contains sources/pipeline/error code/request ID. Live retrieval-stage events, nested tool calls, provider retries, cost, TTFT and exact token accounting are absent from this contract.
- Sources can be multiple entries from the same file/page: “2 source entries” is not “2 independent publications.”
- No per-sentence citation-to-chunk assertion model exists in ChatSource. Bracketed citation positioning in the synthetic UI is not a verified entailment relationship.
- Existing frontend confidence uses domain heuristics, volume and retrieval values (`confidenceCalculator.ts`); even existing labels say uncalibrated. Retire percentage-as-certainty visuals, retain optional raw diagnostics with caveats.

## Reported research, not recomputed findings
`docs/feature_ablation_findings.md` reports a 15 Apr 2026, 54-query retrieval-only reranking comparison:
no_reranking nDCG@K .6813 / p50 236.5 ms; cross_encoder_only .7205 / 485.0 ms; mmr_only .6647 / 538.0 ms; both_reranking .6647 / 774.0 ms.
Difference .0392 and +248.5 ms; latency ratio 2.05074. Underlying referenced run directory is absent locally. No uncertainty intervals or completed answer-quality comparison are established. The 57-query 18 Apr experiment is separate.

## Research refinement — newly verified evidence
A second read-only Codex gpt-5.6-luna review independently recommended an evidence registry rather than a leaderboard. Sol verified the important claims and actual artifact counts.

### Evaluation contracts and current UI pitfalls
- `EvaluationService.local_history_runs`, `load_run_payload` and `_sanitize_artifact_value` in `src/evals/artifact_service.py` force comparable=false. `aggregate_history_summary` returns null averages. `TrendingTab.svelte` already warns that cohorts are unverified. New UI must preserve this guard, not “improve” it into a speculative trend.
- `artifact_compatibility` distinguishes legacy/versioned/unsupported. Versioned format is explicitly not verified semantic identity.
- `load_step_records`, `load_step_metrics` and `load_l6_records` choose the latest run. `load_answer_quality_details(run_dir_name)` is run-scoped. Historical-case drilldown must not silently show latest-run evidence.
- `frontend/src/routes/experiments/+page.svelte:metricValue` turns absent metrics into zero; `deltaClass` colors larger values positively regardless of metric direction; `fmtDelta` multiplies raw differences by 100 with a percent suffix. Replace these semantics: null stays absent; latency/error prefer lower; nDCG deltas are score points; relative change is separately labelled.
- `QualityTab.svelte` displays means and a total scored count but does not make every metric's failed denominator equally prominent. Existing metric-specific counts/errors can support the new coverage view.
- `src/evals/pydantic_tasks.py:ReportCompleteness, report_completeness, project_report` has expected/measured/failed/skipped/errored concepts for newer reports. Do not map older error_count blindly into all these newer statuses.
- `src/experiments/feature_addition_runner.py:ExperimentSummary.get_winner` now gates eligibility. An old JSON winner field is not a newly eligible winner.
- `src/evals/assessment/retrieval_eval.py:graded_ndcg_at_k` documents legacy keyword/source diagnostic scoring. Reviewed evidence qrels and evidence_ndcg_at_k are distinct; never pool them under an undifferentiated nDCG label.
- `_review_manifest_authority_status_from_parts` distinguishes content-hash consistency from reviewer authentication. The local manifest was inventoried, not freshly validated by this design pass.

### The local 57-query archived report
Source: `experiments/outputs/medical_semantic_chunking_exp_report.json`, timestamp 2026-04-18T03:11:29.595480Z.
All four variants' metrics.status are degraded; none of their referenced per-case run directories exist locally.

| Variant | nDCG@5 (report label) | p50 retrieval ms | Measured / expected metric slots | Failed |
|---|---:|---:|---:|---:|
| baseline | 0.6596 | 494 | 268 / 342 | 74 |
| medical_chunking | 0.6596 | 231 | 305 / 342 | 37 |
| query_understanding | 0.7009 | 226 | 318 / 342 | 24 |
| both_features | 0.7009 | 225 | 317 / 342 | 25 |

Baseline metric rows (each expects 57 slots): factual_accuracy mean .9964912281 / count 57 / errors 0; completeness .7087719298 / 57 / 0; clinical_relevance .9771929825 / 57 / 0; clarity .9192982456 / 57 / 0; answer_relevancy .8594487734 / 25 / 32; faithfulness .9798534799 / 15 / 42. Successful counts total 268, failed counts total 74, expected slots 6×57=342.
These are archived model-judged metrics, not clinical validation. High means on incomplete subsets cannot justify “better answers.”
The report names query_understanding a winner and target met=true; new designs quote the archived numerical change but do not certify that old winner under current contracts.

### Dataset inventory and overlap
| File / artifact | Verified records | Split / distinction |
|---|---:|---|
| golden_queries.json | 21 questions | regression 7 / test 6 / dev 8 |
| golden_queries_comprehensive.json | 35 questions | regression 9 / test 17 / dev 9 |
| golden_queries_diverse.json | 20 questions | regression 9 / test 8 / dev 3 |
| golden_queries_expanded.json | 54 questions | regression 15 / test 22 / dev 17 |
| golden_queries_all.json | 57 questions | regression 17 / test 23 / dev 17; 43 high / 14 medium labels |
| golden_conversations.json | 15 conversations, 30 stored turns | 6 regression / 5 test / 4 dev conversations |
| data/evals/review/dataset.json | 8 cases | 7 answerable / 1 unanswerable |
| data/evals/review/manifest.json | 8 case declarations | All human_reviewed by assertion; identity not authenticated |
| data/evals/review/corpus.json | 2,473 documents/chunks / 60 sources | Distinct from the number of review cases |

All 54 exact question strings in the expanded file occur in the current 57-query file. This checks text overlap, not historical byte identity or equal labels. Near-duplicate overlap was not assessed by this audit.
The all-query file has 45 anchor / 7 adversarial / 5 paraphrase cases. Raw rows have no review_status; `dataset_builder._normalize_case_record` defaults it to unreviewed. label_confidence=high does not establish human review or clinical authority.
`dataset_builder._dataset_diagnostics` has exact/source-family overlap checks and near-duplicate not_assessed reporting; inspect that output rather than claiming split independence.

### Feature inventory and API gaps
Six YAML files exist: one legacy-shaped top-level medical semantic config and five v1 configs. Declared variant array sizes: medical semantic 3; baseline 3; baseline_expanded_768dim 4; comprehensive_ablation 25; chunking_strategies 10; extraction_strategies 14. They are not executed-run counts.
Only one *_report.json exists in experiments/outputs locally. The top-level legacy YAML stem medical_semantic_exp differs from the report's medical_semantic_chunking_exp stem: `list_experiments.has_results` and result-by-config lookup use exact filename stems, so they will not automatically associate that report. The old report config also uses a different schema; generic normalized defaults are not proof of its effective settings.
No dedicated datasets/catalog or case-comparison API exists. New read-only adapters must preserve file identity and prevent arbitrary path traversal.
No active Logfire URL is established here. Keep primary detailed tracing in the approved existing tool; link out only when an authorized recorded URL is present.

## Reuse, problems and opportunities
Retain cookie-aware API helpers, error normalization, safe URL/Markdown behavior, Svelte route infrastructure, lazy imports, Chart.js, evaluation export/drilldowns and keyboard-aware TabNav.
Replace the empty chat-first blank canvas, always-prominent pipeline panel, unrelated shared navigation, cryptic source filenames and percentage diagnostic bars.
Improve focus management, textarea labels, status announcements, source-tab semantics and mobile evidence inspection. Preserve technical detail as a deliberate drilldown rather than deleting it.

## Execution and unknowns
- Started existing Vite app locally; HTTP 200 and Chromium screenshot of current landing confirmed navigation, empty chat and composer. Backend /health on port 8000 was unreachable; no live generated answer was requested.
- `npm --prefix frontend run check`: 0 errors, 0 warnings.
- Playwright tests under `frontend/tests/` include chat, pipeline, markdown, metrics and comparability suites; many API responses are mocked. They do not prove live medical answer correctness.
- No production build, full test suite, clinical validation, authenticated deployment, live ingestion or provider latency measurement was performed.
- Source freshness, frozen/intermediate lineage, publishing permissions, intended deployment auth and durable trace retention remain planning gates.
