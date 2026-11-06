# Fieldnote implementation plan

**Plan status:** **P01–P10 are implemented and offline-verified** in the shared working tree; nothing is committed. Deployment, image publish/run, provider spend, hosted exports and authenticated-release verification remain separate owner decisions. See [P10 readiness](../../docs/plans/20261101-p10-readiness.md), [deployment pickup](../../docs/plans/20261101-deployment-pickup.md) and [continuation handoff](continuation-handoff.md).

Normative inputs: [implementation specification](implementation-specification.md), [file ownership map](implementation-map.md), [SVG index](README.md), [interaction contract](interaction-spec.md), [review findings](review-and-refinement.md), root `AGENTS.md` and the current migration decision register.

## 1. Completion target and boundaries

Deliver the private research workspace shown in the19 SVGs using existing SvelteKit/FastAPI infrastructure. The first usable outcome is a truthful archived evaluation view plus dataset/feature inspection—not a live experiment platform.

A completed implementation preserves:
- Existing chat/session safety, source rendering and recorded-trace semantics.
- Existing L0–L6 diagnostics, config inspection, experiment/ablation tools and exports.
- Frozen index/provider/evaluation definitions and non-comparability guards.
- Private/public-synthetic-only authority, CLI/YAML execution and existing external tracing boundaries.

No paid/provider run, corpus rebuild, index migration, public deployment, auth-platform build, automatic promotion or durable trace storage is authorized by this plan. Those remain separate approvals.

## 2. Starting observations and uncompleted gates

### Checked during planning
- Current branch `design/evidence-led-redesign`; design assets are untracked under `assets/svg/`, not yet committed. Do not reset/clean/stash them or overwrite user work.
- Re-read actual routes, artifact service, frontend helpers/components/types, Docker packaging, test configuration and relevant repository guidance.
- Existing focused offline baseline command:

```bash
bash scripts/check_backend.sh fast \
  tests/unit/app/test_evaluation_routes.py \
  tests/unit/evals/test_history_comparability.py \
  tests/unit/app/test_new_routes.py -q
```

Current verified baseline (P10 + follow-up): backend fast2367 passed/1 skip, offline2388/1 skip, lint passed; frontend check/build passed; Playwright108 passed/9 skipped/0 failed. See [P10](../../docs/plans/20261101-p10-readiness.md) and [P09.1/P10.1](../../docs/plans/20261102-p09p10-ask-surface-and-hardening.md).
- Existing frontend check passed0 errors/0 warnings in the preceding design review. SVG validation covered19 XML/rendered assets; see [validation record](validation.md).

### Still required before relevant release/code gates
| Gate | Required decision/evidence | May offline work continue? |
|---|---|---|
| G-AUTH | Private gateway/server credential delivery and operator role policy; no browser key or anonymous bypass | Yes for pure projections/mock UI and existing-auth tests; real deployment cannot be called ready |
| G-FIXTURES | Approval to package the six named public/synthetic fixture JSON files or equivalent fixed read-only source | Yes with missing-file state; deployed dataset feature incomplete until verified |
| G-CONTRACT | Review/approve new catalog DTOs, additive report metadata and selected-run semantics | Required before their code slices |
| G-ROUTES | Approve root→workspace and chat→/ask migration with diagnostic routes retained | Required before P03 |
| G-BRAND | Approve working title Fieldnote or retain existing title temporarily | Does not block behavioral work |
| G-RELEASE | Offline integration, auth packaging, accessibility and no unapproved behavior/default changes | Required before any separate release/deployment decision |

Do not wait for all gates to design more slides. Start with the bounded approved contract slice, keep blockers explicit and do not bypass them.

## 3. Sequence and checkpoints

| Task | Scope | Dependencies | Initial status |
|---|---|---|---|
| P00 | Revalidate source/authority, baseline and code-slice approval | None | Complete |
| P01 | Report identity and metric-display contract | P00 | Offline implemented ([report](../../docs/plans/20261101-p01-archive-identity-and-metric-semantics.md)) |
| P02 | Authenticated read-only dataset catalog + packaging | P00; G-FIXTURES approved | Offline implemented; image unbuilt ([report](../../docs/plans/20261101-p07-selected-run-safety-and-p02-catalog-internals.md)) |
| P03 | Tokens/shell/navigation + chat relocation + workspace | P01; G-ROUTES approved | Offline implemented ([report](../../docs/plans/20261101-p03-shell-workspace-and-ask-relocation.md)) |
| P04 | Coverage-first evaluations and methodology | P01, P03 | Offline implemented ([report](../../docs/plans/20261101-p04-evaluation-coverage-and-methodology.md)) |
| P05 | Feature evidence and honest legacy archive labels | P01, P03, P04 | Offline implemented ([report](../../docs/plans/20261101-p05-feature-evidence.md)) |
| P06 | Dataset catalog UI and revision-bound fixture cases | P02, P03 | Offline implemented ([report](../../docs/plans/20261101-p06-dataset-catalog.md)) |
| P07 | Confined run-scoped diagnostic drilldowns | P00 | Offline implemented ([report](../../docs/plans/20261101-p07-selected-run-safety-and-p02-catalog-internals.md)) |
| P08 | Evidence explorer facets and source detail | P03; additive documents contract | Offline implemented ([report](../../docs/plans/20261101-p08-evidence-facets-and-detail.md)) |
| P09 | Q&A turn showcase, stream correctness and inspector | P03, P08 | Offline implemented ([report](../../docs/plans/20261101-p09-qa-turn-state-and-inspection.md)) |
| P10 | Full offline integration, accessibility, migration/rollback and release readiness | P01–P09 | Offline complete; G-AUTH release pending ([report](../../docs/plans/20261101-p10-readiness.md)) |

Recommended review batches:
1. **Contracts:** P01, P02 internals, P07 internals; integrate shared paths serially.
2. **Research vertical slices:** P03 → P04, with P05 and P06 following agreed DTO/formatting contracts.
3. **Workbench/source parity:** P08 and P09; do not compromise existing research pages while migrating root.
4. **Readiness:** P10, then a separate owner decision about any deployment.

## 4. Task briefs

### P00 — Revalidation and next-slice review

**Work**
1. Read root/scoped instructions, current decisions/audit follow-ups and all linked specification/map sections. Confirm repository paths and any changes since this draft.
2. Record `git status`, branch/worktree and exact ownership before edits. Preserve untracked assets and existing user modifications.
3. Re-run the P01 focused baseline (`65 passed`) and frontend checks if source/environment changed. Inspect failures before proposing fixes.
4. Confirm local archive/fixture availability without credentials, private history or provider calls. Existing packaging excludes fixtures; record G-FIXTURES owner choice.
5. Review the implemented P01 changes/report rather than re-approving them. Then present the next bounded slice (P07 or P02 missing-state internals) with exact ownership/tests.

**Deliverable:** a short slice approval brief, not another broad redesign. Initial dates/counts in assets must not be silently relabelled current runtime.

**Exit (historical):** all P01–P10 slices are now complete offline; deployment/G-AUTH evidence remains the next gate. Use the continuation handoff and deployment pickup brief.

### P01 — Archive identity, null-safe metrics and exact delta semantics

**Owned files**
- Backend: `src/app/routes/experiments.py`; `tests/unit/app/test_new_routes.py`.
- Frontend worker: new `frontend/src/lib/utils/research.ts`, targeted `metric-definitions.ts`, new `frontend/tests/research-metrics.spec.ts`.
- Integrator: additive `types.ts`/`api.ts` shapes and necessary legacy experiment formatter callers; schema documentation after tests.

**Work**
Before report changes, include an explicitly approved authenticated-state guard for experiment list/results/config, matching evaluation policy. Their current no-key exposure is real; the new401 behavior is deliberate and must be disclosed, tested and included in approval. Do not weaken auth or build browser login in this task.

1. Add explicit report IDs to report lists so results can be fetched without guessing a config stem.
2. Hash/parse a single bounded report byte buffer; return additive `_artifact` provenance and known explicit config association. Preserve report root/winner data and all existing endpoints.
3. Unknown/invalid report/schema stays missing/unsupported; no fuzzy config matching or default-driven effective-config claims.
4. Create known-schema frontend projections for legacy answer metrics and current supported coverage data. Null, boolean, invalid/non-finite/count inconsistency are distinct from actual0.
5. Keep archive-specific shape adaptation in research.ts and shared arithmetic/formatting in existing eval.ts/metric-definitions.ts; do not duplicate finite/delta/coverage logic. Add metric family/unit/direction handling. Absolute score difference and relative percentage are separate; undefined relative change for zero/unavailable baseline.
6. Replace legacy missing-as-zero and universal-higher-is-better display where shared consumers currently make those claims. Do not alter evaluator/winner computation.

**Tests / acceptance**
- Unauthenticated/no-key experiment reads now return401 under the approved private policy; authenticated reads retain raw fields. Operator UI delivery remains G-AUTH, not silently fixed by a client key.
- Raw existing response fields retained; report ID resolves the medical archive despite config stem mismatch.
- Digest matches bytes returned, not a separately reread file; traversal/symlink/oversize/malformed input fails safely.
- Known baseline projects57 expected per row,268 successes/74 failures/342 slots, with legacy expectation basis labelled.
- Faithfulness mean remains .9799 with15 successes, not a fabricated57-case score.
- `.7008913797−.6596215032` renders+.0413 and relative+6.3%; lower latency/error correctly classified; zero baseline relative delta absent.
- Current comparable=false/null history guards unchanged.

**Checkpoint:** offline implementation exists in `docs/plans/20261101-p01-archive-identity-and-metric-semantics.md`. Review its 401 behavior, digest contract, actual archive coverage and the two inherited full-frontend failures before approving any workspace integration. P01 does not replace P04/P05 screens.

### P02 — Catalog API, bounded case projections and real packaging

**Owned files**
New `src/evals/research_catalog.py`, `src/app/schemas/research.py`, `src/app/routes/research.py`, `tests/unit/evals/test_research_catalog.py`, `tests/unit/app/test_research_routes.py`. Integrator owns factory/router/type/API/OpenAPI and any approved Dockerfile edits.

**Work**
1. Implement the fixed nine logical IDs and explicit known sources; no dynamic paths/plugins/provider calls.
2. Add authenticated GET list/detail/cases under `/research-data`. Enforce existing authenticated-state boundary; do not invent role grants or weaken old middleware.
3. Derive roots from PROJECT_ROOT/DATA_DIR/DATA_RAW_DIR exactly as specified, not CWD. Missing roots stay missing; no ensure_dirs call. Read bounded approved file snapshots once per request, compute actual current byte revisions and project only allowed fields. Summaries retain raw missing-review status; normalized default may be shown separately.
4. Preserve record units and supporting-array distinctions. All57/Expanded54 overlap computed from exact stored query strings with both revisions; no independence or historical-byte claim.
5. Require matching revision for cases; return409 on change. Ordinal is scoped to that revision, not a globally durable ID.
6. Review set stays summary-only; no reviewer IDs/frozen bodies. D11 entry references existing document inventory rather than opening another store. CSV row count remains separate from served chunks.
7. Apply approved fixture packaging: explicit six-file COPY only; no full tests, data regeneration or lock/dependency changes. Missing mounted data produces unavailable entries.

**Tests / acceptance**
- Unknown/malicious ID cannot become a path; symlink escapes denied; each missing/malformed/oversize entry independent.
- Limit1–100, nonnegative offset and required revision; mismatch409 with safe error shape.
- Proper counts/splits/labels/30 stored conversation turns; stopword/test-document arrays not counted.
- Exact overlap54 calculated, revision identities returned; near-duplicates not_assessed.
- No reviewer/absolute paths leaked; unauthorized requests denied even with no middleware key records.
- Runtime packaging test verifies fixtures present when approved, and missing-state behavior without them. No container image is deployed by this task.

**Checkpoint:** approve catalog payload and packaging evidence; no claim of historical dataset/result pairing.

### P03 — Shell, navigation, root migration and research entry

**Owned files**
Integrator owns layout/AppShell/AppNav/ResearchNav and route wiring. Page owner owns root workspace and `/ask` relocation with corresponding chat-route tests. No simultaneous edits to root/ask by P09.

**Work order**
1. Introduce design tokens with aliases preserving legacy CSS variables; establish landmarks/skip link without nesting multiple main landmarks.
2. Copy/move existing chat page to `/ask` with behavior preserved. Update chat-specific visits in chat/pipeline/markdown tests; leave `/eval` tests targeting `/eval`.
3. Verify chat parity before replacing root. Add root research story consuming actual report projection, independent corpus inventory and private-lab navigation.
4. Add research subnavigation, safe `/research` redirect, retained diagnostic destinations and missing/access states. Links to unfinished routes must show an explicitly scoped placeholder or remain absent until their slice lands; no broken nav.
5. Q&A remains one action away; no old local history deletion merely because the landing route changes.

**Acceptance**
- Root matches01/04 intent and private-lab caveats; unavailable archive/index can fail independently.
- `/ask` preserves chat request/history/abort/source behavior at this stage.
- Existing diagnostics/exports/config/help still reachable; no auto benchmark execution.
- Keyboard/mobile menu state, focus and active-nav semantics pass. API base/credentials unchanged.

**Checkpoint:** explicitly approve switching the root route after parity screenshots/tests. Roll back root/nav alone if migration fails; no data changes are required.

### P04 — Evaluation coverage and methodology

**Owned files**
New research evaluations/methodology pages, `MeasurementCoverage.svelte`, `evaluation-coverage.spec.ts`; integrator handles any existing QualityTab reuse and shared types.

**Work**
1. Distinguish archive selection from current run selection; use explicit report ID/revision rather than “latest” label.
2. Render each metric mean, successful/expected slots and failures with definition/unit/direction. Reflect unsupported/inconsistent/missing states instead of KPI zeros.
3. Render true aggregate completeness separately from cases:268/342 successful slots,74 failures; no342-query or patient inference.
4. Expose identity/source timestamp/coverage and a disabled comparison notice. Link to retained L0–L6 diagnostics rather than replacing them.
5. Explain legacy ranking vs reviewed evidence vs answer judgments; static methodology links existing pipeline/help.
6. Historical drilldown controls remain unavailable until P07 carries a genuine selected run, or until actual archive case rows exist. No latest fallback.

**Acceptance**
AC02/03/09/10; six-row desktop and stacked mobile; proper late-response selection guards; readable chart alternatives and focus. Unknown judge identity remains unknown; no high-average clinical claim.

### P05 — Features and legacy research honesty

**Owned files**
Feature page/component/spec; integrator coordinates existing experiments/ablation display changes and shared utility callers.

**Work**
1. Use archived report declared baseline/variant config; render four rows and numerical outcomes.
2. Label selected row Inspecting; expose raw archived winner only as historical, not current eligibility.
3. Keep declared, effective and observed evidence separate; unknown effective settings/index binding say unverified.
4. Curate capability map with code references for query understanding, medical chunking, optional reranking/HyDE/HyPE/enrichment. Include dependency and evidence scope.
5. Keep54-query reported reranking story distinct from57-query local JSON. No pooling, causal latency claim or invented uncertainty interval.
6. Retain old experiment configs/exports and ablation dimensions; replace hardcoded “latest/optimal” promotional labels with dated archive wording.

**Acceptance**
AC04/10; exact numeric/relative deltas; all four degraded measurement states; no runtime switch or launch control. Missing report/config association is explained, not auto-filled.

### P06 — Dataset catalog and expected-case inspection

**Owned files**
Catalog/detail routes, `DatasetDetail.svelte`, `dataset-catalog.spec.ts`; API/type integration serialized.

**Work**
1. Select by allowlisted catalog ID; show source revision, unit, availability and provenance rather than a combined dataset KPI.
2. Render splits, confidence/review absence, exact overlap and distinct frozen-review authority caveat.
3. Load cases only for supported approved projections with matching revision. Invalidate/reset stale case state after409; preserve user intent and explain refresh.
4. Expected panel displays stored labels/tokens as fixture expectations, not a medical answer. Current first LDL-C fixture is the representative case.
5. Observed panel carries explicit historical_binding=not_established with reason and remains unavailable for this archive. Never join by ordinal/text or query latest records to make it appear complete.
6. Deep-link the selected catalog, not private content. Handle summary-only/missing index/CSV/review entries independently.

**Acceptance**
AC05–08/15; unit counts and split bars correct, raw review absence vs normalized default explicit, revision race deterministic, safe typed rendering and keyboard/mobile selection.

### P07 — Selected-run artifact safety and preserved comparison guards

**Owned files**
Artifact service/evaluation routes/new scoped-record tests; integrator owns helper/type and existing eval/TrendingTab changes.

**Work**
1. Add strict evaluation-root confinement for explicit run directory names, including existing load_evaluation_run/load_answer_quality_details and the new scoped methods, rejecting dots/traversal/separators/symlink escape; do not create or migrate runs.
2. Add optional run selection to latest-only step/record methods, defaulting to latest only when omitted.
3. Echo selected actual run in scoped response. Bound record reads and malformed-line behavior; no uncontrolled file load for a tiny requested page.
4. Fix existing latest-first hydration: initialize selection before dependent fetches, render only matching loaded identity and allow explicit runs outside the current history page. Scope refresh to selection and reject out-of-order responses. Wire selected-run context through helpers. Missing explicit run stays404; no latest substitution and no stale response overwrite.
5. Preserve artifact compatibility as format-only and comparable=false/null averages. Do not add a frontend cohort validator or resurrect trend charts.
6. Dataset observed results remain disabled until real dataset revision/case binding exists; inspecting an independent selected run does not create that binding.

**Acceptance**
AC09/10; two temporary runs with deliberately different records demonstrate exact selected-run retrieval. Missing/unsupported versions/traversal/oversize limits fail safely. Existing history-comparability suite stays green.

### P08 — Evidence facets and source page

**Owned files**
Listing/documents route and related tests; evidence pages/spec; DocumentInspector edits serialized before P09.

**Work**
1. Add global facets separately from current filtered counts; reuse in-memory mirrors, no full-store scan per request.
2. Add optional existing source labels/URL/domain; verified index identity nullable, not guessed from directory name.
3. Move/adapt chunk list to `/evidence`; provide readable source/page/class/excerpt and real limits. Do not ship the mockup's proposed text search as a working input.
4. Implement exact-ID detail with incomplete excerpt warning, null dates and safe original URLs. Print page location only when semantics support it.
5. Redirect `/documents` only after parity; preserve safe source_type/page parameters. Keep old API endpoints unchanged.

**Acceptance**
AC11/14; PDF total1,306 with All2,473 for the verified fixture; filtered source_type_counts retain old semantics. Unknown/missing metadata safe; keyboard/mobile paging/detail/focus and unsafe URL cases pass. No index writes.

### P09 — Q&A showcase, decoder and selected-turn inspection

**Owned files**
`/ask`, small SSE utility and tests, optional per-layout chat state, PipelinePanel, existing chat/pipeline/markdown specs. Layout/DocumentInspector integration stays single-owner.

**Work**
1. Pair current-session user/assistant records into ephemeral turn display identities without changing history backend schema. Use per-layout state factory/context if needed, never an SSR module-global user store.
2. Preserve draft/completed-turn source/trace state during ordinary navigation; abort in-flight work safely on leaving as designed. Hard reload honestly loses unavailable sources/traces.
3. Implement buffered current-contract SSE decode, UTF-8 and frame boundary handling, explicit terminal-success requirement, malformed/EOF/incomplete states and no duplicate auto-resubmission.
4. Keep existing generation counters/abort guards and same-session conflict behavior; label composer, count limit, IME-safe keyboard and restrained live announcements.
5. Add per-turn evidence summary/Inspect action. Refactor existing panel into recorded stage/step/chunk inspection with every available raw field reachable.
6. Zero placeholder timing != measured zero; no context duration/provider-call tree/cost/TTFT/private reasoning created. Dialogs/mobile back restore focus/scroll.
7. Treat the current relative-URL failure as an existing migration blocker. Test absolute HTTP(S) bases, root-relative private prefixes and empty same-origin bases with include_pipeline composition and SSR-safe origin handling. Repair URL resolution without embedding keys or altering auth.

**Acceptance**
AC12/13; tests split terminal JSON/UTF-8 across network chunks, successful terminal, terminal error after content, EOF without done, abort/new chat/overlap, navigation/reload, legacy structured/string sources and safe Markdown. Updated tests verify uncalibrated raw diagnostics rather than confidence claims. No durable trace store added.

### P10 — Integration, visual/accessibility review and readiness

**Work**
1. Run full approved offline gates and document inherited vs introduced failures. No live opt-ins, corpus downloads or lockfile churn.
2. Verify all route aliases/query state, diagnostic tabs/exports and current API compatibility; update OpenAPI and targeted workflow docs only for implemented features.
3. Review responsive screens at320/390/768/1024/1440 plus200% zoom, keyboard-only journeys, screen-reader announcements, reduced motion, focus/dialog behavior and text/non-text contrast.
4. Inspect the authenticated private boundary using an approved test mechanism with isolated/stubbed provider/index state or an already-approved runtime; do not boot against real D11 just to test UI auth. Inherited startup metadata writes (audit F-03) are not authorized data changes or part of this redesign repair scope. No model calls are needed for these read-only checks. No key in bundle or public fallback. G-AUTH remains blocked until this evidence exists.
5. Verify approved fixture image inclusion and missing data-volume states; do not deploy image as part of this check.
6. Confirm unchanged `data/`, provider/default/profile configuration and lockfiles; schema additions do not alter frozen metric/evidence semantics.
7. Produce per-slice handoffs and final readiness/rollback report. Obtain separate approval before any deployment or future deferred extension.

**Exit:** AC01–17 satisfied, or explicit owner-accepted limitations recorded without claiming unsupported features complete.

## 5. Validation commands and test discipline

Commands below are a **future execution checklist**, not claims that new tests currently exist or have passed.

### Focused existing baseline

```bash
bash scripts/check_backend.sh fast \
  tests/unit/app/test_evaluation_routes.py \
  tests/unit/evals/test_history_comparability.py \
  tests/unit/app/test_new_routes.py -q
```

### After corresponding new files land

```bash
bash scripts/check_backend.sh fast \
  tests/unit/evals/test_research_catalog.py \
  tests/unit/app/test_research_routes.py \
  tests/unit/evals/test_run_scoped_records.py \
  tests/unit/ingestion/test_document_listing.py -q

# Canonical broader offline and read-only static gates
bash scripts/check_backend.sh fast
bash scripts/check_backend.sh offline
bash scripts/check_backend.sh lint

# Existing frontend runtime/package tooling; no install/lock update implied
cd frontend
npm run check
npm run build
npm run test -- --project=chromium tests/research-metrics.spec.ts \
  tests/research-workspace.spec.ts tests/evaluation-coverage.spec.ts \
  tests/feature-evidence.spec.ts tests/dataset-catalog.spec.ts \
  tests/evidence-browser.spec.ts tests/sse.spec.ts
```

- Current Playwright default starts a4173 frontend and requires installed Chromium/runtime libraries. Do not silently install packages or alter system/browser dependencies; report missing tooling and seek approval as needed. The preceding design validation used temporary extracted libraries, not a repo dependency change.
- New UI tests stub responses and deny unstubbed API/external requests. Do not point ordinary tests at a provider-backed server or set live opt-in variables.
- Existing full Playwright suite includes optional/direct backend checks; inspect per-spec behavior and isolate/mask appropriately before claiming offline no-network coverage. Migrate chat route assumptions deliberately, not by broad find/replace.
- New backend tests use temporary fixture/evaluation/Chroma roots and fake embeddings. Keep repository data guard enabled; no stateful server lifespan/provider construction for simple catalog tests.
- Ruff/mypy/import boundaries must pass; no broad suppression, quality-floor reduction or unrelated formatting sweep.

## 6. Parallel work and integration ownership

- Integrator exclusively owns shared `types.ts`, `api.ts`, factory imports, shell/layout/nav, test helpers and document index/OpenAPI changes.
- P01 report backend, P02 catalog internals and P07 artifact selection can run independently after their exact contracts/ownership are approved. Shared route integration is serialized.
- P04 and P06 leaf pages/tests may run in parallel after contracts and P03 shell land. P05 reuses shared normalizer; it must not create a second one.
- P08/P09 share DocumentInspector and must serialize edits. P09 starts after the P03 relocation, not concurrently with root migration.
- Every worker gets exclusive files, known test scope and no provider/credential/data-write permission. No generic subagent should infer task authorization from this roadmap alone.

## 7. Migration / rollback

1. Land contract additions before new callers. Preserve existing roots/fields/endpoints; retain filtered document count semantics.
2. Relocate chat and pass parity before root switches. If root migration regresses, restore the old landing/nav while keeping `/ask` available for any links already introduced.
3. Keep legacy diagnostics until full capability inventory proves equivalent alternatives; new coverage pages do not replace detailed tabs or exports.
4. New catalog endpoints and UI are additive and read-only. Rollback is code/nav removal of that slice, not fixture deletion, index reset or history purge.
5. New response metadata can be ignored by old clients. Schema/version drift is an unsupported state, not an automatic rewrite of saved artifacts.
6. No persisted research UI state is required. Revision/selection changes invalidate ephemeral state; no database migration/rollback is needed.
7. Task-scoped commits/checkpoints only after owner approval. Do not use destructive git commands to roll back unrelated user work.

## 8. Per-slice report template

```text
Task / approval reference / code revision:
Owned files and actual changes:
Existing behavior retained:
Contracts and backward compatibility:
Tests run (exact command, result, offline/network status):
Visual/accessibility evidence:
Data/defaults/locks unchanged confirmation:
Open blockers and inherited failures:
Rollback instructions:
Next proposed slice (not assumed approved):
```

Store the report using repository date-prefixed plan/handoff conventions after inspecting existing docs; do not claim implementation completed merely by marking this plan's task table.

## 9. Deferred work, explicitly not hidden completion criteria

Whole-index search, durable trace history, verified semantic comparison cohorts, matched-case win/loss/slice analysis, confidence intervals, live usage/cost analysis, provider call trees, model switching, automatic promotions, patient workflows and public rollout remain separate product/data/security work. The initial implementation must make their absence understandable rather than faking them.

## 10. Immediate next action

P01–P10 and the P09.1/P10.1 review follow-ups are offline-complete. Use [continuation-handoff.md](continuation-handoff.md), [next-agent-start.md](next-agent-start.md) and the [deployment pickup brief](../../docs/plans/20261101-deployment-pickup.md). The next work is the owner-approved Cloudflare demo/G-AUTH evidence or explicitly approved follow-ups; do not redo completed slices or claim authenticated release without recorded evidence.
