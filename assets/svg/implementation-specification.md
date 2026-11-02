# Fieldnote implementation specification

**Status:** repository-grounded specification. **P01–P10 are implemented offline** in the shared working tree; authenticated deployment/release verification remains pending. See [P10 readiness](../../docs/plans/20261101-p10-readiness.md), [continuation handoff](continuation-handoff.md) and the [deployment pickup brief](../../docs/plans/20261101-deployment-pickup.md).
**Scope:** redesign of the existing private research application, not a framework rewrite, public rollout or benchmark run.

Read with the [file/ownership map](implementation-map.md), [execution plan](implementation-plan.md), [interaction specification](interaction-spec.md), [data map](screen-data-map.md) and [SVG index](README.md). The specification governs implementation contracts; SVGs govern visual intent. If either conflicts with source or owner decisions, stop that subtask and document the discrepancy.

## 1. Authority and non-negotiable boundaries

1. Follow root `AGENTS.md`: analyze actual files, present the bounded code plan for approval, minimize scope and introduce no unnecessary abstractions.
2. Follow `docs/plans/migration/decisions.md`, especially D01 private lab, D02 public/synthetic data, D07 no clinical-suitability claims, D09 CLI/YAML-first execution and D10 Pydantic Evals plus primary Logfire UI. Re-read the latest relevant approvals before changing behavior.
3. Retain SvelteKit 2 / Svelte 5, TypeScript, FastAPI, existing RAG and ingestion boundaries, Chart.js, cookie/session behavior and metric definitions. No dependency/lockfile change is required by this spec.
4. Do not modify providers/models/prompts/embedding defaults, corpus/index bytes, evaluation winner rules or comparison eligibility to make a screen look better.
5. No web run launcher, live feature switches, patient uploads, paid calls, hosted exports, automatic promotion, manufactured confidence intervals or full provider-call instrumentation.
6. No credentials, reviewer personal details, private sessions or raw SDK bodies in shipped assets, browser configuration, reports, logs or telemetry. Stable dataset/case/hash identifiers are application joins, not telemetry identities.
7. Current `EvaluationService` returns `comparable=false` and null cross-run averages. Preserve that behavior. Matching formats/counts/paths does not establish a comparison cohort.

## 2. Evidence baseline and consequences

### 2.1 Verified implementation anchors

| Concern | Existing source to retain / adapt |
|---|---|
| Composition / middleware / route wiring | `src/app/factory.py:create_app`, `lifespan`; `src/app/middleware/auth.py`; `src/app/security.py:AuthContext` |
| Evaluation artifact reads | `src/evals/artifact_service.py:EvaluationService` |
| Evaluation HTTP surface | `src/app/routes/evaluation.py` |
| Experiment configs and raw reports | `src/app/routes/experiments.py`; `src/experiments/config.py`; currently no route-level authenticated-state check, so no-key middleware bypass exposes them |
| Dataset normalization / diagnostic semantics | `src/evals/dataset_builder.py:_normalize_case_record`, `_dataset_diagnostics` |
| Required answer metric vocabulary | `src/evals/assessment/l6_contract.py:REQUIRED_ANSWER_METRICS` |
| Newer report completeness semantics | `src/evals/pydantic_tasks.py:ReportCompleteness`, `project_report` |
| Document listing / metadata | `src/ingestion/indexing/listing.py:DocumentListingMixin`; `src/app/routes/documents.py` |
| Frontend networking | `frontend/src/lib/utils/api.ts` |
| Current metrics / types | `frontend/src/lib/utils/metric-definitions.ts`, `eval.ts`, `frontend/src/lib/types.ts` |
| Existing stateful pages | `frontend/src/routes/+page.svelte`, `eval/+page.svelte`, `experiments/+page.svelte`, `documents/+page.svelte` |
| Safe rendering | `MarkdownRenderer.svelte`, `frontend/src/lib/utils/url.ts`, markdown tests |

Source wins over stale context notes: for example `.planning` contains older framework/middleware descriptions; current package and factory code are authoritative. Current `frontend/playwright.config.ts` defaults to port **4173**, despite older docs mentioning 5174.

### 2.2 Artifact truth used by the designs

- D11 local index: 2,473 chunks, comprising PDF 1,306 / HTML 597 / reference CSV 460 / Markdown 110; not a publication count.
- Local archive `experiments/outputs/medical_semantic_chunking_exp_report.json`: timestamp 2026-04-18; baseline 57 queries and six answer metrics. Successful metric slots 268, failed 74, expected 342. Faithfulness mean .9798534799 with 15 successes and 42 errors; answer relevancy .8594487734 with 25 successes and 32 errors.
- All four archived variants are degraded. The report's winner is a historical field, not current eligibility. Underlying case-run directories are absent locally.
- The report stem differs from `experiments/medical_semantic_exp.yaml`. Existing result discovery matches stems exactly; the new UI must not assume they join automatically.
- All-query fixture currently has 57 questions (regression 17 / test 23 / dev 17); current expanded fixture has 54, all also present in All57 by exact query text. Current file overlap is not historical byte/label identity.
- Frozen review set: 8 cases, 7 answerable / 1 unanswerable. Manifest declarations say human_reviewed; this design pass did not authenticate reviewers or perform a fresh manifest verification.
- Existing generic step/L6 record APIs read latest; selected-run L6 details exist separately. Historical UI must never silently substitute latest evidence.
- Default backend image copies `src/`, two config files and `experiments/`, **not `tests/fixtures/`**. A development-only fixture catalog will otherwise disappear in the runtime image.

## 3. Target product and route map

### 3.1 Routes

| Browser route | Required experience | Compatibility / migration |
|---|---|---|
| `/` | Research-first workspace, selected archived coverage story, research pathways, corpus context, Q&A workbench link | Replaces chat landing only when `/ask` and tests are ready |
| `/ask` | Existing Q&A capabilities plus individual turn showcases and deliberate inspection | Move existing chat code before visual extraction; preserve backend cookie/session |
| `/research` | Redirect to `/`, preserving safe relevant search state where applicable | No duplicate workspace |
| `/research/evaluations` | Artifact selector, coverage, definitions, identity, comparison-unavailable state | Link to existing `/eval` for full L0–L6 diagnostics |
| `/research/features` | Declared variant matrix, observed archived metrics, capability/evidence map | Link to existing `/experiments` and `/eval/ablation`; no live switches |
| `/research/datasets` | Catalog, current-file provenance, splits, label/review distinction, overlap | New read-only catalog support |
| `/research/datasets/[datasetId]` | Deep-linkable selected catalog entry and case expectations | IDs must be allowlisted logical identifiers, never paths |
| `/research/methodology` | Curated metric/identity/measurement explanation with links to existing help/pipeline pages | Static documentation, not new analytical functionality |
| `/evidence` | Current chunk list with corrected global facets and labels | `/documents` remains an alias/redirect only after parity |
| `/evidence/[id]` | Full chunk excerpt/provenance; safe original link | Preserve exact store ID; do not reinterpret as publication ID |
| `/eval`, `/eval/ablation`, `/experiments` | Retained diagnostic workflows and exports, corrected misleading labels/formatting | Do not redirect these to simplified screens and lose functionality |
| `/health`, `/settings`, `/help`, `/docs/pipeline` | Retained and discoverable under Research / More | `/settings` remains read-only |

Top-level nav: Overview / Ask / Evidence / Research. Research subnav: Workspace / Evaluations / Features / Datasets / Methodology. On diagnostic routes keep a visible path back to the workspace and the selected artifact. Mobile uses labelled disclosures rather than squeezing all navigation into a row.

Backend additions use `/research-data/...`, **not the same paths as browser `/research/datasets` routes**. Preserve existing API base configuration; deployment must provide an explicit private API origin/prefix. This avoids introducing a new HTML/API pathname collision.

### 3.2 Selection and URL state

- Research selection is a discriminated value: `archive` with report ID + report revision, or `run` with backend run directory + available revision/identity. A raw run path from an archived JSON record is not authorization to fetch arbitrary files.
- Evaluation URL may encode `artifact_kind`, `report_id` or `run`, and `variant`. Dataset URL may encode catalog ID, revision, split and ordinal selection. Only allowlisted enum/ID values are accepted.
- Never place questions, answers, raw prompts, credentials or source bodies into URLs.
- A current catalog fixture can be linked as the **declared dataset reference** of an archive. That does not bind historical results to current cases.
- Initialize requested selection from URL before dependent fetches. Current legacy eval loads latest first and can populate `data` while a historical selection is pending; this is a migration hazard, not desired fallback. Loaded artifact identity—not a pending selection label—owns every rendered metric and drilldown. An explicit run must load directly even if it is outside the current history page.
- Ignore late responses when selection changes. Refresh targets the selected artifact; on missing requested artifact show the missing state, never relabel latest without explicit user action.

## 4. Minimal implementation architecture

Use existing modules and small explicit additions, not a general catalog framework.

1. `src/evals/research_catalog.py` (new): fixed allowlist and bounded file-backed projections for the known fixture/reference/review artifacts. Plain functions and literals; no plugin registry, dynamic discovery, provider imports or ingestion calls.
2. `src/app/schemas/research.py` (new): Pydantic models for the **new** catalog HTTP boundary. Do not migrate all existing schemas.
3. `src/app/routes/research.py` (new): authenticated read-only catalog endpoints. Route inclusion in factory only; no lifespan/provider changes.
4. Extend existing experiment result endpoints with additive provenance, not a second parallel report service.
5. `frontend/src/lib/utils/research.ts` (new): pure known-archive adaptation only. Keep shared finite-number formatting, delta arithmetic and any reused coverage validation in existing `eval.ts`, with unit/direction definitions in `metric-definitions.ts`; do not create a second formatter/coverage engine. Unknown schemas fail to an unsupported/raw-inspection state.
6. Add frontend types to current `types.ts`, API methods to `api.ts`; no new client library or state framework.
7. Extract only components needed by more than one screen or with genuinely independent behavior. The file map lists a small initial set; do not mechanically split every SVG group.

## 5. Access, privacy and deployment gates

### 5.1 Required behavior

- Keep all research/catalog content inside the private lab. New catalog handlers require authenticated request state, as evaluation handlers already do; merely relying on middleware's no-keys bypass is insufficient.
- P01 now protects experiment list/results/config with the existing authenticated-state policy. The deliberate401 behavior for unauthenticated/no-key callers is verified in P01 route tests and documented in its report. Keep it; do not add browser credentials to work around it.
- Existing `/config` already performs an explicit authenticated-state check, like evaluation routes. `/documents` remains a middleware-only legacy surface until its separately approved role/access policy is applied. G-AUTH release verification must cover both and prevent direct no-key document access outside the approved private boundary; public exposure is not an accepted fallback.
- Use existing `AuthContext`. Do not invent new role names or silently grant all browser visitors operator access. Route-level role policy is an owner decision under audit F-02.
- No API key in `VITE_*`, browser storage, URL parameters, static JSON, test screenshots or client source.
- Do not weaken existing middleware/evaluation checks to make the UI demo work.
- Operator gateway/server auth delivery is unresolved. Recommended delivery is the owner's existing private authenticated boundary, with credentials attached server-side and direct backend access restricted. Do not create a new login/BFF/auth system in these slices without a separately approved concrete design.
- Mocked offline browser tests may exercise UI while auth delivery is pending. They are tests, not a production fixture mode or evidence of authenticated end-to-end readiness.
- An authenticated deployment verification is a **release blocker**; it does not block pure normalizer/catalog tests or other offline work.

### 5.2 Content policy

Catalog cases initially expose only the explicitly approved public/synthetic query/conversation fixture projections. Review manifests expose bounded counts/status declarations only, not reviewer IDs or full frozen documents. Raw corpus lives behind existing chunk APIs. CSV catalog metadata exposes inventory/column information; no lab-value interpreter is created.

Local export and external trace links retain current permission constraints. Link out to Logfire only when a genuine authorized recorded URL exists; otherwise say unavailable. No new SDK-body instrumentation or automatic hosted export.

### 5.3 Packaging

Fixture availability is deployment-dependent until packaging lands; initial API entries may legitimately be missing. Available-fixture acceptance must use temporary/mock inputs first and a packaged image later—never hardcoded frontend counts.

For the first complete private deployment, copy **only the six named approved fixture JSON files** into the image at the corresponding `tests/fixtures/` paths, or an owner-approved equivalent fixed read-only location with the same tests. Do not copy the entire test suite or `.env`/local artifacts. Keep review/CSV/index data mounted through the existing data volume; absent mounts produce unavailable entries.

The six files are `golden_queries.json`, `golden_queries_comprehensive.json`, `golden_queries_diverse.json`, `golden_queries_expanded.json`, `golden_queries_all.json` and `golden_conversations.json`, each under `tests/fixtures/`.

The default plan is explicit `Dockerfile` COPY statements for those six files, after owner confirmation that these public/synthetic artifacts may be bundled. No fixture regeneration or data migration. Container tests must prove behavior both with fixtures present and absent. If packaging approval is deferred, ship the catalog's unavailable state and mark dataset deployment incomplete rather than baking invented summaries into the frontend.

## 6. API and projection contracts

The report-provenance contract in §6.1 is implemented by P01; later catalog/drilldown/facet contracts remain proposed. New handlers are GET-only. Use existing structured error handling and request IDs; safe details only. Sync bounded file reads may use normal `def` routes/thread-pool execution. No cache is required initially; when introduced it must be keyed to actual bytes/revision, not path alone.

### 6.1 Experiment report provenance — additive

Retain `GET /experiments`, `GET /experiments/{experiment_name}/results` and `/config`.

Add to report-list entries:
- `report_id`: the validated filename stem accepted by `/results`.
- `schema_kind`: a recognized literal, initially `legacy_feature_addition`, or `unsupported`.
- `report_sha256`: SHA-256 of the exact raw report bytes, or null if unavailable.
- `config_ref`: explicit known association when established, otherwise null. This is a declared association, not effective-runtime proof.

Add reserved `_artifact` metadata to the result object without changing existing root `baseline`, `variants`, `config`, `winner` fields:

```json
{
  "_artifact": {
    "report_id": "medical_semantic_chunking_exp",
    "report_sha256": "<64 lowercase hexadecimal characters>",
    "schema_kind": "legacy_feature_addition",
    "availability": "available",
    "config_ref": "medical_semantic_exp",
    "config_binding": "explicit_archive_association",
    "case_records_availability": "not_exposed_by_report_api",
    "comparable": false
  }
}
```

Requirements:
- Current report API identity is filename/path-based only; `experiment_name` is not a byte identity. The frontend must wait for this additive provenance contract before treating an archive revision as verified.
- Parse and hash the same byte buffer, capped at5 MiB by reading at most cap+1 bytes before parsing; do not reread between hashing and parsing. Apply the explicit authenticated-state check to list/results/config as specified above.
- Constrain filename and root containment, including symlink escape. Unknown reports return 404; malformed/oversized known reports return a safe error or unavailable list entry, never an empty valid-looking report.
- A static explicit association for this known config/report mismatch is acceptable. Do not fuzzy-match names or infer every alias. Do not reinterpret old config through current defaults and call it effective settings.
- Preserve the historical `winner` as raw archive data, but new display does not certify it. Keep `comparable=false`.
- `case_records_availability=not_exposed_by_report_api` is an API capability statement, not proof the user's filesystem lacks all case files. Designs' absence observations apply only to the inspected checkout.
- No generic arbitrary report-path parameter. Do not follow `run_dir` strings embedded in an archive to open files outside an approved evaluation root.

### 6.2 Catalog endpoints

| Endpoint | Purpose | Bounds / semantics |
|---|---|---|
| `GET /research-data/datasets` | Summaries of fixed catalog entries and current overlap observations | All entries have independent availability; missing one must not erase others |
| `GET /research-data/datasets/{dataset_id}` | Current-file metadata/provenance/split summaries | Unknown logical ID 404; no filesystem path input |
| `GET /research-data/datasets/{dataset_id}/cases` | Bounded approved case projections | `revision` required; `limit` default20, 1–100; `offset` >=0; no arbitrary filters in first backend slice |

Allowlisted logical IDs:
`golden-original`, `golden-comprehensive`, `golden-diverse`, `golden-expanded`, `golden-all`, `golden-conversations`, `d11-review`, `lab-reference`, `d11-index`.

Catalog entry fields:

```text
catalog_id: fixed logical ID
label: string
kind: query_fixture | conversation_fixture | review_dataset | reference_csv | retrieval_index
availability: available | missing | malformed | unsupported | inventory_reference
availability_reason: fixed enum or null
origin_ref: safe repository-relative known source reference; never absolute host path
revision_sha256: actual source-byte digest or null
record_unit: question | conversation | case | row | chunk
record_count: nonnegative integer or null
turn_count: nonnegative integer or null
split_counts: map<string, nonnegative integer> or null
label_confidence_counts: map<string, nonnegative integer> or null
raw_review_status_counts: map<string, nonnegative integer> or null
review_status_missing_count: nonnegative integer or null
review_authority: not_assessed | manifest_declared_not_authenticated
case_projection: available | summary_only | unavailable
inventory_ref: existing API reference or null
```

Semantics:
- `revision_sha256` fingerprints current bytes only; no clinical or historical identity assertion.
- Missing fields stay null/missing with explicit counts; do not populate raw review_status with normalized defaults and pretend it was stored.
- For query fixtures parse the named `golden_queries` array; for conversations parse `golden_conversations` and preserve conversation vs stored-turn counts. Exclude stopword/test-document support arrays from case count.
- For review set, allow only aggregate review/answerability declarations. Do not return reviewer IDs, manifest contents or the 1.4 MB frozen corpus as catalog payload.
- D11 catalog entry initially uses `inventory_reference` and the existing `/documents` summary for live total/counts. Do not start a second Chroma client or scan SQLite directly from this new catalog module. If index API is unready, say so; do not reuse a stale fixed 2,473 as a live count.
- Reference CSV row count is not the served reference-chunk total. Preserve separate values and source labels.
- Initial supported-file size cap: 5 MiB per JSON/CSV; record cap 10,000; public field string cap 16,000 characters. Treat oversized/invalid entries as unavailable, not successful truncation. Current inspected files fit these limits. No schema silently upgrades itself when a cap is exceeded.
- Use `src/config/paths.py`'s trusted constants, without calling `ensure_dirs()`: fixture root=`PROJECT_ROOT / 'tests' / 'fixtures'`; review root=`DATA_DIR / 'evals' / 'review'`; reference root=`DATA_RAW_DIR / 'LabQAR'`. Known report root remains `PROJECT_ROOT / 'experiments' / 'outputs'`. These derive from installed code/trusted settings, never CWD or an HTTP parameter. Docker's `/app` layout must satisfy those same roots; approved mounted data is not copied into frontend/static.
- Every logical ID maps to a literal known filename under its approved root. Resolve/check containment at read time; require a regular file, reject symlink escape and read at most cap+1 bytes before parsing. Hash/parse the bytes actually read, not a prior stat snapshot. Tests replace root constants with temporary directories; no extra root-selection config framework is required.
- Do not allow a request to choose a file, glob or directory. Missing roots/files stay missing; catalog reads must not create them.
- Changes to these limits require tests/documentation, not a new configurable parsing framework.

Overlap observations:

```text
left_catalog_id / left_revision
right_catalog_id / right_revision
method: exact_stored_query_text
left_unique_query_count / right_unique_query_count
intersection_unique_query_count
normalization: none
near_duplicate_status: not_assessed
```

Compute a set intersection from actual stored query strings, with both revision digests. The known54 overlap is an acceptance fixture, not a hardcoded response. Do not call it independent sample count or label equality. Do not mix this exact overlap with the existing source-family diagnostic unless clearly named separately.

Case page shape:

```text
catalog_id, revision_sha256, total, offset, limit
items[]:
  locator: { revision_sha256, source_ordinal }
  source_case_id: stored approved identifier or null
  question: string or null
  expected_keywords: string[] | null
  expected_source_labels: string[] | null
  split / difficulty / query_category / source_family / topic: string | null
  label_confidence: string | null
  raw_review_status: string | null
  normalized_review_status: string | null
  stored_turns: approved minimal conversation projection or null
```

A locator is valid **only inside that exact revision**; ordinal is not a globally durable case ID. Case request reads/hash/parses the same file snapshot. If requested revision differs, return409 with safe code `catalog_revision_changed`; UI resets selection after an explicit refresh. Do not automatically join a fixture case to an old report by ordinal or question text. Summary-only entries return a documented unavailable response for case access, not a fake empty successful dataset.

### 6.3 Run-scoped drilldowns — additive, no latest substitution

Extend existing GET methods with optional `run_dir` query selection while retaining no-argument latest behavior:
- `/evaluation/steps/{stage}`
- `/evaluation/steps/{stage}/records`
- `/evaluation/l6/records`

Preserve `/evaluation/answer-quality/{run_dir}`. Add actual `run_dir` in scoped responses so callers can verify selection. Bound record `limit` to1–500 and offset where introduced; read JSONL incrementally up to requested bounded data and reject oversized malformed records safely. Do not interpret old archive `run_dir` paths as directory identifiers under this API.

A small resolver inside `EvaluationService` should:
1. Accept a single directory name, rejecting `.`, `..`, separators, traversal and symlink escape.
2. Resolve strictly under configured evaluation root; do not create missing directories.
3. Select latest only when no run was explicitly requested.
4. Return404 for a missing explicit run; never fall back.
5. Preserve diagnostic compatibility status and `comparable=false`.

Expose an explicit UI/view-model binding state: `historical_binding = not_established | verified`. Initial archive-to-current-fixture links always use not_established with a fixed reason (`declared_path_only`, `case_records_unavailable` or `identity_unverified`). Do not silently omit the state or imply binding through adjacent panels. No first-slice response may produce verified without a separately implemented/tested binding contract.

Do not return observed case evidence in the dataset inspector until both dataset revision and a stable case binding are genuinely available. Initially, the archived report's observed panel remains unavailable; selected run records can be inspected independently without asserting a catalog-case join.

### 6.4 Documents — additive facets and labels

Retain `/documents` limit/offset/source_type and existing fields. Add:
- `global_source_type_counts`: counts from the full in-memory metadata mirror, independent of selected source_type.
- Per item optional `canonical_label`, `display_label`, `logical_name`, `source_url`, `domain` from existing metadata, without fabricating values.
- Public-safe explicit `index_identity` derived from verified existing metadata if available; null otherwise. A label D11 is not a newly verified fingerprint.

Frontend must switch to global facets only after backend fields/parity land. If talking to an old backend, show unavailable unfiltered counts or only the honest existing filtered view; never fabricate an All total from the selected page.

Existing `source_type_counts` retain their current filtered semantics for compatibility. Selected result `total` remains filtered. All facet uses full count, not filtered total. Unknown source types remain inspectable; absent dates remain absent. HTML/Markdown page=1 is not rendered as a print-page claim. No whole-index text search or new sorting is required initially; omit the proposed control until separately implemented.

## 7. Frontend view models and arithmetic

### 7.1 Metric display contract

Use explicit metric definitions with label, unit, direction and definition ID:
- Ranking diagnostic, reviewed evidence, answer judgment, diversity, latency and processing-quality fields are distinct families.
- nDCG/MRR display decimals on0–1, never probabilities of correctness.
- Latency milliseconds, lower is better. Error rates lower is better. No generic “larger is positive” class.
- Count is not a percentage; source entries are not unique publications.

Pure normalizer output per metric:

```text
metric_key / definition_id / label / unit / direction
mean: finite number or null
measured_slots: nonnegative integer or null
expected_slots: nonnegative integer or null
failed_slots: nonnegative integer or null
skipped_slots: nonnegative integer or null
errored_cases: nonnegative integer or null
expected_basis: recorded | legacy_one_slot_per_query | unknown
coverage_state: complete | partial | not_recorded | inconsistent
reason_codes: fixed enums[]
```

Rules:
- Exclude booleans, NaN and Infinity. Invalid/out-of-domain means are unavailable with reason, not clamped into plausibility.
- For the recognized legacy57 archive, expected slots use the explicit adapter rule one answer metric per declared query; label the basis. Count and error_count map to measured/failed metric slots. Do not derive errored **cases** from failed **metric** counts.
- Do not make newer expected/measured/failed/skipped/errored semantics fit the old schema by inventing zeros. Unknown fields remain null.
- Inconsistent counts remain visible as inconsistent and do not earn a completed badge or fabricated residual category.
- Mean remains a reported mean on successful measurements; no raw case data means no recomputed distributions/intervals.
- Recognized baseline: factual_accuracy .9965/57/0; completeness .7088/57/0; clinical_relevance .9772/57/0; clarity .9193/57/0; answer_relevancy .8594/25/32; faithfulness .9799/15/42. Every row has57 expected; totals268 measured +74 failed =342. Error rate74/342=21.6%.

### 7.2 Deltas and feature claims

- Absolute difference is variant−baseline in the metric's units. nDCG .7008913797−.6596215032 =+.0413.
- Relative change is `(variant−baseline)/abs(baseline) ×100`, displayed separately; this positive baseline yields+6.3%. Baseline zero or unavailable means relative change is not available, not Infinity or an invented100%.
- Favorability follows direction; it does not establish statistical significance or promotion.
- A selected feature row is labelled Inspecting, not Winner. Preserve all four degraded archive statuses.
- Declared settings come from the archived report's config; effective runtime settings require a genuinely corresponding record and are otherwise unverified.
- Optional capabilities/dependencies are curated with code references. Do not let UI toggles change active configuration.

### 7.3 Availability/state model

For each independently loaded panel use idle/loading/available/empty/missing/unauthorized/error/stale/unsupported as appropriate, not one global boolean. New requests must not erase usable independent data. Protected data is not cached/shared across authorization contexts. Dates are provided timestamps only; no refresh date inferred from mtime.

## 8. Q&A and evidence implementation behavior

### 8.1 Routing and lifetime

Move current chat page to `/ask` first with its behavior intact; update chat-specific tests together. After parity, create the research root. Conversation/turn display state should survive ordinary in-app navigation in memory without introducing persistent storage. If a small app-level context is needed, keep it session-local and specific to this conversation, not a generic state framework. No localStorage trace persistence.

History reload still returns role/content/timestamp only. Label source/trace unavailable rather than reconstructing them. New conversation confirms DELETE semantics; no saved-session library is introduced.

### 8.2 Streaming correctness

- User text limited to2,000 characters; label textarea, IME-safe Enter handling, Shift+Enter newline.
- Completion requires the backend terminal `done` event without error. EOF without terminal is incomplete; partial content stays explicitly incomplete.
- Build a small current-contract SSE decoder with buffered UTF-8/frame handling; parse data frames across chunk boundaries and terminal error fields. Unsupported/malformed frames cannot turn partial output into success. No auto-resubmit/reconnect that duplicates chat turns.
- Preserve existing request generation/AbortController guards, cancellation and per-session backend admission. New-history-clear cannot race an active stream into a mixed transcript.
- Announce completion/errors, not every token; auto-follow only at tail. Aborting browser fetch does not prove immediate provider cancellation.
- Existing URL construction is a real defect for relative private bases, not a new capability claim. Supported browser forms are an absolute HTTP(S) API base (including an explicit gateway prefix), a root-relative private prefix resolved against current origin, and the existing empty-base behavior resolved against current browser origin. Normalize only trailing separators; reject non-HTTP(S) schemes. SSR must not invent a browser origin or share user state.
- API URL construction must resolve correctly for configured absolute API base or explicitly supported private same-origin prefix; `chatStreamUrl` cannot call `new URL` on an unresolved relative path. Tests cover base URL and include_pipeline query composition without changing credential policy.

### 8.3 Turn inspector

Preserve actual PipelineTrace semantics: retrieval query/options/steps/documents, context counts/source labels/200-character preview, model/timing and optional estimate. Show every recorded optional field on demand; null differs from zero and skipped.

The semantic_search interval wraps retrieval work; keyword_search/score_fusion zeros are placeholders. Do not create waterfalls, context durations, exact token use, cost, retry trees, private reasoning or provider requests from these data. Full breakdown is full **recorded RAG** breakdown.

Use existing `PipelinePanel.svelte` / `DocumentInspector.svelte` behavior where safe; refactor presentation rather than retaining two competing inspector systems. A native/disclosure-based implementation is acceptable; SVG diagrams are not required DOM.

## 9. Visual, responsive and accessibility requirements

- Use `00-design-system.svg` tokens: paper#F7F4ED, ink#182D32, teal#006B61, rust#B34322, blue#375E91, secondary#506469. Preserve legacy CSS variable aliases until old routes migrate.
- Georgia/Times editorial headings and Arial/Helvetica body; no external font dependency.
- Desktop max content1344 with48 margins at1440, mobile24 at390; reflow at640/1024 rather than scaling text down.
- Native forms, headings, tables, buttons, landmarks, skip link and labelled navigation. Real data table accompanies chart output. Coverage bars can be semantic CSS/SVG figures with labels; Chart.js is available but not mandatory for simple counts.
- 44px targets; visible focus; dialogs named, focus-trapped, Escape-dismissable, background inert and focus/scroll restored.
- Text contrast≥4.5:1; non-text/focus≥3:1 where required. Light dividers cannot be the sole interactive boundary or state marker.
- At320/390/768/1024/1440 widths and200% zoom retain values/units/denominators and selected context. Wide evidence/metric tables become stacked rows, not unreadable squeeze layouts.
- No shimmer/mandatory animation; respect reduced motion. Streaming uses restrained status announcements.
- Preserve semantic distinction: green/teal is action/selection/measurement completion, not clinical approval; rust marks engineering limits, not patient risk.

## 10. Acceptance scenarios (required)

| ID | Scenario / observable result |
|---|---|
| AC01 | Root presents private lab with Evaluations/Features/Datasets/Q&A; no clinical/public or live-run claims |
| AC02 | Local archived baseline renders268/342 measured and74 failed; faithfulness15/57 and42 errors beside .9799 |
| AC03 | Missing, boolean/non-finite or inconsistent measurements never become zero or success |
| AC04 | Feature matrix displays .6596/.6596/.7009/.7009; +.0413 and+6.3% separately; no eligible-winner assertion |
| AC05 | DatasetAll57 splits17/23/17 and confidence43/14; raw review status absence is visible |
| AC06 | Exact current-file overlap54 shown with both revisions; not independent samples/historical identity |
| AC07 | A fixture revision change between summary and cases returns409 and invalidates stale case selection |
| AC08 | Real LDL-C fixture expectations shown; absent archived observations remain unavailable, not fake failures |
| AC09 | Explicit historical run request never loads latest data; response run ID must match selection |
| AC10 | comparable=false disables comparison/trends; legacy winner/format matching cannot override |
| AC11 | PDF facet1,306 results while All stays2,473; existing filtered facet contract preserved |
| AC12 | Q&A streaming success/error/cancel/truncated EOF remain distinct; source/trace unavailable after reload is honest |
| AC13 | Inspector exposes actual optional trace fields and placeholder timings, not invented provider calls |
| AC14 | All existing diagnostic/config/help/export capabilities remain reachable; chat tests now target/ask |
| AC15 | Catalog missing files/mounts/unsupported schema render honest partial availability; default image handles approved fixture packaging |
| AC16 | Authenticated research boundary enforced; no credential in browser bundle; direct unauthorized requests fail |
| AC17 | Keyboard/mobile/zoom/screen-reader journeys preserve focus, units, counts and chart alternatives |

## 11. Validation and release readiness

Use [implementation-plan.md](implementation-plan.md) for staged tests and approvals. Existing baseline checked during planning:58 focused evaluation/history/new-route tests passed; frontend check previously passed0 errors/0 warnings. Those are existing-code observations, not new feature acceptance.

Auth smoke tests must use isolated/stubbed provider/index state or an already-approved private runtime, not an unapproved real-corpus boot. Audit F-03 records inherited additive collection-metadata writes during startup; this plan does not authorize fixing that issue or mutating D11 to validate a UI.

Release readiness requires approved auth delivery, fixture packaging, offline backend/frontend gates, browser + accessibility review, safe/private data verification and no unapproved index/provider/default changes. Failure of a new or inherited test must be reported with provenance; do not change benchmark semantics or lower quality gates to clear it.

## 12. Decisions reserved for owner / implementation review

- Exact private gateway/server credential delivery and operator role policy; no public fallback.
- Approval to bundle the six approved public/synthetic fixture files in runtime image.
- Working name Fieldnote; temporary product title may remain existing until approved.
- How far to restyle legacy diagnostic routes before initial release; function preservation is mandatory.
- Any future durable turn storage, catalog-to-observed case binding, verified comparison cohort, hosted export, search or provider-call timeline requires a separate specification and approval.
