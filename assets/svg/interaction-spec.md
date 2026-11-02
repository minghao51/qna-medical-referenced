# Interaction specification
## Navigation and hierarchy
Proposed top level: Overview / Ask / Evidence / Research, within the private lab. Overview is now a research workspace; the research subnav exposes Evaluations / Features / Datasets / Methodology.
- Overview links to the Q&A workbench rather than defaulting to a patient-oriented composer. Carry any intentionally entered draft only in private app state, never URLs.
- Keep the existing completed conversation when navigating away/back; do not clear history on route change.
- /documents and other current routes remain valid through aliases or redirects. Preserve evaluation tab/run parameters and exports.
- Research contains evaluations, experiments, ablations, health, read-only config and pipeline documentation.
- At <640 px use a labelled Menu disclosure. Escape closes, focus returns to trigger, active route announced.

## Ask and turn showcase
- Accessible textarea label, character count and 2,000-character limit. Enter submits; Shift+Enter newline; do not submit while IME composition is active.
- Submit trims whitespace. Pending state prevents concurrent session submissions; preserve failed draft and partial answer.
- Explicit pending → complete / incomplete / error. Only terminal success gets “Complete”; received tokens alone do not establish success.
- Existing backend trace is delivered at completion. Pending UI may say generating, but cannot claim retrieval completed or show speculative live stage timing.
- Stop aborts fetch; label retained partial output “Incomplete.” Backend cancellation is cooperative; do not promise instant provider termination.
- Completed turn showcase: source entry count, breakdown availability and inspect action. Do not show a synthetic medical-confidence badge.
- New conversation requires destructive-history confirmation, then DELETE /history; respect session-busy errors. No multi-conversation library is promised.
- Turn index is derived from current conversation message pairs, not a dataset query ID. Keyboard buttons scroll to heading and move focus without trapping the reader.
- Auto-follow only while reader is near bottom. If they scroll up, offer “Jump to latest.” Announce completion/errors, not every token.

## Full turn and individual-step inspection
Screen 09 is the current-session full trace; screen 12 is the selected step.
1. Open from the answer's own Inspect control. Keep that answer and turn identity selected.
2. Expand/collapse retrieval, context and generation independently via native disclosure semantics. Include skipped records rather than erasing them.
3. Within retrieval, retain actual step names; humanize visually but preserve raw name in inspector.
4. Raw view displays the recorded fields only. Search/fold controls, if added, must include hidden descendants and report match count; not required for initial short traces.
5. Selecting a retrieved chunk opens readable excerpt + provenance. Available raw rank/score fields can expand without losing selected rank.
6. “Input” for a step cannot imply raw provider arguments. Parent query is explicitly labelled related turn context. Unsupported output/request fields say not recorded.
7. Timing bars use recorded durations with units and zero baseline. No fabricated waterfalls or additive step sums. keyword_search/score_fusion zero timings are labelled placeholders.
8. Raw trace may contain user content; show only within authorized session. No unredacted export or telemetry body capture by default.
9. Back/Close restores trigger focus and scroll. Desktop can use route-like inspection within /ask; mobile uses full-screen dialog. Avoid permanent share links until durable authorized IDs exist.
10. History reload without trace shows “No breakdown recorded,” not reconstructed data.

“Full breakdown” includes retrieval query/length/truncation/top_k/config metadata, every available step/details record, every returned document and optional scores/ranks, context counts/source labels/preview, generation model/timing/optional estimate and total. Full context, system prompts, hidden reasoning and unrecorded individual provider calls are expressly excluded.
If a source URL or page is absent, say unavailable. Do not expose local filesystem paths as external links.

## Evidence explorer
- Desktop facets and mobile radio sheet are two presentations of the same single-type selection. Counts remain global D11 facets; changing type resets offset.
- URL can encode source_type and offset; never encode private chat content. Browser Back restores filters and selected item.
- Sheet opens with active choice; changes are a draft until Apply. Escape/Close cancels draft. All types resets.
- Results are chunks; use readable title, exact source type/class, valid location and excerpt.
- Current API returns HTML page=1 as a metadata convention; render print page only for PDFs unless semantics are verified.
- Search is explicitly proposed and disabled/absent until whole-index backend support exists. Changing q resets pagination; debounce and cancel obsolete requests. Match count must not describe only loaded rows.
- Stable sorting is also proposed. Index order is current behavior, not a relevance ranking.
- Next/Previous use limit/offset and disable at boundaries. Keep previous data visible with busy state while loading, and ignore stale responses.
- Mobile cards keep source, location, excerpt and inspect action; no horizontally squeezed desktop table.

## Source detail
Show text as an excerpt, not a self-contained guideline. Preserve partial boundaries. Original link uses safe http(s) URL normalization; external navigation is disclosed. Null dates say not provided, not today's date. Raw metadata is secondary and may need public-safe allowlisting. Preserve exact ID in technical section; do not expose credentials or session identities.

## Research comparison
Current artifact-service records return comparable=false; do not enable cohort comparisons or trends based on client inference. A future comparison contract must verify dataset bytes/labels, split, run family, measurement contract, effective settings and index identity. Matching those fields is necessary, not proof of eligibility. Show dated archived result separately from currently served profile. Bars start at zero; nDCG 0–1 and p50 milliseconds in separate panels. Tooltip supplements, never replaces direct values and accessible table. Do not pool 54-query and 57-query experiments or label retrieval metrics as answer accuracy.
Keep existing CSV/JSON/chart export capabilities in the research area after verifying privacy and metric definitions.

## Evaluation / feature / dataset workspace
- Overview opens an evidence story with explicit artifact date and availability, then links to Evaluations / Features / Datasets / Q&A. No benchmark execution, profile-flip or patient-upload action.
- Every metric presents mean, successful count, expected slots and failed/skipped/errored status only when actually recorded. Never map unknown to zero. Slots and cases are different units.
- Metric grouping: ranking diagnostics / reviewed evidence / answer judgments / diversity / latency / pipeline checks. Provide definition, direction and denominator before coloring a delta.
- Scores such as nDCG use absolute score-point differences; relative change is separately labelled. Lower latency/error is favorable, not automatically “larger is greener.”
- Feature matrix selection changes the inspected archive/config, not active runtime. Declared, effective and observed settings must remain distinct. Missing effective provenance says unverified.
- Dataset selection resets incompatible run/case selection; URL contains allowlisted catalog identity, not arbitrary filesystem path or question text.
- Dataset filters are proposed catalog projections, not existing server capabilities. Respect actual case/turn/chunk/row units; never sum overlapping fixtures.
- Case drilldown has Expected vs Observed panels. A missing run/case binding disables observed results and explains why. Do not borrow latest-run records.
- Dataset split and label-confidence are facets, not certification. Manifest-marked human_reviewed and authenticated review are distinct.
- Compare is disabled for current comparable=false records. It must remain disabled until a future backend contract explicitly supplies a verified cohort; legacy report winner does not bypass this.
- Research mobile replaces wide metrics tables with stacked rows preserving denominators, values, status and definitions. Coverage bars preserve count scale, not medical-risk semantics.
- Export is local/read-only and must disclose content scope. Hosted export and Logfire linking require the existing permission/destination constraints; never add a default raw SDK-body export.

## States
- Empty index: readiness is unavailable, not zero-quality.
- No results: search/filter succeeded with zero matches; preserve filters and offer reset.
- Unauthorized: keep the private-lab boundary, explain access requirements, and do not repeatedly auto-retry; server remains authoritative. No anonymous fallback is introduced.
- Rate limit: show safe message, retry interval if supplied, preserve draft.
- Service error: safe error code + request ID, not raw exception text. Retry only read requests automatically; do not silently duplicate chat submissions.
- Stale: last successful data remains labelled stale with known timestamp only. Unknown freshness stays unknown.
- Loading: aria-busy and static skeleton/text, respect prefers-reduced-motion.
- Selected: rule + textual state + aria-selected/current where applicable, not color alone.

## Responsive and accessibility acceptance
- 1440 desktop / 390 mobile assets; verify 320, 390, 768, 1024, 1440 and 200% zoom in implementation.
- Collapse sidebar before compressing reading text. Mobile turn index becomes an accessible disclosure.
- Keep corpus category labels, counts and axis meaning; research charts stack vertically with the same scales and row order.
- Dialogs: accessible name, initial focus, focus trap, Escape, background inert, restoration.
- Minimum targets 44 px; mobile radio rows need 44 px runtime hit regions even where compact rows are drawn.
- Text contrast ≥4.5:1; control/focus distinction ≥3:1. Dividers can be subtle but cannot be sole focus/selection indicator.
- Semantic landmarks/headings/tables, skip link, labelled inputs, proper tab keyboard behavior and visible focus.
- Screen-reader equivalents for charts and completion state. Avoid repeatedly announcing streaming tokens.
