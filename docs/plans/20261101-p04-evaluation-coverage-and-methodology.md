# P04 — Coverage-first evaluations and methodology

**Status:** implemented offline; review/acceptance pending. No deployment, live/paid provider call, hosted export, data/index mutation or public rollout was performed.

**Approval reference:** continuation authority for P02–P10 plus approved G-ROUTES/G-AUTH shape. This slice implements the planned P04 contract; no backend or provider/default change.

## Scope delivered

1. **New `/research/evaluations`** — archive-first artifact selection by explicit report ID. It loads the report named in `?report=`, otherwise the known `medical_semantic_chunking_exp`, otherwise the first available report. A requested but unavailable/invalid ID shows a missing state and never falls back to another report. Late report responses are ignored via a request sequence.
2. **Coverage summary** — actual measured/expected metric slots, failed slots and error rate. The known archive renders **268 / 342**, **74 failed**, **21.6%**, with the explicit “metric slots, not patient cases” statement and the legacy one-slot-per-query expectation basis.
3. **Metric table** — six answer metrics with mean, measured/expected, failed/skipped, coverage state and an accessible coverage bar. Means are shown only from successful measurements; missing, invalid and inconsistent values stay explicit (`N/A`/state), never zero.
4. **Identity and provenance** — report ID, schema kind, exact-byte revision prefix, explicit config association, `historical_binding` and `comparable=false` in a native disclosure. Per-case run rows are stated as not exposed by the aggregate API; failures are not inferred.
5. **Comparison gate** — “Comparison not verified” with the current `comparable=false` rule, no trends, no compare action, no winner promotion. Links to legacy L0–L6 diagnostics, feature evidence and methodology.
6. **New `/research/methodology`** — static explanation of units (slots/queries/cases/chunks), coverage states, metric families/direction, archive revision vs historical dataset identity, comparison eligibility and recorded-vs-reconstructed Q&A evidence.
7. **Navigation** — Research subnav and Research disclosure now expose Evaluations (`/research/evaluations`) and Methodology (`/research/methodology`); Workspace and Features remain working; Datasets stays absent until P06.
8. **Workspace links** — the root coverage action and Evaluations pathway now target `/research/evaluations`.
9. **States** — loading (`aria-busy`), missing, unsupported schema, unauthorized and error are distinct; the legacy `/eval` route stays available for raw diagnostics.

## Files changed

| File | Change |
|---|---|
| `frontend/src/routes/research/evaluations/+page.svelte` | New archive selection, coverage summary, provenance, comparison gate and next actions |
| `frontend/src/routes/research/methodology/+page.svelte` | New static methodology page |
| `frontend/src/lib/components/MeasurementCoverage.svelte` | New accessible metric/coverage table with mobile stacked presentation |
| `frontend/src/lib/components/ResearchNav.svelte` | Add Evaluations/Methodology working destinations |
| `frontend/src/lib/components/AppNav.svelte` | Research disclosure destinations updated |
| `frontend/src/routes/+page.svelte` | Coverage/pathway links target the new evaluations route |
| `frontend/tests/evaluation-coverage.spec.ts` | Real-shaped coverage, explicit selection, missing/no-fallback, unsupported, stale response, unauthorized, methodology |
| `frontend/tests/research-workspace.spec.ts` | Expected Evaluations destination updated |

No backend, RAG, provider, evaluator/winner, data, index, dependency or lockfile change.

## Tests run

| Command | Result |
|---|---|
| `npm --prefix frontend run check` | **0 errors, 0 warnings** |
| `npm --prefix frontend run build` | **passed** |
| `npm --prefix frontend run test -- tests/evaluation-coverage.spec.ts` | **7 passed** |
| Full `npm --prefix frontend run test` | **71 passed, 9 skipped, 2 failed** |

The two failures remain the inherited chat/pipeline test debt: old “Overall Confidence” wording (`pipeline.spec.ts:249`) and the strict `.message` New Chat locator (`pipeline.spec.ts:562`). They are untouched and remain P09/owner review.

Playwright used the existing `/tmp/qna-browser-libs` `LD_LIBRARY_PATH` workaround because system NSS/NSPR libraries are absent.

## Visual/accessibility evidence

- Desktop summary + six-row metric table with measured/failed legend, definitions and denominators.
- Mobile (<760 px) table keeps table semantics but stacks each row with labelled values.
- Coverage bars carry text alternatives and never rely on colour alone; “Partial” is also textual.
- Native `<details>` provenance, labelled report selector, `aria-busy` loading, independent empty/error states.
- Methodology has a labelled section index, semantic headings and anchor links.

## Backward compatibility

- `/eval`, `/eval/ablation`, `/experiments`, `/help`, `/docs/pipeline` remain reachable and unchanged.
- Report API shape is unchanged; the page consumes the additive `_artifact` provenance from P01.
- `comparable=false` and null cross-run aggregates are preserved; no trend/winner control was added.
- No catalog/run-scoped endpoint changes in this slice.

## Residual risks / pending work

- Current live-run selection is not embedded in the research page; a “Current runs” link keeps legacy `/eval` as the run inspection surface. Full discriminated archive/run selection can be revisited when P07 run-scoped UI is integrated.
- Dataset expectations and observed-case panels remain unavailable until P06; no ordinal/text joins were added.
- Feature matrix remains `/experiments` until P05.
- The known archive still lacks per-case rows; the page states this rather than fabricating failures or judge reasons.
- Inherited full-suite failures remain.

## Rollback

Remove the two new research routes and `MeasurementCoverage.svelte`, revert the two nav link changes, and restore the root workspace links/tests. No data, backend, index or migration rollback is needed.

## Next proposed slice

**P05 — feature evidence**, followed by **P06 — dataset catalog UI/cases**. P05 reuses this metric component/utilities and the P01 delta semantics; P06 consumes the P02 catalog API. P08 then P09, then P10 readiness.
