# Implementation planning brief — private research workspace
## Assignment and authority
P01–P10 are now implemented offline. Pick up from [continuation-handoff.md](continuation-handoff.md), the [P10 readiness report](../../docs/plans/20261101-p10-readiness.md) and the [deployment pickup brief](../../docs/plans/20261101-deployment-pickup.md). Deployment and authenticated-release verification are not done. Do not redo completed slices without evidence. Follow AGENTS.md approval and scope rules.
Read [review-and-refinement.md](review-and-refinement.md), [repository-findings.md](repository-findings.md), [screen-data-map.md](screen-data-map.md), [interaction-spec.md](interaction-spec.md).
Visual order: 01 → 13 → 14 → 15 → 16 → 18 → 08 → 09 → 12; then mobile/system/source screens.

**Authority:** `docs/plans/migration/decisions.md` D01 private lab, D02 public/synthetic only, D07 no clinical-suitability claims, D09 CLI/YAML-first, D10 Pydantic Evals + primary Logfire UI. Read relevant migration/audit records again; these assets do not override existing gates or authorize public-demo work, live runs, paid calls, uploads or default changes.

## Outcomes and primary journeys
1. Determine what a score actually measures, how many successful measurements support it, and what failed.
2. Inspect implemented/configured features without mistaking an old archive or declared flag for effective runtime improvement.
3. Understand dataset units, overlap, labels, review authority and index binding.
4. Inspect Q&A answers, individual turns and recorded RAG steps without fabricated calls.
5. Preserve existing research tools, exports, source detail and diagnostics while making research first-class.

Journeys:
- Workspace → archived report → measurement coverage → feature matrix → dataset → expected case / genuinely bound observation.
- Evaluations → identity + eligibility → inspect independently; compare only if a future verified cohort contract permits it.
- Q&A workbench → selected answer → full turn → individual recorded step → chunk → original source.
- Dataset catalog → splits/labels/overlap → case expectation → matching run evidence if available.

## Retain / refactor / replace / retire / defer
| Action | Scope |
|---|---|
| Retain | SvelteKit/TypeScript, API/cookies/errors, FastAPI/RAG, offline ingestion, frozen index, existing evaluation/experiment routes, raw metric semantics, safe Markdown/URLs, exports, lazy loading, primary external trace tooling |
| Refactor | Shell/navigation; chat into turn/composer/inspector views; reusable null-safe metric formatting; report identity; source facets; selected-run drilldown |
| Replace | Chat-only blank landing; undifferentiated KPI grids; modal-only source detail; buried datasets/config evidence |
| Retire as claims | Uncalibrated medical-confidence percentages, automatic legacy winners, larger-is-always-better deltas, missing-as-zero metrics and unverified history averages |
| Defer | Public rollout, feature toggles, web benchmark launcher, hosted trace duplication, clinical tools, provider-call logs, inferred confidence intervals and automatic promotion |

## Proposed pages and components
- /: WorkspaceStory, ResearchPathways, InventoryContext, WorkbenchEntry.
- /research/evaluations: ArtifactSelector, ArtifactIdentity, MeasurementCoverageTable, MetricDefinition, EligibilityNotice, RunScopedCaseLink.
- /research/features: DeclaredVariantMatrix, CapabilityEvidenceTable, EffectiveSettingsDisclosure, ArchiveCaveat.
- /research/datasets: DatasetCatalog, DatasetProvenance, SplitChart, OverlapNotice, ReviewAuthority, FixtureCaseInspector.
- /ask: Conversation, TurnIndex, TurnShowcase, Composer, SourceList, TurnInspector, RetrievalStepInspector.
- /evidence and /evidence/[id]: ChunkResults, TypeFacets, Pagination, SourceDetail, ProvenanceFacts.
- Existing ingestion/retrieval/quality/advanced/trending/config/help capabilities remain reachable. Keep legacy URLs/query parameters via aliases/redirects.
These are conceptual boundaries, not approval for new generic frameworks, registries or dependency injection.

## Data contracts and backend work
### Required design-support slices
1. **Report identity adapter:** current config medical_semantic_exp and report medical_semantic_chunking_exp stems differ. Explicitly register/match reports rather than assuming stems; identify archived source/schema. Never present this report as current /evaluation/latest.
2. **Legacy metric adapter:** distinguish old report baseline.metrics from newer summary/L6 and projected completeness. Preserve mean/count/error_count/expected_slots and status, with absence preserved as null. For archived baseline six ×57 slots, successful268/failed74. No guessed per-case failures.
3. **Read-only dataset catalog:** allowlisted file-backed metadata, current content digest, record unit/count, split/confidence/review summaries and overlap diagnostics. Do not expose arbitrary filesystem paths as queryable server input. Bound case access, payload size and permissions.
4. **Historical drilldown:** selected artifact identity is carried to case/metric calls. Current generic records routes use latest; do not reuse them for historical selection. Missing case rows remain visibly unavailable.
5. **Facets/provenance:** retain existing fields; add unfiltered type counts and verified public-safe index identity/labels where needed.
6. **Access:** preserve private posture and resolve secure server-side UI auth. Evaluation routes explicitly require authenticated request state. No keys in VITE variables or shipped browser code.

### Deliberately not required initially
- Recompute archives or reindex to match a design.
- Build semantic comparison cohorts: current API comparable=false must remain authoritative.
- Whole-index search, durable chat traces, full provider events, extra hosted exports.
- Case results for missing archived directories. No aggregate-to-case reconstruction.

Model separate concepts: execution state; measurement completeness; artifact compatibility; semantic identity; comparison eligibility; quality/promotion gate. Format version is not evidence of the others.
Dataset identity includes bytes/labels/split and sampling context. Source case IDs join records only; telemetry identities remain fresh/random under existing privacy rules.

## Suggested vertical slices and acceptance
| Slice | Dependencies | Acceptance criteria |
|---|---|---|
| 0. Contract + authority audit | None | Verify decisions, all19 assets, source artifacts, auth, local report paths; safe fixtures and baseline tests; record exact scope |
| 1. Research shell + private workspace | 0 | Research pathways visible, Q&A one click away, legacy routes reachable, no live execution controls |
| 2. Coverage-first evaluation | 1 + adapter | Six real baseline rows show means and 57 expected each; totals268/74/342; missing slots never become zero scores; no live/latest mislabel |
| 3. Feature evidence | 2 + explicit archive identity | Declared matrix matches config/report; absolute +.0413 and relative +6.3% distinct; degraded statuses and absent effective provenance visible; no winner promotion |
| 4. Dataset catalog + case expectations | 1 + allowlisted catalog | Actual fixture units/splits; overlap54/all57 warning; review assertion vs authentication; correct expected case and explicit absent observations |
| 5. Bound drilldowns + comparison guard | 2/4 | Historical selection never loads latest case records; comparable=false blocks trends/compare; unsupported/config-only states work |
| 6. Q&A/source refinement | 1 + existing SSE/facets | Per-turn identity, terminal states, safe sources, placeholder timing semantics, absent historical trace and mobile focus behavior preserved |
| 7. Optional research extensions | Separate approval | Genuine matched cases, slice analysis/uncertainty, search or durable traces only with tested data contracts and permissions |

Slices 2 and4 can progress independently after their contract work. Require exact file ownership and focused tests in the detailed plan. Do not bundle provider/model/index/default changes into visual work.

## Validation priorities
- Numerical: metric direction; score-points vs relative percentage; count/slot/turn/chunk units; coverage arithmetic; null vs zero vs skipped.
- Identity: exact archive selected, dataset bytes not inferred from current path, no automatic stem joins, latest-only API leakage blocked.
- Comparison: non-comparable histories stay non-comparable; old winner and matching formats cannot bypass gates.
- Review: confidence/high labels and manifest hash assertions never become authenticated clinical authority.
- Security: protected catalog paths, bounded payloads, server auth/role policy, safe exports, no raw SDK telemetry or user secrets.
- Q&A: SSE completion/error/cancel, session-busy, history deletion/reload/isolation, safe links/Markdown.
- Accessibility: semantic forms/tables/disclosures, keyboard/focus/announcements, charts with data alternatives, 320–1440px, 200% zoom, screen reader and reduced motion.
- Preserve existing pipeline L0–L6 detail and research exports; do not delete useful capabilities because a new screen omits their expanded state.

## Risks and unresolved decisions
- Private research is established; exact secure web login/role deployment is not.
- Current fixture contents are not proven historical dataset bytes. The local57 report is legacy and underlying run folders are absent.
- D11/intermediate counts differ; no verified fresh source chronology.
- Old keyword/source diagnostics and newer reviewed-evidence measures have different semantics.
- Clinical review, independent judge identity and eligible comparison cohorts are not established by this design.
- Full reload loses current chat sources/traces until separately approved durable storage exists.
- Working name remains proposed.

## Next implementation checkpoint
P01–P10 are implemented offline; use the continuation handoff and P10 readiness report rather than drafting another broad architecture. The next work is the owner-approved Cloudflare demo/G-AUTH evidence or explicitly approved follow-ups. Identify newly discovered contradictions or deferred design elements explicitly, and never replace unavailable runtime data with an SVG fixture.
