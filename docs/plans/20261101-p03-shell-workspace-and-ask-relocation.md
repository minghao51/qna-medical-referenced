# P03 — Shell, research workspace and `/ask` relocation

**Status:** implemented offline; review/acceptance pending. No deployment, live/paid provider call, hosted export, data/index mutation or public rollout was performed.

**Approval reference:** owner approved **G-ROUTES** (root workspace + chat move to `/ask`, legacy diagnostic routes retained) and **G-AUTH** (Cloudflare Access + Tunnel + server-side key injection + no published ports; deployment artifacts staged, not executed).

## Scope delivered

1. **Design tokens** — Fieldnote paper/ink/teal/rust/blue/secondary tokens with legacy aliases (`--page-bg`, `--surface-*`, `--border-color`, `--text-color`, `--muted-color`, `--accent-soft`) so unmigrated routes keep working. Editorial Georgia headings, Arial/Helvetica body, visible `:focus-visible` ring.
2. **Shell landmark** — skip link to `#main-content`; `AppShell` now owns the single `<main>` landmark with 1344 max content width and 48/24 px margins. The nested `<main>` in the experiments detail panel became a labelled `<section>`.
3. **Navigation** — FIELDNOTE brand, Overview / Ask / Evidence / Research, private-lab note, and a labelled mobile `Menu` disclosure under 860 px. Research is a disclosure with working destinations: Workspace, Evaluations, Features, Ablation, Pipeline documentation, Help, Settings, System health. Escape closes menus and restores trigger focus; backdrop closes.
4. **Chat relocation** — the existing chat page moved intact to `/ask` (same request, history, abort, source, pipeline and cookie behavior); chat-specific Playwright visits now target `/ask`. Its title/heading are preserved for parity.
5. **Root workspace** — replaces the chat landing with a private-lab evidence story. It consumes the actual report API and `normalizeLegacyArchive`: faithfulness mean/measured/failed/expected, six-metric slot totals, report revision/date, historical-winner caveat, and links to `/eval?tab=quality`. Archive and corpus panels load independently; missing/unauthorized/error states never become zero.
6. **Corpus context** — actual `/documents` total and source-type counts, labelled as chunks (not publications) with a units warning. No fixed count is hardcoded in the frontend.
7. **Research subnav** — Workspace / Evaluations / Features only. Datasets and Methodology are intentionally absent until P04–P06 land; no broken links.
8. **`/research` redirect** — 307 to `/` so there is no duplicate workspace.
9. **Retained diagnostics** — `/eval`, `/eval/ablation`, `/experiments`, `/health`, `/settings`, `/help`, `/docs/pipeline` remain reachable from nav; `/documents` remains the interim Evidence destination until P08.

## Files changed

| File | Change |
|---|---|
| `frontend/src/routes/+layout.svelte` | Tokens, legacy aliases, typography, focus ring, Fieldnote default title |
| `frontend/src/lib/components/AppShell.svelte` | Skip link, single main landmark, width/padding |
| `frontend/src/lib/components/AppNav.svelte` | Research-first nav, research disclosure, mobile Menu, focus/Escape behavior |
| `frontend/src/lib/components/ResearchNav.svelte` | New working subnav (availability-scoped) |
| `frontend/src/routes/+page.svelte` | New research workspace with independent archive/corpus states |
| `frontend/src/routes/ask/+page.svelte` | Existing chat page moved; stylesheet path adjusted |
| `frontend/src/routes/research/+page.server.ts` | 307 redirect to `/` |
| `frontend/src/routes/experiments/+page.svelte` | Nested `<main>` → labelled `<section>` |
| `frontend/tests/chat.spec.ts`, `pipeline.spec.ts`, `markdown-rendering.spec.ts` | Chat visits target `/ask` |
| `frontend/tests/research-workspace.spec.ts` | Workspace coverage/units, independent failure, redirect, mobile menu/Escape |

No backend, provider, default, metric/evaluator, data or lockfile change.

## Tests run

| Command | Result |
|---|---|
| `npm --prefix frontend run check` | **0 errors, 0 warnings** |
| `npm --prefix frontend run build` | **passed** |
| `npm --prefix frontend run test -- tests/research-workspace.spec.ts` | **4 passed** |
| `npm --prefix frontend run test -- tests/research-workspace.spec.ts tests/chat.spec.ts tests/markdown-rendering.spec.ts` | **9 passed** |
| Full `npm --prefix frontend run test` | **64 passed, 9 skipped, 2 failed** |

The two failures are inherited and untouched: `frontend/tests/pipeline.spec.ts:249` expects the old “Overall Confidence” wording while the panel renders “Pipeline diagnostic (uncalibrated)”, and the New Chat test uses a strict `.message` locator that intermittently resolves before/against the welcome state. The New Chat test passed in one full run and failed in another; no fix was applied because it belongs to P09/owner review.

Playwright used the existing `LD_LIBRARY_PATH=/tmp/qna-browser-libs/root/usr/lib/x86_64-linux-gnu` workaround because system NSS/NSPR libraries are absent.

## Visual/accessibility evidence

- Desktop workspace: hero, archived coverage, Q&A entry, three pathways, corpus units.
- Mobile 390 px: labelled `Menu` opens the primary/research panel; Escape closes it and restores focus to the trigger.
- Skip link and one `<main>` landmark; nav links expose `aria-current`; menu buttons expose `aria-expanded`.
- Coverage bar has a text alternative with measured/failed/expected counts; all values and denominators remain in text.
- Focus ring uses the teal token with offset; targets are 44 px for primary navigation/actions.

## Backward compatibility

- Chat behavior, API calls, cookies and history semantics are unchanged; only the browser path moved.
- Legacy diagnostic routes and exports remain reachable; no redirect removes them.
- `/documents` is still the working Evidence page; `/evidence` and `/documents` aliasing remain P08 work.
- Existing pages inherit new tokens but keep their legacy CSS variable aliases and layouts.
- Unavailable archive/corpus states are explicit; the workspace never substitutes latest-run data or zeros.

## Residual risks / pending work

- P04–P06 screens do not exist yet; Datasets/Methodology are omitted from the subnav rather than linking to placeholders.
- The root workspace shows only the archived baseline coverage and corpus inventory; it is not the full evaluations/datasets workspace.
- Chat visual refinement, SSE correctness and turn inspection remain P09. The inherited confidence-wording and intermittent New Chat test failures remain for P09/owner decision.
- Deployment artifacts exist but were not executed; G-AUTH release evidence is still pending.
- `/documents` remains middleware-only inside the app; Cloudflare Access protects it at the edge for the demo.

## Rollback

Restore the previous `frontend/src/routes/+page.svelte`, remove `routes/ask/`, `routes/research/` and `ResearchNav.svelte`, revert `AppNav`/`AppShell`/layout token changes, restore the experiments element, and revert the chat-route test updates. No data or migration rollback is needed.

## Next proposed slice

**P04 — coverage-first evaluations and methodology** (`/research/evaluations`, `/research/methodology`), reusing P01 coverage utilities and linking retained `/eval` diagnostics. P05 can follow against the shared metric utility; P06 follows P02+P03. P08 then P09, then P10 readiness.
