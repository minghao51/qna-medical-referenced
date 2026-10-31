# Maintainability and operational clarity: implementation specification

**Status:** proposed handoff; no implementation authorized by this document alone.
**Baseline:** `66cb168`; source verification and corrections are in
[maintainability-verification.md](maintainability-verification.md).
**Start here:** [agent pickup instructions](maintainability-agent-handoff.md).

This package supersedes the earlier conversational recommendations where they
conflict, but does not supersede the migration decision register or approve
previously deferred scope. Follow-ups F-01–F-11 remain tracked in
[migration/20261030-audit-followups.md](migration/20261030-audit-followups.md).

## 1. Objective and success criteria

Make the repository easier to operate and change without changing retrieval
quality, provider defaults, artifact identity, history semantics, or public API
contracts incidentally. Deliver small independently reversible patches with
explicit evidence. No full rewrite, universal file-size rule, general framework,
new dependency-injection container, or mass renaming.

Completion means:

- One documented offline test command shared by local use and CI; coverage is
  explicit and project-wide; provider opt-ins are independent and tested.
- Published test/docs commands refer to existing paths and describe actual gates.
- HTTP artifact reads are root-confined; L6 response memory is bounded while
  exact count semantics are retained; request-size/error contracts are specified.
- SSE parsing has isolated fast tests and cannot silently treat truncation as success.
- Assessment helpers have cohesive homes without changing stage ordering,
  dependency override seams, cache eligibility, identities, or failure artifacts.
- Deployment examples clearly separate source-mounted development from immutable
  image deployment. Changes that need policy/dependency/data approval are not
  smuggled into these improvements.

## 2. Invariants and non-goals

1. Keep D11 default path, `medical_docs`, `baseline`, single production worker,
   current generation/embedding/judge choices and optional-dependency boundaries.
2. No live provider/embedding calls, hosted export, corpus download, index rebuild,
   R2 remote mutation, data backfill, or legacy-data movement during this project.
3. Never print secrets, API key hashes, endpoint account IDs, PHI/chat content, or
   raw provider exception messages. Credential diagnostics say set/missing only.
4. No admin pages or role enforcement without renewed owner approval. Auth and
   role policy are deliberately different workstreams.
5. Keep `set_index_metadata` authoritative replacement for migration; preserve
   provenance under overlay paths. Do not bless unknown metadata by backfilling
   it from current settings.
6. Freeze artifact schemas, identity/fingerprint inputs, replay eligibility,
   atomic publication order, terminal stream event semantics, cancellation and
   session-admission behavior during structural moves.
7. No dependency/lock changes until explicitly approved for that slice. Respect
   existing Logfire, adapter, pilot, and model-download approval gates.
8. Do not create a README under ignored `data/` or force-add runtime artifacts;
   describe the layout in tracked `docs/data/` instead.

## 3. Sequencing and ownership

Recommended order:

```
M0 reproduce baseline
  -> M1 independent opt-ins/test hygiene
  -> M2 shared commands and coverage -> M3 dependency-audit repair
  -> M4 documentation/config truth-sync
  -> M5 artifact containment/L6 bounds -> M6 HTTP limits/error contract
  -> M7 frontend parser tests (dependency approval)
  -> M8 assessment extraction -> M9 targeted remaining cohesion
  -> M10 serving metadata invariants
  -> M11 strict sync integrity (policy approval)
  -> M12 deployment hardening (deployment approval)
```

M4 docs can proceed alongside M5 after command interfaces are fixed. M7 can run
alongside M8 with disjoint ownership. M8 and M10 must not concurrently edit
runtime/index seams. M3, M7, and M12 may touch dependency/configuration files;
serialize their integration. Assign a single owner to each file, especially
`pyproject.toml`, workflow files, lockfiles, `docs/README.md`, and settings.
No worker commits, resets, stashes, remote actions, or dependency installation
unless explicitly delegated. Parent owns approval, final gates, commits and push.

Priority: M1–M3 prevent misleading tests; M5/M6 close concrete security/resource
gaps before cosmetic refactors. M8 is valuable only once behavior is captured.
M9–M12 are separable follow-ups, not prerequisites to claim the earlier slices done.

## 4. Work packages

### M0 — Establish a reproducible, safe baseline

**Own:** evidence only; scratch output under `/tmp`.

- Read `AGENTS.md`, `.planning/codebase/*`, existing structural roadmap, migration
  decision register/current pickup brief, and this package. Follow applicable
  decisions instead of treating historical handoffs as current authorization.
- Record HEAD, clean/dirty status and pre-existing changes; never discard them.
- Record exact interpreter, uv, Bun and lock revisions; secrets only set/missing.
- Run the offline command in the verification report. Separately collect the
  slow-but-offline selection before deciding whether it is safe to execute.
- Record project runtime-file hashes/mtime without displaying contents. Tests
  must not mutate `data/chroma-d11`, chat history, or project rate-limit DB.
  Investigate a write before continuing; do not mask it by silently restoring data.
- Capture baseline coverage with `--cov=src`, not filename-shaped source paths.
  Record dependency groups actually installed: this developer environment may
  have optional packages absent from CI's `uv sync --dev --frozen`.

**Acceptance:** counts, skips/warnings, commands, installed groups, and limitations
recorded. A clean CI-equivalent environment is a separate validation, not inferred
from this workstation. Stop if new failures or project-data writes appear.

### M1 — Independent test opt-ins and non-vacuous offline tests

**Own:** `tests/conftest.py`, targeted tests under `tests/unit/evals/`,
`tests/unit/ingestion/test_ingestion_error_handling.py`, new hook-policy tests.
**Evidence:** V04–V06.

- Remove the Qwen early return; gate `live_api`, `live_openrouter`, and
  `e2e_real_apis` independently. A test with multiple live requirements needs
  every corresponding opt-in. Keep offline fixture initialization before imports.
- Test the full 2^3 flag matrix without contacting providers. Verify marker
  reasons and selection; patch setup/precheck functions so tests cannot spend quota.
- Separate the two artifact-only tests from the live module. Make the write-error
  test actually exercise a write boundary or rename/rewrite it as a schema test.
- Replace conditional `if results` checks with explicit expected cardinality and
  per-case status assertions in touched tests. Patch dependencies where consumed,
  including async retrieval, active provider and judges, not only Qwen methods.
- Replace the skipped retry placeholder using the downloader's real transport
  seam; assert attempts, result, cleanup and terminal failure. If no retry contract
  exists, document that fact and remove the false test rather than invent behavior.
- Keep slow offline distinct from live; do not broadly mark awkward tests live.

**Acceptance:** flag-matrix tests pass with zero provider calls; extracted offline
cases run in fast gate; genuine live cases remain excluded by default. Explain
count changes rather than pinning the suite forever to 2,284.

### M2 — One command surface and honest coverage

**Own:** new root `Makefile`, minimal `scripts/check_backend.sh`,
`pyproject.toml` pytest options, `.github/workflows/ci.yml`, backend test guide.
**Evidence:** V03,V07,V21.

Prefer Make plus a shell entrypoint over introducing Just. Direct script use must
work where Make is unavailable. Keep it a small command dispatcher, not a framework.

| Command | Required semantics |
|---|---|
| `make test` / `bash scripts/check_backend.sh fast` | Offline marker expression from report, no coverage; do not inherit live opt-ins from caller to widen selection. |
| `make test-offline` / script `offline` | Include slow offline; exclude all live/network/DeepEval markers. Still synthetic, no corpus rebuild. |
| script `unit` / `integration` | Same offline fast selection restricted to tier; optional existing xdist for unit only after isolation check. |
| `make coverage` / script `coverage` | Same shared selection, `--cov=src`, deterministic report paths; fail-under chosen from clean-environment baseline. |
| `make lint` | Ruff check/format-check, mypy src, import-linter, Bandit, docs consistency; never auto-fix. |
| `make frontend-check` | Existing Svelte check/build only; separate frontend tests target. |
| `make smoke` | Synthetic smoke selection; no real provider path or project DB. |
| `make help` | List targets, scope and potential side effects. |

- Move coverage options out of default pytest `addopts`. Retain strict markers,
  import mode, durations and failure summaries. Preserve direct targeted pytest use.
- Script owns the marker expression once. It forwards user arguments as an array,
  does not use `eval`, propagates exit codes, and fails on unknown mode.
- CI calls the script. Recommended initial design: one offline backend coverage
  job combining unit+integration rather than introducing coverage-artifact merge
  complexity. Retain tier commands for diagnosis; avoid rerunning same tests in
  multiple jobs without a reason. Keep workflow-level timeouts.
- Measure coverage on clean CI dependency groups. Start with a nondecreasing floor
  below the measured rounded baseline (candidate 80% only if clean baseline supports
  it); do not copy 82% blindly, lower it to hide failures, or call branch coverage done.
- Live tests are a separate explicit operation, not `make test-all` that silently
  spends quota. Document independent opt-ins; do not attach secrets to offline CI.
- Shell-policy tests: unknown mode, exit propagation, exact selection, argument
  quoting and absence of implicit coverage. Use dry-run/fake uv command where useful.

**Timeout note:** progress-hidden `| tail` is unsuitable for diagnosing stalls.
Redirect to a file and monitor it, but process-tree termination must be verified
on the chosen runner. GNU timeout `--kill-after`/signals are not a portable proof
that detached grandchildren terminate; use CI job timeouts plus explicit process
supervision when needed. Do not add a process supervisor without a demonstrated need.

**Acceptance:** one selector source; local fast run has no coverage collection;
CI-equivalent run has one explicit project-wide report and documented threshold;
all commands are copy/paste runnable and preserve nonzero exits.

**Not included:** console scripts. Current repository has no explicit packaging
build system. Add entrypoints only in a later packaging decision, with wheel,
config-file discovery, editable-install and image-install tests. `python -m`
interfaces remain supported; do not invent an unsupported `qna` command.

### M3 — Audit actual project dependencies

**Own:** dependency-audit workflow section and documented audit command; separate
from M2 workflow edits or same owner. Dependency installation changes need approval.
**Evidence:** V19; prior upper-bound recommendation corrected.

- Export the selected locked dependency set to a temporary requirements file
  using uv's supported frozen export mode; audit that file explicitly, not the
  isolated `uvx` tool environment. Alternatively sync and audit the project
  interpreter explicitly; choose one reproducible method and test it.
- Include runtime and dev in stated audit scope; optional groups either get
  explicit audits or are listed as uncovered. Preserve approved pins.
- Do not audit a requirements file containing editable project references/hashes
  unsupported by the chosen pip-audit mode; verify command compatibility first.
- Tool/service/network failure must fail or be labelled unavailable, never clean.
  Vulnerability exceptions require an advisory ID, reason, owner, and expiry.
- Document lock-refresh policy and test matrix. Do not impose arbitrary upper
  bounds or run broad upgrades as an audit repair.

**Acceptance:** workflow artifact identifies lock revision, groups, tool version,
input and findings; fixture/fake-auditor test proves explicit project input;
manual network audit is separately authorized. No claim of zero vulnerabilities
from a failed/offline audit.

### M4 — Current-state docs, configuration parity and data layout

**Own:** `docs/README.md`, new `docs/STATUS.md`, `docs/data/artifact-layout.md`,
architecture guides, `.planning/codebase/*`, test guide, targeted settings tests;
Compose simplification only after M12 contract agreement.
**Evidence:** V09–V12,V21.

- Make `docs/STATUS.md` the concise current entry: shipped functionality, offline
  gates, known deployment restrictions, open decisions and links to this plan.
  Historical reports retain their dates and evidentiary limits.
- Human architecture lives in `docs/architecture/`; `.planning/codebase/` retains
  agent-specific conventions/testing/context and links to canonical architecture
  rather than repeating long trees and line counts. Update AGENTS pointers only
  if necessary; do not delete useful information without mapping its destination.
- Inventory docs into current reference / active plan / historical evidence.
  Add status metadata and an archive index; do not mass-move 49 handoffs and break
  links. Move root `TEST_MIGRATION.md` only with redirects/link repairs or mark
  it historical in place. Include MkDocs links/nav in link checks.
- Replace deleted module/test paths with actual ones. Validate every documented
  targeted pytest path exists. Remove timing guarantees tied to one machine.
- Document `experiments/` as configs/output versus `src/experiments/` code; prefer
  explanatory names in guides over physical renames.
- Artifact-layout guide: raw/silver/gold/processed, frozen D11, legacy chroma,
  eval review/cache/output, mutable rate/history state; state which are portable,
  ignored, immutable, rebuildable, and excluded from R2. No data movement.
- Preserve current settings precedence and `APP__APP__ENVIRONMENT` compatibility.
  It is awkward but renaming it is a migration, not cleanup.
- Add tests for Compose APP__ keys resolving through Pydantic fields, YAML/model
  serving-identity defaults, explicit override precedence, and secret redaction.
  Legitimate Compose deployment overrides must be allowlisted with explanations.
  Nonsecret `.env` overrides remain valid despite secrets-only example guidance.

**Acceptance:** existing and new guide links resolve; startup/testing examples are
safe and current; no phantom modules; no new competing authority; config parity
fails when a future typo is introduced. Do not ratify F-01 on the owner's behalf.

### M5 — Artifact containment and bounded L6 memory

**Own:** `src/evals/artifact_service.py`, evaluation/experiment routes as necessary,
focused route/service tests. No role changes. **Evidence:** V13,V14.

- Centralize containment at EvaluationService's HTTP-facing read boundary.
  Treat evals root and comprehensive-ablation root as separately configured
  allowlisted roots; latest-pointer file is a pointer, not an authority to escape.
- Reject empty, `.`/`..`, separators, absolute/drive paths and invalid IDs. Resolve
  target under its approved root; reject symlink components and artifact symlinks.
  Validate explicit IDs, scans, pointer targets, and every artifact read.
- Preserve existing valid pointer encodings: inspect writer before changing it;
  support legitimate root-relative/repo-relative/absolute-in-root values through
  one normalized resolver with tests. Do not permit arbitrary external paths just
  to retain an unsafe historical pointer. Document rejected cases.
- Audit experiment routes too: regex plus appended suffix blocks common traversal,
  but discovered config/report symlinks still need root checks. Do not label regex
  acceptance of `..` alone as arbitrary-file disclosure.
- Map invalid input to generic 400, missing safe artifact to 404; no external
  filesystem path leakage. Static resolved containment is not a full defense
  against a malicious local writer racing symlink swaps; document trusted-writer
  assumption or use no-follow descriptor opens where threat model requires it.
- L6 route: `Query(100, ge=1, le=500)`; service validates positive bounded limit
  for non-HTTP callers too. Keep exact `total_count`.
- Read lines incrementally, retain at most `limit` parsed records, scan/count valid
  records to EOF. Preserve malformed-record behavior unless explicitly changed.
  Exact count entails O(file size) I/O; do not promise early termination/O(limit)
  runtime. A future count sidecar or paginated contract is separate work.
- Add an explicit maximum JSONL line size or record-byte bound if untrusted files
  are in scope; otherwise document that a single huge record remains a limit.

**Tests:** `.`/`..`, encoded separators, absolute paths, sibling-prefix trick,
run-dir symlink, artifact symlink, pointer escape, valid pointer forms, missing
files; large synthetic JSONL confirms retained list <= limit and exact count,
limits -1/0/501 rejected, malformed lines contract preserved. All fixtures tmp-only.

**Acceptance:** HTTP readers cannot escape configured roots in tested threat
model; valid payload shapes and exact counts unchanged; no project artifacts read
as fixtures or rewritten. Root/path safety is enforced even for direct service calls.

### M6 — Request size and consistent HTTP errors

**Own:** app middleware/factory/settings, OpenAPI contract and targeted tests.
**Decision required:** approve a body-size value/scope and rate-reset semantics
before implementation; proposed starting policy is a configurable 1 MiB cap for
JSON chat/evaluation POSTs, subject to actual payload needs. **Evidence:** V16.

- Use ASGI receive-byte enforcement, not Content-Length alone; handle chunked or
  missing length, lying length, malformed length and disconnect. Do not consume
  or buffer an entire unbounded body. Keep streaming responses unaffected.
- Ensure 413 follows existing error envelope and gets CORS/request ID through
  deliberate middleware placement; test OPTIONS, auth rejection, allowed requests
  and oversized requests. No duplicate response after response start.
- Standardize 429 envelope without removing `detail`; retain Retry-After.
  Choose/document epoch timestamp vs delta for X-RateLimit-Reset after inspecting
  client/spec consumers; test both allowed and rejected response semantics using
  fake time. Do not conflate error-envelope change with auth policy changes.

- Add a published OpenAPI drift guard (F-04): prefer a deterministic exported
  FastAPI schema for implemented endpoints, or compare normalized request/response
  shapes for the checked-in YAML's documented subset. Account for references,
  nullable forms and version differences; do not snapshot unstable ordering.
  Do not instantiate lifespan/providers/index to generate schema. SSE wire events
  need separate contract fixtures because OpenAPI alone cannot validate them.
  If current untyped route dictionaries cannot express the published contract,
  add narrow response models in a separately reviewed patch rather than making a
  schema test tautological or deleting documentation to make it pass.

**Acceptance:** bounded receive behavior proved with a synthetic ASGI stream,
not just TestClient Content-Length; docs/runtime schemas agree; deliberately
changing a documented request/response shape fails the drift test; no SSE regression.

### M7 — Pure frontend stream parser and fast tests

**Own:** frontend package/lock/config (only with dependency approval), new parser
under `frontend/src/lib/utils/`, `+page.svelte`, unit tests and relevant Playwright
cases. **Evidence:** V08. Do not introduce an admin UI.

- Propose a compatible Vitest version first; use existing Bun lock workflow.
  Do not silently upgrade Svelte/Vite or substitute another package manager.
- Extract a pure incremental parser with `feed`/`finish` behavior; page retains
  fetch/AbortController/UI ownership. Support UTF-8 splits, LF/CRLF, event blank
  lines, comments, optional space after `data:`, and joined multiline data.
- Interpret the existing JSON protocol: content chunks; one terminal `done`
  carrying sources/pipeline or error metadata. EOF without terminal is incomplete;
  malformed JSON is a controlled visible error, not console-only success.
- No auto-reconnect/resubmit for POST chat: that can duplicate generation/history
  and quota. `[DONE]` is not emitted by this backend; do not treat it as success
  unless protocol compatibility is explicitly selected. Unknown fields may be
  ignored; unknown event types must not fake completion.
- Decoder flush and final pending-frame behavior must be defined/tested. Cancellation
  is separate from truncation; stale generations cannot mutate current messages.
  Release/cancel reader in finally; do not mask primary errors with close errors.
- Unit cases: every possible chunk boundary for representative frames, split
  multibyte content, CRLF, multiple frames/chunk, malformed payload, normal EOF,
  terminal error, duplicate terminal, trailing partial frame, intentional abort.
- Playwright regressions: truncated response visible error; clear-history failure
  retains history; stale stream after new generation cannot update the page.

**Acceptance:** fast parser tests run in frontend CI without browser; existing
58 tests are still collected (plus additions), Svelte check/build pass, browser
execution is recorded independently. No promise of browser pass if dependencies
are absent; collect-only is not execution.

### M8 — Extract assessment responsibilities, preserve semantics

**Own:** `src/evals/assessment/` and relevant tests only; no runtime/settings/lock
changes. **Evidence:** V01. Requires M0/M1 baseline, no provider calls.

First add characterization fixtures for: successful offline run, failed attempt,
replay, invalid review manifest, cache ineligibility, stale identity, partial metric
failure, cancellation/cleanup, and metadata-only telemetry. Compare artifact
schemas/order/identity inputs/statuses with deterministic clocks and generated IDs.

Extract in small ordered patches, functions first:

1. Review-manifest parsing/schema/dataset/snapshot binding helpers -> cohesive
   `review_validation.py` (keep symlink/duplicate-key/re-read checks intact).
2. Execution snapshot/index identity/input provenance helpers ->
   `execution_identity.py` and/or `provenance.py`, only if dependencies stay acyclic.
3. Replay validation/execution helpers -> `replay.py`; keep pipeline call ordering.
4. Finalization/failure publication helpers -> `publication.py`, keeping atomic
   publication, failed-attempt records, cache eligibility, usage and span outcomes.
5. Reassess stage methods. Leave `AssessmentPipeline` as coordinator and public
   `run_assessment()` in its current import location. Do not mechanically move
   methods into mixins or pass the entire pipeline object to every helper.

Names are proposals; confirm cohesion/import graph before the first move. Keep
existing injectable callables and `monkeypatch` resolution from orchestrator's
namespace until callers/tests are migrated deliberately. Extracted helpers receive
explicit inputs; create a small typed stage result only when it replaces an
existing unclear dict, not a general workflow engine.

**Acceptance:** deterministic artifact parity for all fixtures, no weakened
failure/privacy assertions, no new import exemptions/cycles, public imports and
CLI unchanged. Report responsibility/line-count reduction; ~600 lines is a review
signal, not a hard goal that justifies splitting cohesive code artificially.
Commit each extraction separately from test rewrites where practical.

### M9 — Targeted remaining cohesion, no blanket rename

**Own:** one module family at a time (`retrieval_eval`, `store`, `telemetry`,
`dataset_builder`) and matching tests. **Evidence:** V02,V20.

Map public API, state, locks, dynamic imports and consumers before choosing a
split. Rank by actual changes/confusion, not just LOC. Reuse existing `listing`,
`factory`, `hype_index` seams; avoid duplicate helpers. Telemetry lifecycle/privacy
must remain under one clear owner. Analyze allowed eval/experiment/RAG edges and
remove only genuinely unnecessary ones; do not add adapters merely to hide cycles.

**Acceptance:** one justified cohesion improvement per patch, imports and behavior
preserved, no added ignore patterns. Defer any module whose split has no clear win.

### M10 — Metadata validation revision and serving-write policy

**Own:** store/factory/index and tests, serialized with M8 if seams overlap.
**Evidence:** V17; addresses F-03 in two separable parts.

- First test metadata mutation after successful validation. Choose a minimal
  revision/token or metadata snapshot in validation credit; invalidation must cover
  `set_index_metadata`, documents replacement, clear/rebuild and store swap,
  including failed mutations where persisted state may have changed.
- Never hash the raw corpus on every retrieval to solve this. Bound metadata
  comparison cost; document that external-process mutations are out of scope unless
  explicitly checked. Store/config identity checks remain.
- Separate persisted build evidence from in-memory runtime overlays. An overlay
  must not rewrite conflicting historical build metadata and then validate itself.
  Add tests for mismatch visibility before and after constructor overlays.
- Strict read-only serving is a separate policy spike. Test a copied index on a
  genuinely read-only mount with the installed Chroma version. If client itself
  needs writes, report the limitation and propose remote/read-only snapshot serving;
  do not promise read-only boot simply by skipping collection.modify.

**Acceptance:** in-process metadata changes force verification; authoritative
migration replacement/overlay provenance semantics remain; no raw-tree rehash per
request. Write-free metadata policy and full filesystem-read-only support are
reported separately; production policy changes need approval.

### M11 — Exact frozen sync integrity

**Own:** manual R2 script/tests/runbook; no remote calls. **Decision required:**
approve replacing tolerance semantics for corpus/review and defining raw policy.
**Evidence:** V18; stronger than the previous F-07 description.

- Frozen verify must reject every unequal size, including 1–100 byte drift, and
  compare SHA-256 for equal sizes. Raw tolerance, if retained, must be explicitly
  named approximate mode and never labelled exact/integrity verified.
- Strict transfer must repair equal-size drift, not just report it: compare an
  authoritative digest or fetch/hash; do not assume S3 ETag is SHA-256. Preserve
  report-only verify behavior, containment, atomic parts and body closure.
- Do not add a manifest unless ownership/versioning makes it authoritative.
  If chosen, specify schema version, safe relative key, exact size, sha256,
  snapshot generation, publication-last rule, partial upload/download failure and
  compatibility with old remotes. Never checksum a live-mutating SQLite/WAL tree
  and call it a coherent snapshot; quiesce/export locally in a separately approved
  operation. No real sync executed as part of implementation.

**Acceptance:** fake-S3 tests for +/-1/100/101 bytes, equal-size corruption,
missing/unsafe keys, interrupted transfer, deterministic strict repair. Docs
accurately distinguish object equality from snapshot consistency. Migration of
existing remote objects is not implicit approval.

### M12 — Deployment reference and non-root runtime

**Own:** Dockerfiles, Compose files, deployment docs/tests. **Decision required:**
reference deployment model, UID/GID/storage ownership and proxy topology.
**Evidence:** V12,V15,V16; F-10.

- Preserve current invocation compatibility where possible: document existing
  Compose as source-mounted local configuration; add a standalone production
  reference without source mount, rather than relying on ambiguous override merge
  semantics to remove it. Choose exact filenames after checking docs consumers.
- Add non-root runtime UID/GID; writable directories and host mounts must have
  documented ownership. No chmod 777, recursive startup chown, or copying secrets
  into image. Test prepopulated and empty writable state directories.
- Production example must use actual security preconditions, correct image code,
  healthchecks and current one-worker limit. Missing secrets fail clearly without
  revealing values. Optional groups/assets remain opt-in.
- When trusting forwarded headers, ingress overwrites them and direct backend
  access is blocked. Document NAT/shared buckets. Edge limits supplement, not
  silently replace, application limits.
- Docker image build alone is insufficient: run synthetic boot/health with fake
  provider and copied index, then graceful shutdown; no paid provider calls.

**Acceptance:** non-root identity proved, valid state permissions, no source overlay
in production reference, health/shutdown proof, sanitized failure cases and explicit
proxy requirements. No public deployment or role-policy change performed.

## 5. Explicit decision backlog (not automatic implementation)

| Decision | Needed before | Default until approved |
|---|---|---|
| F-01 serving-default ratification in migration register | governance closure | Document existing baseline; do not fabricate an owner approval. |
| Role matrix/public-admin split/server-side UI auth | any F-02 implementation | Preserve prior no-admin/no-role scope. Draft route matrix only. |
| New dependencies/lock changes | Vitest, audit tooling additions, packaging | Existing lock stays unchanged. |
| Body size/scope and reset-header semantics | M6 | Draft proposed values, test contract after approval. |
| Frozen/raw sync semantics and snapshot production | M11 | No remote mutation or data migration. |
| Metadata/read-only deployment target | M10 policy half | Fix tested invalidation without claiming read-only support. |
| Deployment UID/GID/ingress | M12 | No deployment posture change. |
| Packaging/installable CLI | later optional slice | Task runner + existing python -m interfaces. |
| Dependency compatibility bounds | deliberate lock refresh | Frozen install; advisory-specific fixes only when approved. |
| License/authors/version policy | packaging/public distribution work | Do not invent legal ownership, choose a license, or bump versions as cosmetic cleanup. |

## 6. Verification ladder and release evidence

After each code slice: targeted tests -> shared offline suite -> Ruff
check/format-check -> mypy src -> import-linter -> Bandit -> docs consistency.
Frontend slices add unit tests, Svelte check/build and Playwright execution.
Coverage/reporting slices add clean-environment whole-project coverage. Deployment
slices add Docker build AND synthetic runtime checks, not just YAML parsing.
Structural slices additionally require deterministic artifact parity. These
engineering gates are not evidence of clinical safety, diagnostic suitability,
benchmark promotion, PHI compliance, or production load capacity. Those require
separate domain evaluation and operational review; keep status docs explicit.

Record command, HEAD, lock/group scope, exit code, counts, duration, warnings,
project-data mutation check and environmental skips. No hidden `| tail` masking
exit status; retain logs under /tmp or CI artifacts. Confirm clean-tree diff scope
and no credentials/runtime files before commit. Never call a skipped live/browser
suite verified. No numerical coverage drop justified solely by moving code.

Keep failures primary: do not weaken tests, reduce floors, broadly mark cases
live, or increase timeouts to make gates green. A hanging test requires bounded
trace/profiling and classification, not guessing at deadlocks.

Each patch has independent revertability. Refactor rollback is a code revert;
data/schema rollback is not needed because migrations are prohibited here.
Contract/policy patches that need migration must stop for a separate plan.

## 7. Definition of handoff completion

The implementer updates this checklist with commit/evidence links, not narrative
claims alone:

- [ ] M0 baseline and clean CI-equivalent dependency matrix captured
- [ ] M1 opt-ins independent; meaningful offline coverage restored
- [ ] M2 shared commands/explicit coverage; CI uses same policy
- [ ] M3 project-lock dependency audit input verified
- [ ] M4 docs, config parity and artifact-layout truth-sync
- [ ] M5 containment and L6 memory/count contract tested
- [ ] M6 body/error contract approved and tested, or explicitly blocked
- [ ] M7 frontend dependency approval + parser unit/browser evidence
- [ ] M8 characterization and staged assessment extraction parity
- [ ] M9 only justified remaining cohesion patches, or explicit deferral
- [ ] M10 metadata invalidation fixed; read-only support truthfully reported
- [ ] M11 strict sync policy approved/tested offline, or explicitly blocked
- [ ] M12 non-root/deployment policy approved/runtime-tested, or blocked
- [ ] F-01/F-02 and remaining decision backlog labelled approved/open/deferred
- [ ] Final review, data safety, limitations and rollback evidence attached

A blocked decision is an honest outcome. Do not report all work complete while
silently excluding a gated slice, and do not continue to product-feature work
under this maintainability authorization.
