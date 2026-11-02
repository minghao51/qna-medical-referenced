# P06 — Dataset catalog UI and revision-bound case inspector

**Status:** implemented offline; review/acceptance pending. No deployment, live/paid provider call, hosted export, data/index mutation or public rollout was performed.

## Scope delivered

1. **Frontend catalog contract** — additive `types.ts` DTOs and `api.ts` calls for `/research-data/datasets`, detail and cases. No new client/state framework.
2. **New `/research/datasets`** — renders the nine fixed catalog entries with independent availability, units, splits, turns, review state and first-page overlap. Missing/malformed/unsupported entries keep their actual state and do not erase others.
3. **Overlap** — exact stored query-text overlap (All57 ↔ Expanded54) with both current revisions, normalization and near-duplicate status. Explicitly not independence, label identity or historical bytes.
4. **Review set** — 8 frozen cases, answerability split, manifest-declared review status and authority caveat; reviewer IDs and frozen bodies remain unexposed.
5. **Reference/index entries** — CSV row count is separated from served chunk totals; D11 index is an inventory reference linked to `/documents`, never a fixed 2,473 count.
6. **New `/research/datasets/[datasetId]`** — deep-linked allowlisted ID, current revision, split bars, confidence counts, raw review absence, overlap and availability states.
7. **Revision-bound cases** — case rows are requested only for `case_projection=available`, with the current byte revision. Case ordinals are scoped to that revision; `?case=` is validated and updates only the selected ordinal.
8. **Case inspector** — real LDL-C fixture expectations (question, expected source label, lexical terms, split/difficulty/category/family/topic/confidence, raw review status absent). Conversation fixtures render minimal stored turns. Ordinal locator and revision are shown.
9. **Observed panel** — explicitly unavailable: `historical_binding=not_established`, `reason=case_records_unavailable`. No latest run, ordinal/text join, fabricated ranks, judge reasons or failures.
10. **Revision change** — `409 catalog_revision_changed` invalidates selection and shows an explicit refresh action; refresh re-reads the entry revision and cases. No automatic stale-data join.
11. **Navigation** — Research subnav and disclosure now include Datasets; root third pathway points to the catalog.

## Files changed

| File | Change |
|---|---|
| `frontend/src/routes/research/datasets/+page.svelte` | Catalog list, availability, overlap and review context |
| `frontend/src/routes/research/datasets/[datasetId]/+page.svelte` | Deep-linked entry, revision-bound cases, expected vs observed |
| `frontend/src/lib/components/DatasetDetail.svelte` | Current-file inventory, splits, labels/review, overlap and inventory states |
| `frontend/src/lib/types.ts` | Additive catalog/overlap/case DTOs |
| `frontend/src/lib/utils/api.ts` | Catalog list/detail/cases calls |
| `frontend/src/lib/components/ResearchNav.svelte`, `AppNav.svelte` | Datasets destination |
| `frontend/src/routes/+page.svelte` | Datasets pathway |
| `frontend/tests/dataset-catalog.spec.ts` | 6 tests: catalog/overlap, detail/case, ordinal URL, summary-only, revision change, unknown ID |

No backend change (P02 provided the API); no provider/default/lockfile/data change.

## Tests run

| Command | Result |
|---|---|
| `npm --prefix frontend run check` | 0 errors, 0 warnings |
| `npm --prefix frontend run build` | passed |
| `npm --prefix frontend run test -- tests/dataset-catalog.spec.ts` | **6 passed** |
| Full suite after P05/P06 | **82 passed, 9 skipped, 1 failed** |

The remaining failure is the inherited old “Overall Confidence” expectation in `pipeline.spec.ts:249`; the intermittent New Chat test passed in the latest run. Both remain P09/owner test debt.

Playwright used the existing `/tmp/qna-browser-libs` `LD_LIBRARY_PATH` workaround.

## Backward compatibility

- Existing `/documents`, `/experiments`, `/eval*` routes remain unchanged.
- Catalog APIs are the additive P02 endpoints; no existing DTO was repurposed.
- Dataset/open-run binding remains unestablished by design; no comparison behavior changed.
- The dataset list/detail pages are read-only; no data is written and no index client is opened.

## Residual risks / pending work

- Observed per-case results remain unavailable until a separately specified stable binding exists. The UI intentionally shows the gap.
- The catalog is a current-file projection; it is not historical dataset identity for an archived report.
- D11 chunk totals are shown through the existing Evidence/documents surface, not duplicated in the catalog.
- No public/anonymous access; the private boundary is unchanged.
- P08 evidence facets/detail, P09 Q&A inspector/SSE and P10 readiness remain.

## Rollback

Remove the two dataset routes, `DatasetDetail.svelte`, the additive catalog DTO/API additions, nav/root links and the dataset test. The P02 backend stays usable independently. No data/index migration is required.

## Next

P08 evidence facets and source detail, then P09 Q&A turn refinement, then P10 readiness.
