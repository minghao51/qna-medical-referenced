# P09.1 / P10.1 — Ask surface and readiness hardening

**Status:** implemented offline. No provider call, deployment, hosted export, data/index mutation or public rollout was performed.

**Trigger:** owner requested the review-recommended follow-up pass after visual/functional review of P01–P10.

## Delivered

### Ask surface (P09.1)

1. `/ask` now has a Fieldnote research-workbench frame: eyebrow, `Ask the evidence.` heading, public/synthetic-only and not-a-clinical-service copy, and a title of `Ask · Fieldnote`.
2. Desktop conversation rail: New conversation, conversation label, derived turn index with question/status, selected turn, and cookie-bound history disclaimer. Hidden below 1024px.
3. Empty state explains the frozen-index context, clinical limit and inspection expectation instead of the old patient-facing welcome.
4. Turn presentation uses paper/ink/teal tokens, an editorial user block, a recorded assistant card, turn status, source cards and a recorded-trace summary.
5. The pipeline panel no longer opens automatically. It is opened by Inspect turn or Show recorded trace.
6. Loading exposes `Stop response`; aborting retains partial output as `Incomplete` with an `Ask again` action.
7. The pipeline inspector is now a native modal `<dialog>` with an accessible name, focus trap, background inertness, scroll lock, Escape dismissal and focus restoration.

### Readiness hardening (P10.1)

1. `/health`: runtime rows use a wrapping grid; long runtime values are disclosure blocks with bounded, scrollable `<pre>` content; runtime spans the full grid row. Removed the 6.6k–8k px horizontal overflow and the 12k px single-column JSON page.
2. Dataset detail: case navigation/select can shrink; 390px select/root overflow is removed.
3. `/eval`: grid track is `minmax(0, 1fr)` and the tab wrapper can shrink; 390px page overflow is removed (the tab strip remains intentionally horizontally scrollable).
4. `/eval/ablation`: page header and `Archived feature benchmark` label render in every state; empty data now has one `<h1>` and an explicit no-winner/no-eligibility message.
5. Report IDs get break opportunities at underscores and a smaller mobile size; no mid-word split such as `chu/nking`.
6. Motion: smooth shimmer skeleton removed; global `prefers-reduced-motion` handling added; typing indicator stops animating under reduced motion.
7. Tokens/craft: rust brand bar and teal active-nav underline restored; success text uses a darker `--success`; settings/experiments status colors no longer fail 4.5:1; methodology reading measure narrowed; settings cards fit 320px.
8. Evidence: at mobile widths metadata columns are hidden, excerpts clamp to three lines, source files no longer force width, and the page fetches 20 rows instead of 50. Desktop remains 50 rows.
9. Brand link and primary toggles meet the 44px target. Standalone `.text-link`, evidence Inspect and evidence-detail back/target links now provide 44px targets; inline prose links retain text semantics.

### Visual reconciliation with the SVG direction

1. **Root**: removed the bordered/gradient hero card, restored the editorial unboxed hero, made the Q&A panel the dark ink block from SVG 01, and replaced corpus count cards with labelled horizontal bars (PDF/HTML/reference/Markdown).
2. **Evaluations**: measurement slots now use the dark ink block from SVG 13 instead of a light summary card; the coverage table remains the primary evidence surface.
3. **Evidence detail**: rebuilt as the SVG 03 two-column composition: excerpt on the left, provenance/host/position/verification and original-source action on the right, technical identity below.
4. **Tabs**: narrow-screen evaluation tabs now wrap into two rows rather than clipping horizontally.
5. **Experiments**: duplicate `baseline` configs are distinguished by experiment ID, and long report IDs wrap rather than clip.
6. **Navigation**: rust brand mark and teal active underline now match the design system across routes.

**Intentional adaptations retained:** the datasets index keeps an inventory + context split with a dedicated revision-bound detail route rather than the SVG's in-page master-detail; the evidence browser uses a dense table/card hybrid for 2,473 chunks rather than a large illustrative card list; and the workspace keeps the extra investigation paths/selection controls because they are functional navigation, not decorative mockup content.

## Files changed

| File | Change |
|---|---|
| `frontend/src/routes/ask/+page.svelte` | Workbench layout, rail, copy, stop/retry, no auto-open, tokens, mobile composer |
| `frontend/src/lib/components/PipelinePanel.svelte` | Native modal dialog, focus trap, scroll lock, Escape/restore, token styling |
| `frontend/src/routes/+layout.svelte` | `--success`, reduced-motion media query |
| `frontend/src/lib/components/AppNav.svelte` | Rust brand mark, teal underline active state, 44px brand target |
| `frontend/src/lib/components/LoadingSkeleton.svelte` | Static skeleton; shimmer removed |
| `frontend/src/routes/health/+page.svelte` | Wrapping runtime rows, disclosure for long values, full-width runtime card, mobile stack |
| `frontend/src/routes/research/datasets/[datasetId]/+page.svelte` | Case-nav shrink/select width |
| `frontend/src/routes/eval/+page.svelte` | Grid min-width fix |
| `frontend/src/routes/eval/ablation/+page.svelte` | Always-on archived header, empty state, success token |
| `frontend/src/routes/research/evaluations/+page.svelte` | Report-ID `<wbr>` wrapping and mobile size |
| `frontend/src/routes/research/features/+page.svelte` | Report-ID `<wbr>` wrapping and mobile size |
| `frontend/src/routes/research/methodology/+page.svelte` | Reading measure 760px |
| `frontend/src/routes/settings/+page.svelte` | 320px-safe grid, success/blue tokens |
| `frontend/src/routes/experiments/+page.svelte` | Report wrapping, success token, active border |
| `frontend/src/routes/evidence/+page.svelte` | Mobile compaction, 20-row mobile page, 50-row desktop page, 44px Inspect targets |
| `frontend/src/routes/evidence/[id]/+page.svelte` | Two-column excerpt/provenance detail composition |
| `frontend/src/routes/+page.svelte` | Editorial hero, dark Q&A block, corpus count bars |
| `frontend/src/lib/components/TabNav.svelte` | Wrapping tabs on narrow screens |
| `frontend/tests/chat.spec.ts` | New Ask copy, Stop/Incomplete/Ask again |
| `frontend/tests/pipeline.spec.ts` | Explicit trace opening, modal/focus/backdrop assertions |
| `frontend/tests/readiness.spec.ts` | 390px route matrix and one-`h1` checks for dataset/eval/ablation/health |
| `frontend/tests/accessibility.spec.ts` | Roving tab focus/selection regression |
| `docs/testing/accessibility.md` | axe, accessibility-tree and keyboard audit |

No backend, provider, metric definition, data, index or lockfile change. The accessibility audit and cancellation evidence are recorded without adding a runtime dependency.

## Verification

| Gate | Result |
|---|---|
| `npm --prefix frontend run check` | 0 errors, 0 warnings |
| `npm --prefix frontend run build` | passed |
| Full Playwright | **108 passed, 9 skipped, 0 failed** |
| 320/390/768/1024/1440 route sweep | no page-level horizontal overflow on the reviewed routes |
| Before/after | `/health` 8,062 → 0 px horizontal overflow, 12,715 → 1,123 px desktop height; dataset 461 → 0; `/eval` 109 → 0; evidence mobile 18,519 → 3,602 px with 12 rows and 44px uniquely named Inspect targets; evaluation mobile tabs wrap with no clipping |
| Modal evidence | `:modal = true`, body overflow hidden, 12-Tab containment, Escape restores focus |
| Contrast spot check | no non-disabled text failures on the reviewed routes |
| axe-core 4.10.2, WCAG A/AA | **0 violations** across 16 static and 7 dynamic states |
| Cancellation-focused backend tests | **21 passed** (ASGI disconnect, stream failure, telemetry cancellation) |

## Residual risks / open items

- No authenticated-release evidence, image build or deployment was performed; G-AUTH remains pending.
- The Ask rail is session-only; hard reload still loses unavailable sources/traces.
- The datasets page intentionally uses an index + dedicated detail route rather than the SVG's in-page master-detail; this preserves revision-bound case handling and direct linking.
- The evidence list intentionally remains a dense table/card hybrid; the SVG card list was illustrative, not viable for 2,473 chunks without paging/search.
- Mobile evidence uses 12 compact rows per page; a server-side search/sort contract remains out of scope.
- Inline prose links remain compact under WCAG's inline-text exception; standalone link/button targets are 44px.
- Axe/accessibility-tree audit is recorded in [docs/testing/accessibility.md](../testing/accessibility.md); no physical NVDA/VoiceOver session was available.
- Provider cancellation remains cooperative at the SDK boundary; ASGI disconnect closes the route iterator and the focused backend cancellation tests pass (21 passed). A provider cannot guarantee immediate billing/stop semantics after disconnect.

## Rollback

Revert the files above and the three Playwright specs; no data, index or lockfile migration is required. The demo stack was not touched.
