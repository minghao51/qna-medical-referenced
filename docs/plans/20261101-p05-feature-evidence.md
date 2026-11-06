# P05 — Feature evidence and historical ablation labels

**Status:** implemented offline; review/acceptance pending. No deployment, live/paid provider call, hosted export, data/index mutation or default-profile change was performed.

## Scope delivered

1. **New `/research/features`** — read-only archived feature evidence for the 57-query report. It fetches the report by explicit ID, normalizes the legacy shape and builds declared-variant rows.
2. **Variant matrix** — baseline, medical chunking, query understanding and both-features rows with declared chunking/query-understanding settings, nDCG@5, absolute delta and separate relative percentage, and measurement state. Selection is labelled **Inspecting**, never winner.
3. **Reported change** — `query_understanding` shows `+0.0413` score points and `+6.3%` relative separately. `medical_chunking` shows `0.0000`. The archived winner is displayed only as a historical field with an explicit non-eligibility note; no promotion control exists.
4. **Degraded measurement** — all four variants' degraded answer-measurement state is disclosed; retrieval ranking is not presented as complete answer quality.
5. **Inspection panel** — declared chunking/query-understanding settings, observed nDCG and coverage state, plus explicitly **unverified** effective runtime settings and index binding. No live toggles or run controls.
6. **Capability map** — query understanding, medical semantic chunking, cross-encoder reranking and HyDE/HyPE/enrichment, each with implementation reference, archived evidence scope and limitation. The 54-query reranking study is shown separately with its own table, source note and no pooling with the 57-query report.
7. **Legacy ablation labels** — `Latest Feature Benchmark` → `Archived feature benchmark` dated 2026-04-18; `Optimal` → `Archived top variant`; no “latest” or promotion wording remains on that panel.
8. **Error/selection states** — unauthorized, missing requested report (no fallback), unsupported schema and late-response guard.

## Files changed

| File | Change |
|---|---|
| `frontend/src/routes/research/features/+page.svelte` | New feature evidence page, declared/observed/effective separation, 54-query study, capability map |
| `frontend/src/lib/components/FeatureEvidence.svelte` | Accessible declared-variant/result matrix with selection |
| `frontend/src/routes/eval/ablation/+page.svelte` | Archived wording; removed “latest/optimal” promotion labels |
| `frontend/src/lib/components/ResearchNav.svelte`, `AppNav.svelte` | Features points to `/research/features` |
| `frontend/src/routes/+page.svelte` | Features pathway points to the new route |
| `frontend/src/routes/research/evaluations/+page.svelte`, `methodology/+page.svelte` | Cross-links updated |
| `frontend/tests/feature-evidence.spec.ts` | 4 tests |
| `frontend/tests/research-workspace.spec.ts` | Features destination updated |

No backend/provider/default/lockfile/data change.

## Tests run

| Command | Result |
|---|---|
| `npm --prefix frontend run check` | 0 errors, 0 warnings |
| `npm --prefix frontend run build` | passed |
| `npm --prefix frontend run test -- tests/feature-evidence.spec.ts` | **4 passed** |
| Full suite at this slice | **75 passed, 9 skipped, 2 known inherited failures** |

The known failures remain the old confidence wording and intermittent New Chat locator; untouched.

## Residual risks / pending work

- Effective runtime settings and index binding remain unverified by design; the archive declares configuration only.
- The archived winner is not re-evaluated; no cohort, confidence interval or per-case win/loss analysis exists.
- The 54-query study is a curated static projection from `docs/feature_ablation_findings.md`, not a live API.
- Dataset identity/case linkage remains P06.

## Rollback

Remove the new feature page/component/test, restore `/experiments`-based links if desired, and revert the ablation label text. No data/backend rollback.

## Next

P06 dataset catalog UI/cases (implemented next in this pass), then P08 and P09.
