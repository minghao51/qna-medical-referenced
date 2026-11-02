# Implementation map — files, ownership and evidence

**Status:** **P01–P10 are implemented offline** in the shared working tree. The tables below preserve the planned ownership map; where a row still says planned/`new`, treat it as implemented in the current tree and verify against the per-slice report. Start with [P10 readiness](../../docs/plans/20261101-p10-readiness.md), [continuation handoff](continuation-handoff.md) and the [deployment pickup brief](../../docs/plans/20261101-deployment-pickup.md).

### Implemented offline

The reports and actual working tree are the source of truth: P01 archive/metric/auth; P02 catalog/packaging; P03 shell/workspace/`/ask`; P04 evaluations/methodology; P05 features; P06 datasets/cases; P07 selected-run safety; P08 evidence facets/detail; P09 turn/SSE inspector; P10 readiness. The deploy stack/G-AUTH artifacts are staged but not executed.

Companion documents: [normative specification](implementation-specification.md), [task plan](implementation-plan.md), [next-agent entry](next-agent-start.md). Task IDs P00–P10 are defined in the plan.

## 1. Workstream and dependency map

```text
P00  revalidation / auth + packaging decisions / baseline
 ├─ P01  archive identity + metric view models ──────┐
 ├─ P02  authenticated read-only dataset catalog ─┐ │
 ├─ P07  run-scoped record safety ────────────────┼─┼──────────┐
 └──────────────────────────────────────────────┼─┼─ P03 shell + /ask move
                                                │ │   ├─ P04 evaluations
                                                │ ├───┼─ P05 feature evidence
                                                └─────┼─ P06 datasets + cases
                                                      ├─ P08 evidence facets/detail
                                                      └─ P09 Q&A turn refinement
P10  full offline integration / private auth + packaging / accessibility / release gate
```

The diagram shows data dependencies, not permission to edit shared files concurrently. Shared frontend contracts/shell and factory integration have a single owner. No production release while auth delivery is unresolved.

## 2. Backend / artifact map

| Path | Current evidence / planned change | Status | Task / exclusive owner |
|---|---|---|---|
| `src/app/routes/experiments.py` | **P01 implemented:** authenticated-state guard (401), canonical roots, bounded report/config reads, digests/schema/association; raw roots retained | Implemented | P01 backend |
| `src/app/schemas/research.py` | Typed new catalog response boundary only; no broad schema migration | New | P02 backend |
| `src/evals/research_catalog.py` | Fixed allowlist, bounded summaries, revision-aware case projections and exact overlap; no provider/ingestion imports | New | P02 backend |
| `src/app/routes/research.py` | GET `/research-data/datasets`, detail and cases; explicit existing authenticated-state requirement | New | P02 backend |
| `src/app/routes/__init__.py` | Export new router only if required by current import convention | Modify if needed | Integration owner / P02 |
| `src/app/factory.py` | Include new router; preserve lifespan, dependency ownership and middleware order | Minimal modify | Integration owner / P02 |
| `src/evals/artifact_service.py` | Preserve comparability guards; add confined explicit-run selection for currently latest-only records/steps and bounded record reads | Modify | P07 backend |
| `src/app/routes/evaluation.py` | Add optional `run_dir` to existing record/step reads; validate identifiers, echo actual selected run, retain latest defaults | Modify | P07 backend |
| `src/ingestion/indexing/listing.py` | Add global facets and optional source labels/URL from existing metadata, retain filtered counts | Modify | P08 backend |
| `src/app/routes/documents.py` | Forward additive facets/labels/verified identity fields without changing existing inputs | Modify | P08 backend |
| `Dockerfile` | Explicitly package only six owner-approved fixture JSON files; no whole-tests COPY and no dependency changes | Modify after packaging approval | P02/P10 integration |
| `docs/20260424-openapi-swagger.yaml` | Add/adjust only implemented contracts; keep manual schema truthful until a separate generation guard is approved | Modify | Integration owner after P01/P02/P07/P08 |
| `docs/testing/playwright.md` | Correct configured4173 default; document new route/spec selection and offline mocks | Modify | P10 integration |
| `docs/local-workflows.md` | Add read-only private-lab UI workflow/fixture availability notes if needed | Modify only relevant section | P10 integration |

**Do not change by default:** `src/rag/*`, `src/usecases/chat.py`, provider SDK clients, evaluator computation/winner rules, configuration defaults, ingestion steps, frozen corpus or lockfiles. A newly discovered defect there needs a separate bounded proposal.

## 3. Frontend data / state / component map

| Path | Planned responsibility | Status | Owner |
|---|---|---|---|
| `frontend/src/lib/types.ts` | Add discriminated archive/run selection, catalog DTOs, nullable metric coverage and optional additive provenance/facet fields; retain existing shapes | Modify | Integration owner across P01/P02/P07/P08/P09 |
| `frontend/src/lib/utils/api.ts` | Add catalog calls; optional scoped record parameters; structured status-safe handling; preserve cookie/base/error behavior | Modify | Integration owner across contracts |
| `frontend/src/lib/utils/research.ts` | Known archive shape adaptation and explicit report/config association only; consume shared finite/count/delta logic from eval.ts/metric definitions | New | P01 frontend |
| `frontend/src/lib/utils/metric-definitions.ts` | Reuse/extend definitions with units, direction and separate legacy/evidence semantics | Modify narrowly | P01 frontend |
| `frontend/src/lib/utils/eval.ts` | Own shared finite/count/coverage validation and unit-aware delta/format behavior; preserve selection/legacy callers; no duplicate logic in research.ts | Modify if needed | P01/P07 integration |
| `frontend/src/lib/utils/export.ts` | Preserve exports; include displayed scope/denominators/provenance where relevant; no automatic hosted export | Modify only if new export offered | P10 integration |
| `frontend/src/routes/+layout.svelte` | Tokens, legacy variable aliases, semantic defaults; per-layout chat state context only when P09 needs it | Modify | P03 then P09 integration |
| `frontend/src/lib/components/AppShell.svelte` | Shared width/margins/skip landmark; avoid nested main landmarks with existing pages | Modify | P03 frontend |
| `frontend/src/lib/components/AppNav.svelte` | Research-first top nav, mobile disclosure and retained diagnostic destinations | Modify | P03 frontend |
| `frontend/src/lib/components/ResearchNav.svelte` | Small reusable research subnavigation with active route semantics | New | P03 frontend |
| `frontend/src/lib/components/MeasurementCoverage.svelte` | Accessible mean/count/error/expected rows and mobile equivalent; no generic KPI engine | New | P04 frontend |
| `frontend/src/lib/components/FeatureEvidence.svelte` | Declared settings + archived result matrix and capability evidence/limitations | New | P05 frontend |
| `frontend/src/lib/components/DatasetDetail.svelte` | Selected current revision, splits, labels/review, overlap and expected-case panel | New | P06 frontend |
| `frontend/src/lib/chat-state.svelte.ts` | Optional small per-layout factory/context state for current in-memory conversation; **no module-global user singleton**, persistent store or SSR cross-user sharing | New only when needed | P09 frontend |
| `frontend/src/lib/utils/sse.ts` | Small current-contract buffered SSE decoder with terminal-state validation; no retry/reconnect framework | New | P09 frontend |
| `frontend/src/lib/components/PipelinePanel.svelte` | Refactor into selected-turn stage/step inspector; preserve every recorded field on demand | Modify | P09 frontend |
| `frontend/src/lib/components/DocumentInspector.svelte` | Reuse chunk inspection; repair dialog focus/labels and safe provenance | Modify | P08 then P09 integration |
| `frontend/src/lib/components/EmptyState.svelte`, `LoadingSkeleton.svelte`, `TabNav.svelte`, `MetricChart.svelte` | Reuse; repair only needed accessibility/tokens | Reuse / targeted modify | Integration owner |

Do not create a component for every conceptual label in the handoff. Page-local markup is acceptable for one-off editorial notes/identity facts. New components above are proposed minimum reusable/stateful boundaries; merge when implementation evidence supports less code.

## 4. Browser route and screen map

| Path | Operation | SVG coverage | Task |
|---|---|---|---|
| `frontend/src/routes/+page.svelte` | Replace with private research workspace after chat relocation | 01/04 | P03 |
| `frontend/src/routes/ask/+page.svelte` | Move existing chat intact first, then refine | 08/09/10/12 | P03 → P09 |
| `frontend/src/routes/research/+page.server.ts` | New redirect to `/`, no duplicate workspace | 07 | P03 |
| `frontend/src/routes/research/evaluations/+page.svelte` | New archive/current-run selection, coverage/identity/gate, link to legacy diagnostics | 13/17/18 | P04 |
| `frontend/src/routes/research/features/+page.svelte` | New configured-feature/observed evidence workspace | 14 | P05 |
| `frontend/src/routes/research/datasets/+page.svelte` | New catalog selection | 15 | P06 |
| `frontend/src/routes/research/datasets/[datasetId]/+page.svelte` | New deep-linked selected revision and fixture-case inspector | 15/16 | P06 |
| `frontend/src/routes/research/methodology/+page.svelte` | New concise definitions/provenance page linking existing docs/help | 07/18 + written spec | P04 |
| `frontend/src/routes/evidence/+page.svelte` | Move/adapt existing documents list, corrected facets and labels | 02/05 | P08 |
| `frontend/src/routes/evidence/[id]/+page.svelte` | New full chunk excerpt/provenance route | 03 | P08 |
| `frontend/src/routes/documents/+page.svelte` / new `documents/+page.server.ts` | Retire duplicate list page only after equivalent `/evidence` is complete; redirect preserves safe filter/page parameters | 02/05 | P08 |
| `frontend/src/routes/eval/+page.svelte` | Retain diagnostics and exports; selected-run drilldown fixes | Legacy capabilities + 18 | P07 |
| `frontend/src/lib/components/QualityTab.svelte` | Reuse coverage presentation where schema supports it; no lost quality checks | 13/17 semantics | P04/P07 integration |
| `frontend/src/lib/components/RetrievalTab.svelte` | Preserve metric groups; keep legacy/evidence semantics separate | Written spec | P07 integration |
| `frontend/src/lib/components/TrendingTab.svelte` | Keep non-comparability notice and null averages; no trend chart resurrection | 18 | P07 |
| `frontend/src/routes/experiments/+page.svelte` | Correct missing-as-zero, delta direction and legacy winner labels; retain config/report exploration | 14 semantics | P01/P05 integration |
| `frontend/src/routes/eval/ablation/+page.svelte` | Keep functionality, label hardcoded findings dated archives rather than live/latest/eligible winner | 11/14/18 | P05 |
| Health/settings/help/pipeline routes | Keep reachable; no settings editor or source-date inference | 06/07 | P03/P10 |

Routes that rely on datasets unavailable in an image show an honest missing state. Route existence never authorizes content or substitutes a fabricated fixture.

## 5. Test map — existing anchors and planned additions

### Backend

| Path | Cases to retain / add | Status / task |
|---|---|---|
| `tests/unit/app/test_evaluation_routes.py` | Existing58-test baseline group includes this file; add explicit-run selection/auth/error assertions | Existing; P07 |
| `tests/unit/evals/test_history_comparability.py` | Preserve comparable=false/null averages, non-finite/boolean sanitization and diagnostic metadata | Existing; P01/P07 regression |
| `tests/unit/app/test_new_routes.py` | Existing documents/experiments routes; add report metadata and facet backward compatibility | Existing; P01/P08 |
| `tests/unit/evals/test_research_catalog.py` | Fixed allowlist, current byte revision, missing/malformed/oversized entries, overlap, units, no reviewer export, case-revision409 | New; P02 |
| `tests/unit/app/test_research_routes.py` | Authenticated GET catalog/list/detail/cases; validation, errors, no path input, independent availability | New; P02 |
| `tests/unit/evals/test_run_scoped_records.py` | Explicit run vs latest, traversal/symlinks, bounded JSONL, no fallback, actual run echoed | New; P07 |
| `tests/unit/ingestion/test_document_listing.py` | Global vs filtered counts, missing/unknown metadata and optional label fields | New; P08 |
| `tests/integration/app/test_app_security.py` | New catalog unauthorized denied; protect existing cookie/auth/CORS/rate behavior; no real provider construction | Existing; P02/P10 |
| `tests/integration/ingestion/test_chroma_search.py` | Retain list paging behavior, additive facet/label parity using fake embeddings and tmp store | Existing; P08 |
| `tests/unit/evals/test_dataset_builder.py`, `test_review_manifest_authentication.py` | Preserve normalization/review authority semantics; no new catalog should mutate these rules | Existing regression; P02/P06 |

All new test files use temporary roots/fixtures. Tests never regenerate or write repository `data/`; do not disable its guard to clear failures. Prefer patchable explicit module constants/paths, not production config framework additions solely for tests.

### Frontend

| Path | Cases | Status / task |
|---|---|---|
| `frontend/tests/research-metrics.spec.ts` | Pure normalizer checks through current Playwright test runner: finite/null/count rules, legacy expectations, delta units/direction/zero baseline | New; P01 |
| `frontend/tests/research-workspace.spec.ts` | Private root, research/Q&A nav, missing/unauthorized partial data, keyboard/mobile | New; P03/P10 |
| `frontend/tests/evaluation-coverage.spec.ts` | Real archive projection268/74/342, six means/denominators, missing/unsupported state, selected artifact races | New; P04 |
| `frontend/tests/feature-evidence.spec.ts` | Declared config vs effective unknown, four degraded variants, no eligible-winner claim, real +.0413/+6.3% | New; P05 |
| `frontend/tests/dataset-catalog.spec.ts` | Actual units/splits/confidence/overlap, current revision invalidation, expected case, absent observed data, malicious IDs | New; P06 |
| `frontend/tests/evidence-browser.spec.ts` | Global facets with filtered results, original links, route aliases, unknown dates, focus restoration/mobile | New; P08 |
| `frontend/tests/chat.spec.ts`, `pipeline.spec.ts`, `markdown-rendering.spec.ts` | Move chat-specific root visits to `/ask`; preserve behavior/security, replace confidence expectations with recorded diagnostics | Existing; P03/P09 |
| `frontend/tests/helpers.ts` | Reuse request fixtures; add focused safe helpers only when reused | Existing; integration owner |
| `frontend/tests/history-comparability.spec.ts` | Preserve all existing non-comparability checks; add historical selection not reading latest | Existing; P07 |
| `frontend/tests/quality-metrics.spec.ts`, `visual-verification.spec.ts` | Keep diagnostics coverage; update only intentionally changed routing/semantics | Existing; P04/P10 |
| `frontend/tests/sse.spec.ts` | Pure decoder chunk boundaries/UTF-8/errors/terminal/EOF + browser partial-answer behavior as appropriate | New; P09 |

Browser tests for new screens deny unstubbed external/API traffic. No `API_URL` live backend opt-in for ordinary design acceptance. Do not add a unit-test dependency just to run pure helpers; the existing test runner can execute those checks.

## 6. Shared ownership and parallel execution rules

- Integrator owns `types.ts`, `api.ts`, shared shell/layout, route imports, factory wiring, test helpers, OpenAPI and documentation index changes. Workers must not independently edit those files.
- A bounded worker can own report route changes, catalog internals, run-scoped artifact internals or a leaf page/test pair **after** contract and integration deltas are assigned.
- P01 backend report work and P02 catalog internals can proceed independently; P07 artifact safety can run independently if its route integration is serialized.
- P04 coverage and P06 datasets can proceed in parallel only after shared DTO/API/nav contracts land. P05 consumes the agreed metric utility rather than inventing another formatter.
- P03 chat relocation lands before P09 chat redesign. P08 and P09 both touch DocumentInspector only serially or through integrator.
- Each task includes its code, tests, relevant documentation and a bounded review report. No destructive git cleanup, global resets or unrelated fixes.
- If delegating, verify integration/model IDs again and announce any unavailable request/fallback. Do not assume historical labels name available current models.

## 7. Explicit exclusions / future map

Not scheduled: new auth platform/BFF, verified cohort backend, provider-call event ledger, clinical tools, whole-index text search, patient data storage, durable chat trace persistence, new chart library or external font system. These require separate decisions/contracts and are not hidden prerequisites to claiming the first offline UI slices done.
