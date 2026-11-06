# P08 — Evidence facets, `/evidence` browser and source detail

**Status:** implemented offline; review/acceptance pending. No deployment, live/paid provider call, hosted export, data/index mutation or public rollout was performed.

## Scope delivered

### Backend (additive)

1. `DocumentListingMixin` now returns `global_source_type_counts` computed from the full in-memory metadata mirror, independent of the selected `source_type`.
2. Existing `source_type_counts` retain their filtered semantics; selected `total` remains the filtered count.
3. Listing items expose only present `canonical_label`, `display_label`, `logical_name`, `source_url` and `domain`. The URL is passed through `sanitize_external_url`; unsafe schemes are null.
4. `index_identity` exposes only a valid 64-hex `source_snapshot_sha256` from existing collection metadata; otherwise null. A directory name or “D11” label is never treated as a fingerprint.
5. `/documents/{id}` adds the same safe label/URL/domain/type/class/page fields without removing the existing content/metadata shape.

### Frontend

1. **New `/evidence`** replaces the duplicate document list. It shows global facets (`All 2,473; PDF 1,306; HTML 597; reference 460; Markdown 110` for the inspected fixture) while result totals remain filtered.
2. Filter and offset are encoded in `source_type`/`offset`; browser Back restores the previous view via `popstate`.
3. Table shows readable source label + file, PDF page only for PDFs, type/class, length, excerpt and an exact-ID Inspect link. HTML/Markdown `page=1` is not presented as a print page.
4. Unknown/missing dates stay absent; no mtime-derived date is displayed.
5. **New `/evidence/[id]`** shows the indexed chunk excerpt, safe original link, type/class/domain, length, logical name, PDF page only where valid, and the exact store ID.
6. Unsafe/absent original URLs show “Original link unavailable”; the local source path is not turned into an external link.
7. Missing chunk IDs show a “not found” state and are not reconstructed from source/page values. File modification time is never used as a freshness date.
8. `/documents` becomes a 308 alias to `/evidence`, preserving only safe `source_type`/`offset` parameters.
9. Top navigation and workspace/dataset links now point to `/evidence`; `/documents` remains valid through the redirect.
10. No whole-index search or new sorting control is added.

## Files changed

| File | Change |
|---|---|
| `src/ingestion/indexing/listing.py` | Global facets, safe labels/URL/domain, verified `index_identity` |
| `src/app/routes/documents.py` | Forward additive fields on list/detail |
| `tests/unit/ingestion/test_document_listing.py` | Global vs filtered counts, unsafe URL, missing metadata, index identity |
| `tests/unit/app/test_new_routes.py` | Route forwarding and detail safe-field assertions |
| `frontend/src/routes/evidence/+page.svelte` | Evidence browser, global facets, URL/back navigation, PDF-only location |
| `frontend/src/routes/evidence/[id]/+page.svelte` | Exact-ID chunk detail and safe provenance |
| `frontend/src/routes/documents/+page.server.ts` | 308 alias preserving safe filters |
| `frontend/src/routes/documents/+page.svelte` | Removed duplicate list |
| `frontend/src/lib/types.ts`, `api.ts` | Additive document fields only |
| `frontend/src/lib/components/AppNav.svelte`, root/dataset pages | Evidence links |
| `frontend/tests/evidence-browser.spec.ts` | 7 tests |
| `docs/20260424-openapi-swagger.yaml` | Additive listing/detail fields |

No RAG ingestion step, corpus/index bytes, provider/default, dependency or lockfile change.

## Tests run

| Command | Result |
|---|---|
| `bash scripts/check_backend.sh fast tests/unit/ingestion/test_document_listing.py tests/unit/app/test_new_routes.py -q` | **27 passed** |
| `bash scripts/check_backend.sh fast` | **2367 passed, 1 skipped, 115 deselected** |
| `bash scripts/check_backend.sh lint` | passed |
| `npm --prefix frontend run check` | 0 errors, 0 warnings |
| `npm --prefix frontend run build` | passed |
| `npm --prefix frontend run test -- tests/evidence-browser.spec.ts` | **7 passed** |
| Full Playwright | **88 passed, 9 skipped, 2 inherited failures** |

The two failures remain the inherited confidence-wording test and the intermittent New Chat `.message` locator; neither was touched.

Playwright used the existing `/tmp/qna-browser-libs` `LD_LIBRARY_PATH` workaround.

## Backward compatibility

- `/documents` API endpoints are unchanged; only additive fields appear.
- Browser `/documents` redirects after parity; safe filters survive.
- `source_type_counts` keeps filtered semantics; new global facets are separate.
- No index write or second Chroma client is introduced.

## Residual risks / pending work

- The global facet mirrors the current in-memory store; missing/unknown metadata still appears as `unknown`, not inferred.
- `index_identity` is present only when the existing collection metadata contains a valid `source_snapshot_sha256`; local snapshots without it honestly show unavailable.
- Raw detail metadata remains in the existing response for compatibility; the UI uses the safe fields. A future stricter allowlist is still separate work.
- P09 turn inspector/SSE remains next; P10 readiness after that.

## Rollback

Revert the listing/router additive fields and tests, remove `/evidence` pages, restore the old `/documents` page, revert nav/root/dataset links, remove the redirect server file and the evidence spec. No data/index migration is needed.

## Next

P09 — Q&A turn showcase, SSE decoder correctness and selected-turn inspector; then P10.
