# Screen → data → capability map
All visual layouts are proposals. “Existing” below describes underlying data/functionality, not an already implemented screen.

## Shared sources
- API base/cookies/errors: `frontend/src/lib/utils/api.ts`; safe source links: `frontend/src/lib/utils/url.ts`.
- Runtime trace types: `src/rag/trace_models.py`; frontend equivalents: `frontend/src/lib/types.ts`.
- Chunk APIs: `src/app/routes/documents.py`; list/detail shaping: `src/ingestion/indexing/listing.py`.
- D11 local counts: read-only SQLite metadata grouping. Do not hardcode these counts into production.

| Screen / component | Existing input and transformation | Missing / proposed work |
|---|---|---|
| 00 tokens and controls | Current layout CSS/component inventory | New CSS tokens; native form, disclosure, dialog semantics; no backend needed |
| 01 / 04 research entry | Local 57-query report baseline faithfulness mean/count/errors; dedicated /ask workbench link | Import archived report through a read-only adapter; do not present it as /evaluation/latest |
| 01 corpus bars | /documents source_type_counts and total; D11 local values 1306/597/460/110 | Stable unfiltered facet contract and explicit index identity; current API has no verified freshness timestamp |
| 01 inventory note | D11 corpus + golden query/conversation fixtures + frozen 8-case review set | New dataset catalog adapter; counts have distinct units and are not summed |
| 01 research pathways | Existing evaluation/experiment inspection plus local fixture metadata | First-class Features and Datasets routes are proposed |
| 02 / 05 facets | GET /documents?source_type=pdf&limit=50&offset=0 | Current counts are filtered along with results; add global_source_type_counts rather than silently changing meaning |
| 02 text search / sorting | Neither full-text q nor stable sort parameter exists on list API | Clearly proposed; implement server-wide query + stable ordering before enabling. Do not search only loaded page |
| 02 selected rows | Real D11 chunk indices 0/1/2 of ace_diabetes_insulin_2024 | Rows intentionally grouped for illustration, not actual first page order; human title/labels need metadata enrichment in list response |
| 03 detail | GET /documents/{id} → content + metadata; actual chunk 1, page 1, quality_score 1.0 | New route; title mapping; source URL extracted from detail metadata; no inferred source update date |
| 06 pending/error/empty | Existing health readiness, status codes, SSE terminal error and request ID | Shared state model; rate-limit and auth handling; never treat unauthorized as empty |
| 06 no results | Type-filter empty results today | Text-search no-results only after proposed search ships |
| 07 navigation | Existing nine routes | /ask, /evidence, /research information architecture + aliases; role gating depends on deployment auth |
| 08 conversation | GET/DELETE /history; POST /chat?include_pipeline=true; role/content/timestamp | In-memory pairing of user+answer into turn summaries; explicit completed/incomplete states; confirm destructive clearing |
| 08 source entries | Terminal ChatSource list, canonical/display label, URL, page | No publication-count assumption; no verified per-sentence citation entailment; bracket positions shown are synthetic |
| 09 durations | pipeline.retrieval.timing_ms, generation.timing_ms, total_time_ms | Label as recorded durations, not a waterfall; context time absent. Additive current-session layout only |
| 09 ranked evidence | retrieval.documents[].content/id/rank/page + optional raw scores/ranks/provenance | Show optional fields as not recorded; no common score scale guaranteed; do not recompute combined_score from visual bars |
| 09 context | total_chunks / total_chars / sources / preview | Preview is 200 chars + ellipsis, not full context or prompt. Distinct file count may be derived from returned sources, labelled accordingly |
| 09 model | generation.model / timing_ms / tokens_estimate | Example model is synthetic. Token estimate is not exact usage and current runtime supplies None |
| 10 mobile drilldown | Same current-session trace as 09 | Full-screen sheet / focus restoration; no permanent share URL promised |
| 11 comparison bars | Reported 54-query reranking table in docs/feature_ablation_findings.md | Original bundle unavailable locally: publish as reported archive only, or revalidate before any “latest” label |
| 12 step record | retrieval.steps[] → name/timing_ms/skipped/details | Raw typed key-value renderer; related query and results labelled as parent context, not raw individual-call request/output |
| 12 future call ledger | No current provider request/result event API | Separate proposal: privacy-reviewed per-call instrumentation; schema/version/access/retention/export decisions required |

## Research refinement screens
| Screen / component | Existing evidence | Missing / proposed work |
|---|---|---|
| 01 / 04 coverage story | Actual baseline.metrics.faithfulness mean/count/error_count from 57-query archived report | Read-only archived report import; root is private workspace, not public composer |
| 13 / 17 per-metric coverage | Local report baseline.metrics: six means, counts, error_count; expected 57 each | Adapter from archived report, separate from newer run-summary/L6 schema; no patient case count inference |
| 13 measurement slots | 268 successes + 74 failures = 342 = 6×57 | Preserve score denominator and declared expected count; do not fabricate skipped/errored details absent in old artifact |
| 14 variant matrix | config.baseline/config.variants and report baseline/variants metrics | Declared config only; effective settings/index provenance unavailable from missing run dirs; no live toggles |
| 14 capability map | production_profile.py; query understanding/chunking code; optional reranker; dated 54-query note | No automatic feature promotion; distinguish configured/implemented/executed/measured/effective |
| 15 catalog | Actual fixture files, review dataset/manifest/corpus and public LabQAR CSV | New allowlisted read-only catalog service or build-time extraction; not a fictitious existing endpoint |
| 15 split bars | golden_queries_all.json: regression17/test23/dev17 | Units=questions, max chart domain25; do not imply held-out independence |
| 15 overlap warning | Exact current query-string intersection expanded/all=54 | Not historical dataset identity, near-duplicate analysis or label equivalence |
| 16 expected panel | First all-query fixture: question, expected_keywords, expected_sources, split/category/family/confidence | Typed case adapter; raw fixture lacks stable query ID; do not treat row number as durable identity |
| 16 observed panel | Underlying archived per-case dirs absent; aggregate report remains available | Explicit unavailable state. Existing latest-only records endpoints must not service a selected historical case |
| 18 comparison gate | EvaluationService forces comparable=false and null cross-run averages | Future verified cohort contract required; dataset/index/label/measurement checks cannot be merely frontend heuristics |

## Real archived fixture values for refinement
Screens 01, 04, 13 and 17 use the same baseline metrics from experiments/outputs/medical_semantic_chunking_exp_report.json, not the synthetic chat fixture.
57 questions × 6 metrics = 342 expected slots; 268 successful + 74 failed. Faithfulness mean .9798534799 on 15 successful measurements (42 failed); answer relevancy .8594487734 on 25 (32 failed); other four metrics each 57 successful.
Screen14 uses nDCG .6596215032 → .7008913797; exact delta .0412698765, displayed +.0413 and relative +6.3%. The four reported values are descriptive, not a verified cohort.
Legacy numeric fields are retained as archived diagnostics; reviewed-evidence metrics use separate definitions and eligibility.

## Fixture constants (not production data)
Screens 08–10 and 12 share synthetic turn 02:
- Query: “What should I ask at my next appointment?”
- 2 chunks, 2 source entries, 1 distinct source file; context 900 characters.
- total 1,800 ms; retrieval 300 ms; generation 1,400 ms.
- query_expansion 20 ms; semantic_search 200 ms; keyword_search and score_fusion 0 placeholders; reranking skipped.
- Rank 1: chunk 1, semantic .72, keyword .25, source prior .90, combined .66, quality 1.0; ranks semantic 1 / BM25 2 / fused 1.
- Rank 2: adjacent chunk 0; combined .61 (screen 12 only).
- Source boost, fused score, exact tokens and TTFT not recorded.
- “example-model” is an explicit synthetic identifier. No medical or benchmark conclusion follows from this fixture.

Arithmetic residual: 1,800 − 300 − 1,400 = 100 ms. This is not attributed context duration; intervals may not partition execution. Current semantic_search timing wraps retrieval work; keyword/fusion zero values are placeholders, not measured zero-cost operations.

## Contract proposals
Minimal additive fields, subject to a planning agent's verification:
1. Document list: retain total/items/source_type_counts/index_metadata; add unfiltered facets plus public-safe index identity; enrich rows with canonical/display label and URL where available.
2. Optional search: q/source_type/limit/offset and a documented deterministic order + tie-breaker. Define totals/facets under q explicitly and test whole-index behavior.
3. Public-safe provenance: publication date nullable, ingested_at nullable, index_built_at nullable, lineage ID if verified. Never synthesize these from local filesystem mtime.
4. Turn inspector phase 1: ephemeral frontend turn key, response, sources, optional trace, terminal status and safe request ID. No backend history schema change needed.
5. Durable trace phase 2 (not required): fresh random turn IDs, versioned minimized records, authorization, TTL/delete and redaction. Do not persist raw prompts/provider bodies or sensitive documents by default.
6. Full per-provider-call timeline: deferred. Need genuine start/end and parent IDs; never manufacture call trees by splitting stage labels.
