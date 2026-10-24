# Phased implementation plan

**Status:** P1-A1–P1-A4 and the bounded P1-B/P1-C1/P1-C2 slices approved and verified on 2026-10-15; Phase 1 is partially complete. All unchecked tasks remain pending. Evidence: [P1-A1](20261015-p1-a1-handoff.md), [P1-A2](20261015-p1-a2-handoff.md), [P1-A3](20261015-p1-a3-handoff.md), [P1-A4](20261015-p1-a4-handoff.md), [P1-B](20261015-p1-b-handoff.md), [P1-C1](20261015-p1-c1-handoff.md), [P1-C2](20261016-p1-c2-handoff.md).
**P2/P3 follow-through:** Owner requested offline Phase 2/3 implementation. The bounded [role/completeness and existing-export foundation](20261016-p2-p3-foundation-handoff.md) is implemented; neither phase is complete and integrated exit dependencies remain unchanged.
**Normative requirements:** [implementation specification](implementation-spec.md).
**Owner choices:** [decision register](decisions.md). **Access/spend:** [environment guide](environment-and-credentials.md).

**Core slice + T4–T6 complete (2026-10-21):** The approved Logfire/OTel adoption + P3-C offline-canary core (T1–T3), the confirmed T4 review-polish batch, the T5 D11 frozen-identity builder + snapshot, and the T6 attested-manifest authoring tool are done — see the [Logfire/P3-C handoff](20261021-logfire-canaries-handoff.md), the [T4 handoff](20261021-t4-review-polish-handoff.md), the [T5 handoff](20261021-t5-d11-snapshot-handoff.md), and the [T6 handoff](20261021-t6-review-manifest-tool-handoff.md) (gate 1,787 ×2, review chains closed, preservation OK). **T7 boundary documentation is also complete:** see the [T7 handoff](20261021-t7-boundaries-handoff.md) and [data-processing boundaries](../../data-processing-boundaries.md). All T1–T7 tasks of the [next-slice brief](20261021-next-slice-brief.md) are delivered; this does not close whole phases or operational privacy/hosted/live gates. Decisions of 2026-10-20 are in the [decision register](decisions.md).

**Offline hardening follow-up (2026-10-21):** [Closure](20261021-offline-hardening-handoff.md): owned HyDE logs sanitized, seven canary/behavior tests added; gate 1,794 ×2. Repeated review-context validation deliberately retained; API-key masking assessed only. The pre-existing preflight/runtime legacy-hash mismatch was subsequently [closed](20261021-auth-preflight-parity-handoff.md), including JSON-precedence readiness reporting; gate 1,814 ×2.

**Current continuation (2026-10-20, second slice):** See the [admission/manifest/spans handoff](20261020-admission-manifest-spans-handoff.md) for independent embedding spans, stream retry transition telemetry, generalized budget admission, and hash-verified review-manifest attestations (content consistency only). Whole phases, identity-authenticated review authority, full budget admission and hosted/live/container exits remain open.

**Previous continuation (2026-10-20):** See the [evaluation-tracing handoff](20261020-evaluation-tracing-handoff.md) for opt-in local run/case-correlated stage/attempt traces, supported-launcher log repairs, isolated verification and scoped review. Whole phases, authenticated review authority, full budget admission and hosted/live/container exits remain open.

**Previous integration checkpoint (2026-10-19):** The consolidated remaining Phases 1–3 plan and narrow dependency/browser provisioning are approved. See the [integration handoff](20261019-phases-1-3-integration-handoff.md) for current code, isolated gates, exact dependency changes, review repairs, and open exits. Earlier no-install/browser-blocked statements below describe their historical slices. **Whole phases remain incomplete; no live/model/corpus/export/default-switch/Phase 4 permission is inferred.**

## Execution rules

1. Complete Phase 0's decisions only as needed for the next slice. Do not block an independently approved offline defect fix on every future product decision.
2. Before each slice: inspect current files/tests, present the bounded plan, get approval, then implement. The owner's request to draft this plan is not approval for an unbounded rewrite.
3. Keep changes focused. No new generic registry, DI container, workflow engine, or duplicate evaluation service.
4. Code, tests, operational documentation, and this checklist change in the same slice. Record deliberate metric/behavior changes rather than demanding parity with known bugs.
5. Keep the fixed deterministic baseline available throughout. Avoid unrelated formatting/refactoring and preserve the existing import-linter boundaries.
6. Run live work only with an approved dataset, provider allowlist, exact models, limits, and budget. Never auto-consume local credentials just because they exist.
7. Use fresh subprocesses and separate writable artifacts/index storage for experiments until explicit run-level state isolation is proven.

## Dependency graph

```text
0: decisions for the next slice
  |
  v
1: repair served baseline + configuration
  |
  v
2: trustworthy identity, artifacts, labels, metrics, and runner
  |
  v
3: safe baseline telemetry
  |
  v
4: Pydantic generation adapter + shared Pydantic Evals comparison
  |
  v
5: optional tool-driven experiments -> explicit keep/promote/reject decision
```

Dependency/capability research and private deployment preparation can happen alongside earlier phases. Integration gates remain sequential: a new framework cannot bypass a failing baseline or an untrustworthy benchmark.

## Phase 0 — Confirm scope and establish a safe workspace

**Goal:** Turn ambiguous goals into explicit constraints without requiring credentials.

### P0-A: Decision checkpoint

- [x] Approve P1-A1 via “let's proceed, lets start”, P1-A2 via “proceed”, and P1-A3 via “proceed with next”, and P1-A4 via the subsequent “proceed”; approve proposed P1-B via “continue with the tasks” / “proceed”; retain the owner's async-first direction. The subsequent “proceed” approves proposed P1-C streaming retries/cleanup, begun as bounded C1; the subsequent explicit “approve” accepts C2's concrete rejection/atomic-commit/admitted-worker cancellation semantics. Remaining work is separately planned. Unrelated slices remain unapproved.
- [x] P1-A1 uses synthetic store/ingestion dependencies with no live/export access; final wider RAG verification uses temporary Chroma storage. Earlier pre-existing test-directory caveat is recorded in the handoff.
- [x] Record D01/D02: private research, public/synthetic data only. D17 now selects corrected `baseline`; its remaining matched request settings and benchmark capture are still pending.
- [x] Record D05/D06/D08/D09: adapter first; local then metadata-only Logfire; experiment-oriented reuse; CLI/YAML + subprocess isolation. These choices do not authorize live requests/export.
- [x] Record follow-up D03/D04/D10: owner-confirmed Go eligibility, USD 20/month incremental project charges (existing Go subscription separate), approved Logfire/Pydantic Evals consolidation and public/synthetic case input/output export.
- [ ] Before live work, verify Go account/model access, honest `User-Agent`, stable per-conversation `x-opencode-session`, usage-reporting limits, and D07 judge/review needs. Before export, configure D06/D15 destination/access/retention and pass local content-policy tests. No public rollout or arbitrary paid run is implied.

### P0-B: Baseline record

- [ ] Record current revision, working-tree state, Python/lockfile versions, installed extras, and non-secret config selections.
- [x] Capture P1-A1–P1-A4/P1-B/P1-C1/P1-C2 offline results, commands, selections/skips, reviews, and static checks in linked handoffs; broader suite/per-request lifecycle gates remain pending.
- [ ] Use isolated synthetic fixtures, temporary history/artifacts, and fake embeddings. Do not change or dump existing data/credentials.
- [ ] Record actual source/index availability. If the real corpus is incomplete, rebuild only into new approved storage or mark live retrieval checks blocked.
- [x] Create the [P1-A1 handoff](20261015-p1-a1-handoff.md); update it and these checklists with verified progress.

**Exit:** A bounded Phase 1 plan can execute offline with no ambiguous data access or production side effects.

**Rollback:** Documentation only; no runtime rollback needed.

## Phase 1 — Repair the baseline, not the framework

**Requirements:** R00–R05; deployment subset of R11.
**Credentials:** None for implementation/regression tests. Optional approved synthetic live smoke is a separate task.

### P1-A: Real async retrieval and lifecycle

**Primary files:** `src/rag/runtime.py`, `src/rag/index.py`, `src/rag/retrieval.py`, `src/rag/hyde.py`, `src/usecases/chat.py`, `src/app/factory.py`.

- [x] Separate sync-only initialization from the async retrieval path using existing seams (P1-A1); real HTTP lifespan verification remains below.
- [x] Move initialization's thread-lock wait, store work, and synchronous ingestion together off-loop; serialize async/sync contenders and document/test cooperative cancellation before/after worker admission (P1-A2).
- [ ] Keep already-initialized behavior correct; do not lazily rebuild/download during a benchmark request.
- [x] Offload synchronous store access, expansion, HyPE, candidate search (including query embedding), and rerank/diversification on the async retrieval path; use native async HyDE generation (P1-A3). No full HTTP/lifecycle claim.
- [x] Test real async retrieval boundaries with synthetic leaves, not mocked orchestration/initializer guards (P1-A1–P1-A3).
- [x] Own/drain app startup and cleanup tasks; attempt closure of app-constructed SDK clients, clear references, and reset state even when later startup fails (P1-A4).
- [x] Add full synthetic HTTP/SSE lifespan integration tests through real router/use-case/initializer/retrieval, substituting only dependency leaves (P1-A4).
- [ ] Track per-request worker/upstream-stream ownership and cleanup on cancellation/error; coordinate with P1-C. No universal worker drain or physical Chroma close is implied.

**Acceptance:** A non-empty HTTP SSE chat completes through the actual async orchestration; an already-ready index does not trigger a sync-loop error; cancellation and shutdown release owned resources; event-loop responsiveness is checked with deliberately blocking fakes rather than fragile absolute latency thresholds.

### First bounded slice — P1-A1 (approved and verified)

- Fix only the async retrieval/index-readiness failure: separate shared query preparation from sync/async initialization and use the existing async initializer on the async path. Preserve the sync CLI guard/behavior.
- Primary change: `src/rag/runtime.py` plus focused tests under `tests/unit/rag/`; change `src/rag/index.py` only if the inspected implementation requires it. Test through real initialization boundaries with fake store/ingestion dependencies, including an already-ready index, without mocking away the guard.
- Offline/synthetic/temporary storage only; no keys, network, paid calls, exports, dependency changes, real index/history writes, provider/default switches, or unrelated lifecycle/streaming work.
- Verified: 10 new regression cases; 99 RAG unit cases passed, with no skipped/deselected cases, using temporary Chroma storage and a socket/DNS-denying test runner. Ruff/format, MyPy on `src/`, and all four import-linter contracts pass. [Handoff](20261015-p1-a1-handoff.md) includes the original failing regression and initial test-storage caveat.
- This completed only async readiness. Subsequent P1-A2–P1-A4 cover initialization contention, off-loop retrieval, and app-owned lifecycle; per-request resource cleanup and live support remain pending.

### Second bounded slice — P1-A2 (approved and verified)

- Follow the owner's async-first direction: canonical async initialization, with the existing guarded sync CLI wrapper delegating to it. No parallel orchestration implementation or loop-bound global async lock.
- Offload one synchronous initialization helper, keeping the process-local thread lock through storage work and ingestion. Move state/signature reads inside that lock.
- Cancellation observed before the worker's post-lock checkpoint skips all work; after admission, even before first store access, caller cancellation cannot revoke the build. Active work completes/fails under the lock; cancellation never promises to kill a thread.
- Seven new event-controlled regressions cover async/async and async/sync contention, active cancellation, observed cancellation before admission (including forced rebuild), cancellation after admission, and failure/retry. A bounded real thread-lock wrapper prevents old deadlocks from hanging pytest.
- Verified: 106 RAG unit + 4 config-concurrency integration cases passed, no skips/deselections; seven concurrency cases repeated in 10/10 isolated runs. Ruff/format, source MyPy, and all four import contracts pass. [Handoff](20261015-p1-a2-handoff.md).
- At completion, search/reranking remained pending; subsequently covered by P1-A3. App startup/shutdown ownership, full HTTP/lifespan smoke, concurrent configuration mutation, cross-process coordination, and failed-partial-index provenance remain outside this slice. No provider/dependency/data/default changes.

### Third bounded slice — P1-A3 (approved and verified)

- Move synchronous retrieval-stage work off the event loop with `asyncio.to_thread`, preserving query/stage order, context variables, source metadata, ranking/filtering behavior, and sync entry behavior. Search each expanded query sequentially in one worker batch; no new parallel provider workload.
- Cover async runtime and direct candidate/expansion APIs. Keep native async clients on the owning loop: HyDE previously called synchronous `generate()` inside an async function; it now awaits existing `LLMClient.a_generate()` without changing provider selection, prompt, truncation, or ordinary-error fallback.
- Guard cached runtime reranker lookup, lazy loading, and prediction with one thread lock; async callers acquire it only inside a worker, preventing newly overlapping model construction/loading/prediction.
- Cancellation propagates and stops downstream orchestration. Already-started synchronous stages can finish, including the rest of a candidate batch or a reranker worker waiting on its lock. No thread-termination or charge-reversal promise.
- Verified: 25 new synthetic regressions; 131 RAG unit + 11 explicitly selected safe HyDE unit + 4 config-concurrency integration cases passed, no selected skips/deselections. New cases repeated in 10/10 isolated runs. Ruff/format, source MyPy, four import contracts, and read-only GPT-6 Luna `xhigh` review pass. [Handoff](20261015-p1-a3-handoff.md) records selections and boundaries.
- At completion, HTTP/lifespan/startup-failure cleanup was pending; subsequently covered by P1-A4 for app-owned resources. Configuration/index mutation during requests, provider migration, evaluation changes, and throughput claims remain excluded.

### Fourth bounded slice — P1-A4 (approved and verified)

- Test the real app lifespan and non-empty HTTP/SSE route through real use-case/retrieval/initializer/factory boundaries, with synthetic store/ingestion/generation leaves and real temporary history/rate-limit SQLite. Cover cold/ready startup and optional pipeline traces without bypassing lifespan.
- Wrap acquisition/yield in `try/finally`; initialize off-loop before publishing the warm store. Capture and close only the composition-root-constructed client, not a later `app.state` replacement. Attempt native Qwen/Gemini async/sync transport closure; optional no-hook clients remain supported and library-global LiteLLM sessions are not closed.
- Shield/drain lifespan-owned startup and cleanup tasks across repeated cancellation before reset. Preserve caller cancellation over a drained initializer failure; log ordinary cleanup errors without raw SDK exception details or masking startup errors. Clear stale dependency references and reset logical factory/runtime state.
- Verified: 24 new cases (18 lifespan integration + 6 mocked SDK cleanup unit), repeated 10/10 runs; wider selected gate 218 passed, 1 skipped for unavailable optional DeepEval, 0 deselected. Ruff/format, source MyPy, four import contracts, and read-only GPT-6 Luna `xhigh` review pass. [Handoff](20261015-p1-a4-handoff.md).
- Use the new handoff's pre-collection storage isolation, not a bare pytest command: rate-limit SQLite is constructed at module import. No live calls, real data writes, dependency/default changes, physical Chroma shutdown claim, shared-app topology, or per-request worker drain.
- Phase 1 is not complete. At P1-A4 completion P1-B was the unapproved next slice; subsequently approved and verified below. Per-request stream ownership remains outside P1-A4.

### P1-B: Effective profiles and ingestion flags

**Status:** Approved bounded fixes verified; [handoff](20261015-p1-b-handoff.md). This is not certification of every future configuration/provenance requirement or baseline promotion.

**Primary files:** `src/rag/config.py`, `src/rag/index.py`, `src/rag/production_profile.py`, `src/ingestion/runtime_config.py`, `src/ingestion/pipeline.py`, `src/ingestion/nodes/enrich.py`, `src/app/routes/chat.py`, `src/usecases/runtime_config.py`.

- [x] Use the shared retrieval resolver for applied profile/run + explicit options; pass inherited/explicit top-k through serving and evaluation; preserve explicit CLI retrieval-flag presence and coherent mode/top-k aliases. Whole-run manifest/presence-aware configuration consolidation remains a later gate.
- [x] Copy typed ingestion flags through `RuntimeState` into `IngestionRunConfig`, not through the store factory.
- [x] Preserve explicit `false`, None-as-inherit, and zero MMR; clamp count limits consistently and make zero sampling generate nothing.
- [x] Explicitly retain DashScope/Qwen for HyPE/enrichment; generation-provider migration does not migrate those roles or embeddings.
- [x] Distinguish applied/configured profiles, provider-appropriate/injected generation models, and next-build versus materialized index features in diagnostics.
- [x] Assert real initializer/Hamilton/steps execute synthetic generation only for enabled features; assert real built-in profile invokes the fake reranker and explicit disable skips it.

**Acceptance:** Verified with 66 new cases (54 unit/CLI + 12 integration), repeated 10/10 processes; selected wider gate **373 passed, 1 skipped** (unavailable optional DeepEval), 0 deselected. Ruff/format (20 files), MyPy (154 source files), four import contracts, and read-only GPT-6 Luna `xhigh` reviews pass. Corrected `baseline_cross_encoder` invokes a fake reranker; no ranking/quality benchmark or default promotion is inferred.

**Limits/next:** Profile/run overlays replace one another; no concurrent mutation/shared-app support, frozen whole-run configuration/provenance guarantee, automatic feature backfill, or live asset/provider verification. CLI long-flag abbreviation tracking remains a pre-existing gap. Retain legacy reports and capture the owner-selected corrected `baseline` plus D17's remaining matched request settings before comparisons. At P1-B completion, P1-C was proposed but unapproved; subsequently approved and begun as C1 below.

### P1-C: Streaming failure and history contract

**Status:** In progress. Owner-approved [P1-C1](20261015-p1-c1-handoff.md)/[P1-C2](20261016-p1-c2-handoff.md) remain verified; [P1-C3a](20261017-p1-c3a-handoff.md) adds SDK-boundary repairs, with the owner-approved [Gemini HTTPX follow-up](20261017-gemini-httpx-fix-handoff.md) resolving its generation-adapter transport finding. Scoped Luna re-review found no actionable issues. Phase 1 and R03 are not complete.

**Primary files:** `src/infra/llm/{qwen_client,litellm_client,gemini_client,interfaces}.py`, `src/usecases/chat.py`, `src/app/routes/chat.py`, relevant history interfaces/store.

- [x] Coordinate retries for the three existing generation adapters under the recorded supported routes. C3a aligns all twelve nonstream methods with C1's transient-only policy/per-call SDK options/async budgets; its approved Gemini fix explicitly selects and owns public HTTPX in the actual constructor, avoiding default aiohttp's hidden retry. Constructor/native/lifecycle regressions pass. This does not certify direct judge SDK calls, arbitrary auth/router/callback settings or live compatibility.
- [x] C1 forbids invisible stream restart/fallback after nonempty content; conflicting LiteLLM global retry/fallback policies fail closed without mutation.
- [ ] Complete request upstream/worker ownership under cancellation. C3a owns/drains returned public close awaitables through repeated asyncio/AnyIO cancellation, retaining session admission until settlement; real route/usecase and Starlette ASGI-spec-2.0 disconnect tests pass. Native Gemini inner physical release, broader workers, unentered/abandoned response cleanup and other server/send-error paths remain unverified.
- [x] C1 guards a single terminal/discards failed generation; C2 publishes completed pairs in one file replacement, fails closed on read/write I/O errors, and owns admitted commit workers until settled under cancellation. Cancellation before the pre-submit checkpoint admits no job; after admission a full pair may persist, cancellation remains primary, and the session stays owned until settlement. This is server completion, not terminal-delivery acknowledgment or fsync durability.
- [x] C2 rejects same-instance/process overlapping sync/stream turns and history clears (`chat_session_busy`), allows unrelated sessions, and releases admission before terminal yields. Busy streaming response is SSE/HTTP 200; clear is 409 with no cookie rotation. Legacy low-level message writes and independent instances/multiworker are not whole-turn guarded.
- [x] C1 parameterizes three-client fakes for pre/post-content failure, empty/usage chunks, timeout, cancellation/backoff, cleanup and SDK options; native OpenAI MockTransport proves attempt count and response close without closing the shared client.

**C1 evidence:** 99 new cases (88 unit + 11 integration), repeated 10/10 corrected-tree processes (990 executions). Wider selected gate **493 passed, 1 skipped** for unavailable optional DeepEval, 0 deselected. Ruff/format (8 files), source MyPy (154 files), and four import contracts pass. Read-only review requested excluding consumer pauses from the producer budget; corrected, follow-up verification recorded in the handoff. No live calls/dependency/schema/default/provider changes.

**C2 evidence:** 42 new cases (36 unit + 6 real-lifespan HTTP integration), repeated 10/10 fresh processes (420 executions). Wider selected gate **535 passed, 1 skipped**, 0 deselected. Ruff/format (9 Python files), source MyPy (154), four import contracts pass. Review and exact self-contained reproduction are recorded in the C2 handoff. No live calls/dependency/schema/default/provider changes.

**C3a evidence:** 393 added cases overall, including 391 in four new files (10/10 fresh processes, 3,910 executions). Expanded isolated gate **1,282 passed, 6 optional DeepEval skips**, 0 deselected; Ruff/format on nine Python files, source MyPy (154), four import contracts pass. Luna identified a default-Gemini-aiohttp retry gap missed by the initial HTTPX-only tests. The approved [follow-up](20261017-gemini-httpx-fix-handoff.md) resolves it for the actual generation-adapter constructor: 37 additional cases (10/10 fresh processes), expanded **1,319 passed / 6 optional DeepEval skips**, static checks and no actionable Luna re-review findings. Native SDK-default behavior and direct judge SDK paths are not certified by that fix.

**Remaining/next:** The bounded generation-adapter C3a transport finding is repaired and re-reviewed. Broader C3b request/response-worker ownership requires separate inspection/presentation/approval. Native Gemini physical per-stream release and direct judge SDK compatibility remain unverified. No SDK upgrade/private patch, arbitrary history redesign, broad dependency/provider/profile switch or public deployment is implicitly approved.

**Acceptance:** An interrupted stream never produces replayed prefixes; terminal/error metadata remains frontend-compatible; failed partial output cannot silently become a completed historical turn. C1/C2 and C3a's public-close subset meet only their recorded bounded contracts; the broader remaining gates above still apply.

### P1-D: Setup, preflight, and security baseline

**Resumed bounded batch (2026-10-16):** Dedicated session signing, fail-closed unknown-provider and single-worker guards are implemented with synthetic regressions; see the [guard-batch handoff](20261016-guard-batch-handoff.md). Expanded isolated gate: **856 passed, 6 optional DeepEval skips**; Ruff/source MyPy/import contracts and frontend type/build checks pass. Browser execution remains blocked. The owner-approved [follow-up](20261017-review-repair-handoff.md) repairs both Luna findings, adds median/partial-summary regressions, and passes **889 tests with 6 optional DeepEval skips** plus static/frontend checks. Luna re-review found no actionable issues; browser execution is still unverified. Owner selected corrected `baseline` for D17; remaining matched generation settings, setup/preflight, container parity, SDK/worker cleanup and baseline capture are still open.

**Primary files:** `src/config/settings.py`, `config/settings.yaml`, `.env.example`, `Dockerfile`, `docker-compose.yml`, `src/app/session.py`, `src/app/security.py`, `src/app/factory.py`, setup/deployment docs.

- [ ] Align local/container config inclusion and chosen provider/profile. Unknown provider strings are now rejected in typed settings and the client factory; container/config parity remains pending.
- [ ] Add non-secret local preflight information without paid connectivity checks.
- [ ] Validate extras/assets for selected profiles; provision heavy assets explicitly, not during normal benchmark traffic.
- [x] Require a dedicated random session secret outside development and test JSON-key auth configuration too (`APP__API__SESSION_SIGNING_SECRET`; missing/weak values fail closed, process-random development fallback, no legacy signer).
- [x] For private-lab scope, document binding/access constraints, supported single-worker file-storage topology, and explicit production auth failure behavior. Production CLI rejects worker counts other than one; independent shared-file processes remain unsupported. No public/container parity claim.
- [ ] If a public demo is selected, approve a separate bounded auth/proxy implementation: anonymous chat versus private routes, server-side secrets, cookies/CORS, and tests. Do not silently weaken all-route auth.
- [ ] Update stale environment-variable and setup examples to actual supported nested names.

**Acceptance:** Local and container resolved non-secret settings match; missing required credentials/extras fail clearly; no secret appears in diagnostics; deployment mode and session signing are tested. No public deployment while its policy remains open.

### Phase 1 exit and rollback

- [ ] Offline unit/integration suite plus real-lifespan smoke passes.
- [ ] Ruff, formatting, MyPy on `src/`, and import-linter remain green.
- [ ] Corrected baseline configuration and known deliberate behavior changes are captured.
- [ ] Existing SSE contract and session isolation are covered.

**Rollback:** Revert individual non-security changes only with a written explanation. Do not restore predictable session signing or partial-stream replay as an operational fallback. A historical broken revision is diagnostic only, never the new control benchmark.

## Phase 2 — Trustworthy evaluation before model comparisons

**Requirements:** R05–R10/R15; artifact compatibility portions of R13.
**Dependencies:** Phase 1 exit. **Decisions:** D07–D11/D17 as applicable.

**Scope split:** The required foundation is existing defect repair, versioned identity/completeness, isolated execution, and a frozen fixed-index pilot. Full cross-chunker passage mapping, broad clinical case annotation, repeated benchmark campaigns, and inferential promotion studies are separately approved extensions, not prerequisites for trying the adapter offline. Without those extensions, label the pilot exploratory and do not make promotion/clinical/equivalence claims.

### P2-A: Explicit role selection and effective experiment snapshot

**Primary files:** `src/config/settings.py`, `src/experiments/config.py`, `src/evals/schemas.py`, `src/evals/deepeval_models.py`, `src/evals/assessment/{orchestrator,answer_eval}.py`.

- [ ] Introduce independent generator/judge selections using small additions to existing config models.
- [ ] Keep implementation selection separate from provider strings; initially execution still uses existing clients.
- [ ] Validate only credentials/dependencies required by the selected task roles.
- [ ] Translate legacy settings explicitly and record effective settings, including request/prompt parameters, without secrets.
- [x] Do not make installed API keys implicitly enable a costly answer suite; run selection is explicit.
- [x] Bounded foundation: independent judge provider over existing supported provider/model/credential fields, selected-role metadata, and selected generator/judge credential diagnostics. Full task/implementation axes, snapshot handoff, client ownership and retry layering above remain pending.

**Acceptance:** Fake Gemini generator/judge evaluation runs without a DashScope generation key; a task needing real DashScope embeddings still reports that role's missing credentials accurately; unknown configuration fails early.

### P2-B: Versioned fingerprints, snapshots, and safe caches

**Primary files:** `src/evals/assessment/{orchestrator,reporting,answer_eval}.py`, `src/evals/{artifacts,artifact_service}.py`, `src/evals/checks/l5_index.py`, `src/experiments/config.py`, existing store metadata helpers.

- [ ] Define versioned manifest/metric/cache semantics and legacy-reader behavior before writing new artifacts.
- [ ] Separate execution ID from semantic fingerprint; make repeated benchmark attempts fresh. Dirty-source reuse requires a source-content digest; otherwise disable reuse and promotion for that execution.
- [ ] Compute a consistent actual collection/index fingerprint, including content and build spec; support clear unsupported/preflight errors for remote snapshot verification rather than writing `None` as a valid identity.
- [ ] Include effective generator/judge/expansion role, endpoint, prompt/rubric, dataset, corpus, index, output schema, and lock/source identities where relevant to each cache layer.
- [ ] Use per-attempt cache paths and atomic writes; do not cache transient failures as successful results.
- [ ] Preserve old artifacts unchanged and mark them legacy/non-comparable to new scoring semantics.

**Bounded B1 foundation:** [Handoff](20261016-p2-b1-handoff.md): artifact contract v1, unique fresh executions with one store, bounded tracked/untracked Python-source/lock provenance, attempt-local nonreusable cache schema v3, atomic publication and legacy/unsupported reader labels. Unverified run/answer reuse is disabled; assessment dataset-cache replay fails with explicit-file guidance. Source verification does not verify runtime/index identity; all new attempts remain semantically unverified and non-promotion-eligible. Full checklist items above remain open.

**Acceptance tests:** Changing model, provider/route, prompt, judge/rubric, expected evidence, index content, dimensions, retrieval flags, or output schema invalidates the correct cache layer; key values are absent; repetitions do not deduplicate; two isolated writers cannot corrupt one run's data; old artifacts still load.

### P2-C: Completeness and strict quality gates

**Primary files:** `src/evals/assessment/{thresholds,answer_eval,orchestrator}.py`, `src/evals/schemas.py`, `src/cli/eval_pipeline.py`, report readers/UI mappings as needed.

- [ ] Declare required suites/metrics and minimum eligible/measured coverage per run.
- [ ] Distinguish disabled/not-applicable, skipped, errored, failed quality, and passed quality.
- [ ] Reject missing/non-finite required values; preserve per-case errors and denominator counts.
- [x] Make strict CLI runs nonzero for incomplete required measurement even if no numerical threshold was evaluated.
- [ ] Prevent report/winner selection from treating incomplete or failed variants as ordinary candidates.
- [ ] Test generation failures, judge timeout, absent dependency, missing key, empty case set, excluded cases, and mixed partial success.

**Bounded foundation evidence:** Required thresholds reject missing/invalid/non-finite/boolean answer scores; selected-case and per-answer-metric denominators are recorded; other cases survive generation/judge failures; strict CLI and runner winner guards are covered. Full excluded/subpopulation policy, retrieval-case failure preservation and other dashboard mappings remain open. See the [handoff](20261016-p2-p3-foundation-handoff.md).

**Resumed history boundary:** The [guard batch](20261016-guard-batch-handoff.md) makes history aggregates `null`, suppresses charts/selectors, and retains run/source counts plus diagnostic filtering/selection. Invalid numerical measurements are unavailable, not zero; configuration and legitimate boolean findings remain readable without artifact rewrites. Frontend frozen-lock installation and type/build checks passed; mocked browser regressions are added but execution is blocked on provisioning. This verifies no comparison cohort and does not complete P2-C.

**Acceptance:** An explicitly requested answer suite cannot pass without scored cases; a declared retrieval-only run does not falsely fail merely because answer evaluation is intentionally out of scope; aggregate failure coverage is visible.

### P2-D: Frozen cases, evidence judgments, and correct metrics

**Primary files:** `src/evals/dataset_builder.py`, `src/evals/assessment/retrieval_eval.py`, `src/evals/metrics/_utils.py`, versioned fixtures under `tests/fixtures/` or the existing evaluation data location.

- [ ] Inventory overlapping fixture sets; pick a canonical case/version source rather than silently concatenating all files.
- [ ] Preserve approved splits; detect duplicate queries and document source-family overlap.
- [ ] Freeze the fixed-index pilot's source/index snapshot and independent reviewed judgments where scored; evidence quotes and stable IDs are sufficient for this initial slice.
- [ ] When a chunking comparison is separately approved, define source-span offsets/normalization and map reviewed passages across variants; do not require this machinery for a generation-only adapter comparison.
- [ ] Keep heuristic/synthetic labels visibly separate; disable per-variant automatic label regeneration in benchmark mode.
- [ ] Define independent qrels/evidence units and version nDCG/recall/precision formulas with hand-calculated tests.
- [ ] Add a minimal synthetic regression set for empty evidence, follow-up, unsupported citation, and injection behavior. Broad contradictory-evidence/units/ranges/red-flag clinical annotation belongs to the separately approved safety/promotion study and retains its review status.
- [ ] Calibrate quality margins only after initial reviewed measurements; do not copy old thresholds unchanged to changed metrics.

**Acceptance:** A matching source with irrelevant text is not an evidence hit; repeated chunks cannot inflate evidence recall; missing relevant judgments reduce nDCG appropriately; unanswerable ranking metrics are not applicable; the same frozen cases/labels are used for every compared variant.

### P2-E: Evaluate actual artifacts and isolate the runner

**Primary files:** `src/evals/checks/l3_chunking.py`, `src/evals/assessment/orchestrator.py`, `src/experiments/{feature_addition_runner,feature_ablation_runner,comparison_report,metric_utils}.py`, `src/cli/eval_pipeline.py`.

- [ ] Consume actual emitted chunks for L3 and fingerprint all index-affecting reuse settings.
- [ ] Run variants in fresh subprocesses with separate outputs/history/caches and isolated writable index directories.
- [ ] Use a frozen read-only collection for generation-only comparisons; verify identity before/after. Use verified per-process snapshot copies if the embedded backend cannot safely enforce read-only sharing.
- [ ] Add explicit functional replay versus fresh benchmark behavior.
- [ ] Implement matched per-case comparison, execution-order/sample-count metadata, cold/warm boundaries, and separate evaluator cost/latency. Descriptive pilot reports are explicitly exploratory; repeated campaigns and uncertainty estimates are required before inferential/promotion claims, not before the adapter can be exercised.
- [ ] Audit/declaratively install statistical dependencies if helpers are used; do not rely on undeclared SciPy.
- [ ] Regenerate affected ablations only under an approved dataset and budget; retain prior reports as historical.

**Acceptance:** Chunk size/overlap/enrichment/embedder changes prevent incorrect index reuse; modifying one variant cannot alter another's history/cache/index; cold/warm state is controlled and recorded; ineligible runs cannot win the report. A descriptive pilot is not automatically promotion-eligible.

### P2-F: Minimal monthly spend/usage summaries

**Primary files:** existing run manifests/reporting and evaluation/experiment CLI composition; reuse available SDK usage, no new billing database, request-event ledger, or dashboard.

- [ ] Implement accepted D04 scope: USD 20/month across all incremental project charges, excluding the existing Go subscription. No mandatory per-run dollar maximum; finite request/token/time/concurrency settings remain required.
- [ ] Add compact per-run usage/cost summaries by role where available; mark retries/failures/missing usage incomplete if costs cannot be recovered, and avoid double-counting SDK/framework totals.
- [ ] Aggregate existing run summaries by UTC month, counting each run once; keep a small manual record of subscription charges and provider-console adjustments, separate from included-quota consumption.
- [ ] Show known/estimated/unknown costs and pricing provenance. Disclose that Go account-level billing API access is unverified; exact quota/balance/invoice reconciliation initially uses Console/manual records. Do not start paid runs at the recorded ceiling; confirm auto-top-up/overage is off and document that local logging is not a hard cap.
- [ ] Test aggregation/month boundaries, repeated run records, quota/cash distinction, and unknown/incomplete usage offline.

**Bounded admission evidence (2026-10-20):** `paid_operation_budget_status` generalizes the fail-closed benchmark gate to named recorded paid operations with identical reason semantics and an explicit no-hard-cap/no-chat-gating disclosure; the benchmark wrapper stays byte-compatible and offline diagnostics report per-recorded-mode admission. This is informational admission against local records, not full runtime budget admission.

**Acceptance:** A simple CLI/monthly summary reuses existing records, keeps Go quota-value consumption distinct from cash, and makes provider-console reconciliation explicit.

### Phase 2 exit and rollback

- [ ] Deterministic retrieval metric/gate/identity/isolation tests pass.
- [ ] New/legacy artifacts load through existing result browsing contracts.
- [ ] A reviewed pilot benchmark exists or is explicitly marked blocked on human review; wiring-only synthetic results are not claimed as gold.

**Bounded manifest evidence (2026-10-20):** Review manifests can now carry optional per-record plus overall content-hash attestations verified fail-closed (tamper rejects the whole manifest; legacy manifests unchanged), distinguishing `manifest_hash_verified_not_identity_authenticated` from asserted/unavailable. This authenticates supplied-content consistency only — not reviewer identity, qualifications, or an external authority; all eligibility guards remain unconditionally false and the genuine reviewed-pilot requirement stays open.
- [ ] Paid calibration, if authorized, follows provider workload permission and D04's approved accounting scope, with per-case records, monthly cost summaries, and explicit usage/cost limitations.
- [ ] Metric/schema changes and legacy comparability limits are documented.

**Rollback:** Keep new artifacts in separate versioned namespaces and preserve the original index. Revert a new reader/runner if needed, but never relabel old cached outputs as valid under a new metric/gate contract.

## Phase 3 — Observability without implicit content export

**Requirements:** R11; usage/identity portions of R06.
**Dependencies:** Phase 2 identity/completeness contract. **Decisions:** D02/D06/D15 before export.

### P3-A: Local tracing and lifecycle

**Package gate update (2026-10-16):** The approved isolated [Logfire compatibility spike](20261016-logfire-compatibility-spike.md) is complete as research, not adoption. Candidate 5.2.0 APIs were probed without network, but full resolution moves OTel and protobuf 4.x to 6.x; review/bounded dependency approval is still required. Automatic body/exception capture and lifecycle timeout limits remain blockers. Frontend frozen-lock installation/type/build checks passed separately. Project locks are unchanged; no application tracing, hosted export, broad SDK upgrade, model download, Pydantic AI/Evals cutover or phase completion is inferred.

**Primary files:** `src/app/{factory,logging}.py`, request-ID middleware, `src/usecases/chat.py`, retrieval/provider boundaries, evaluation orchestration, `pyproject.toml`, `uv.lock`.

- [ ] Resolve and lock minimal Logfire/OTel dependencies; verify compatibility before adopting APIs.
- [ ] Add optional disabled/local/explicit-export configuration, preserving startup without a token.
- [ ] Create correlated request, retrieval, generation, retry/error/cancellation, run, and case spans around the corrected baseline.
- [ ] Record effective model/route, usage availability, phase timings, and cache status; avoid double-counting nested SDK spans.
- [ ] Test exporter failure and bounded flush/shutdown.

**Bounded span-coverage evidence (2026-10-20):** The [second continuation](20261020-admission-manifest-spans-handoff.md) adds privacy-safe independent embedding spans at the owned embedding boundary and stream retry transition markers for all three generation adapters' async stream loops (no span context across generator yields; `outcome="retry"` added to the manual finish API). Logfire/OTel dependency resolution, hosted export, and complete third-party log boundaries remain pending.

### P3-B: Export policy and existing artifact paths

**Primary files:** `src/experiments/{config,wandb_tracking}.py`, `src/app/routes/chat.py`, telemetry integration points, frontend confidence presentation, docs.

- [ ] Implement disabled/local/metadata-only and explicitly approved public/synthetic case-content modes. Allowlist exports, including HTTP attributes, exceptions, tool content, and eval-report data; do not enable blanket body/history capture.
- [ ] Keep local diagnostic artifacts separate from external aggregates; default new raw W&B artifact uploads off. Freeze W&B/custom-dashboard feature expansion while preparing the approved D10 consolidation target.
- [ ] Restrict/disable rich browser traces and document browsing according to data/access decisions; preserve a safe compatibility path for the public-corpus demo if selected.
- [x] Relabel heuristic confidence and state that it is not a probability of medical correctness.
- [ ] Document retention, access, deletion, and third-party processing boundaries; no unsupported claims of automatic PHI scrubbing.

**Bounded existing-path evidence:** New raw W&B artifact defaults are off; explicit metadata/metric payloads are allowlisted and fake-SDK canaries cover normal/error paths. Legacy explicit raw upload remains a warned compatibility path, not certified content approval. Logfire modes/spans, automatic SDK capture, broader browser/artifact controls and complete export-policy verification above remain pending; see the [handoff](20261016-p2-p3-foundation-handoff.md).

### P3-C: Canary verification and optional hosted smoke

- [ ] Insert synthetic secret, cookie, patient-like identifier, prompt, context, and tool canaries into local test fixtures.
- [ ] Assert forbidden secret/identifier/cookie canaries never appear in spans/logs/reports, including error/validation paths. Verify ordinary content fixtures are absent in metadata-only mode and present only in approved public/synthetic-content mode.
- [ ] Once destination/access/retention is configured, run a bounded synthetic hosted smoke and inspect actual stored fields; include the approved case-input/output mode as well as metadata-only coverage.
- [ ] Record destination/region, access policy, and cleanup instructions without tokens.

**Exit:** Baseline traces are useful and correlated; hosted export is optional; exporter outages do not break chat; content-canary tests pass. If hosted access is unavailable, mark hosted verification blocked rather than complete.

**Rollback:** Disable/exporter-select local mode. Preserve local manifests and request behavior; never enable content capture as a fallback for missing telemetry.

## Phase 4 — Pydantic AI adapter plus shared evaluations

**Staged start accepted (2026-10-21):** [Fresh-session pickup brief](20261021-phase4-pickup-brief.md). Primary goal: working opt-in Go chat via Pydantic AI; selected upcoming generator MiMo V2.6 Flash, superseding earlier DeepSeek selection without changing historical snapshots or serving defaults. Offline/isolated P4-A investigation authorized; present dependency diff/capability findings before project-lock changes or P4-B. Schema-validated output required internally and for user-facing generation. No live calls now; P4-D execution and P4-E cutover remain separately gated. **P4-A spike delivered 2026-10-21:** [capability report](20261021-phase4a-capability-spike.md) — latest Pydantic AI blocked by the `openai>=3`/litellm wall; compatible candidates `2.31.0` (recommended, `openai`→2.54.0) and `1.66.0` (zero `openai` change) resolved and offline-probed (14/14 ×2, network denied); owner review pending before any project-lock change. **P4-B delivered 2026-10-21:** [adapter handoff](20261021-phase4b-adapter-handoff.md) — owner approved candidate B and the exact dependency diff (applied byte-identical to the reviewed resolution); GLM implementation → Luna review (three P2) → parent repairs (including a gate-caught transient-classification defect) → Luna closure **CLOSED**; isolated gate **1,846 passed ×2**; opt-in only, no default flip, no live calls. P4-C/P4-D/P4-E remain unstarted; their checkboxes remain unchecked.

**Requirements:** R05/R12/R13 and all earlier contracts.
**Dependencies:** Phases 1–3 exit for integrated comparison. **Decisions:** D03/D04/D07/D10/D16/D18.

### P4-A: Dependency and provider-capability spike

- [x] Resolve Pydantic AI slim/provider extras and Pydantic Evals against Python 3.12/current lockfile in an approved change slice. *Delivered in the authorized isolated spike: full-project scratch resolutions for candidates 2.31.0 and 1.66.0; latest 2.59.0 unsatisfiable. Project-lock application pending owner review.*
- [x] Record exact versions and supported selected routes; avoid adding every provider SDK speculatively. *Exact pins/diffs recorded; only slim `[openai,evals]` extras resolved; no other provider SDKs added.*
- [x] Check sync/async APIs, stream delta semantics, structured-output modes, context-manager ownership, usage reporting, and telemetry content controls against those versions. *Fake-transport probe of 2.31.0: 14/14 checks ×2 fresh sandboxed processes, zero network attempts; see the report matrix.*
- [x] Use D03's selected Go route and owner-reported eligibility. Verify honest `User-Agent` and stable, opaque per-conversation `x-opencode-session` through fake-transport tests across sync/async/streaming/structured paths; isolate case/variant/judge sessions without mutating shared client state. No impersonation, fake tool traffic, or silent `-free`/paid-route substitution. *Headers proven request-scoped against the documented Go base URL; honest app `User-Agent` requires per-request override of the provider default.*
- [ ] Validate endpoint region/model access with explicit credentials only during the separately approved live smoke; account for separate Go subscription/quota versus pay-as-you-go billing. *Deferred by design to P4-D; pay-as-you-go spillover must stay off.*
- [x] If compatibility requires an unrelated major stack upgrade, stop and present alternatives rather than silently expanding scope. *Stopped at the `openai>=3` requirement (litellm/langchain-openai conflict); alternatives presented in the report.*

**Exit:** A small supported capability matrix and a reproducible dependency resolution. No blanket assertion that every OpenAI-compatible endpoint supports the same features. *Both delivered in the [P4-A capability report](20261021-phase4a-capability-spike.md); real Go-route schema/stream behavior and account access remain untested until the gated live smoke.*

### P4-B: Existing-interface generation implementation

**Primary files:** a focused adapter under `src/infra/llm/`, existing `interfaces.py`/factory, `src/app/factory.py`, `src/config/settings.py`, targeted unit/integration tests.

- [x] Implement current protocol sync/async/text-stream/structured generation using Pydantic AI. *Delivered in `src/infra/llm/pydantic_ai_client.py` (sync-in-loop restriction documented as a material difference).*
- [x] Separate implementation selection from provider and agentic harness selection. *Provider literal `pydantic-ai` + explicit model settings; no agent harness introduced.*
- [x] Reproduce current prompt/history/context behavior for matched tests; record material differences rather than hiding them. *Exact `build_medical_messages`-equivalent prompt asserted by test; confounds recorded in the adapter docstring and P4-A/B reports.*
- [x] Reuse/close owned provider/model/agent resources correctly. *One owned `httpx.AsyncClient` per client, closed by `aclose()`; pydantic-ai does not close injected clients.*
- [x] Preserve stable SSE/history/citation behavior and partial-output retry restrictions. *Chat wiring change is scope-wrapping only; no-retry-after-emitted-delta asserted by test.*
- [x] Add offline test/function-model coverage, a deny-live guard, and provider-client contract tests. *23 fake-transport cases + `deny_live_models` fixture (sets/restores `ALLOW_MODEL_REQUESTS`); TestModel/function-model coverage proven at the P4-A probe level.*
- [x] Keep existing clients selectable; no default flip in this slice. *Default provider remains `qwen`; existing clients unchanged.*

**Acceptance:** Fake/model-contract tests pass for both implementations; current clients need no new hosted token; unsupported schema/request settings fail clearly; actual model identity is correct in diagnostics and cache keys. *Fake-transport contract tests pass for the adapter and all existing clients (gate 1,846 ×2); existing clients need no new token; unsupported modes/invalid settings raise; `self.model` identity feeds the existing telemetry/diagnostics path. Live route/schema behavior and judge-role wiring remain P4-D/P4-C exits.*

### P4-C: Pydantic Evals tasks and output compatibility

**Primary files:** focused task/evaluator integration under `src/evals/`, existing assessment/CLI composition, artifact adapters/readers, multi-turn integration tests.

- [x] Evaluate plain-Python baseline and adapter tasks on the same frozen cases/index/prompt settings. *Offline machinery delivered ([P4-C handoff](20261021-phase4c-evaluation-tasks-handoff.md)): identical frozen inputs and one normalized result model for both implementations, proven with fake transports; an actual scored corpus run stays blocked by D11 corpus/index materialization.*
- [x] Reuse repaired retrieval metrics and existing DeepEval definitions during calibration; avoid duplicate rubrics. *`MedicalMetricEvaluator` bridges the existing `METRIC_SPECS`/`create_medical_metrics` definitions — no rubric restated; a source-text test guards it.*
- [x] Save normalized per-case outcomes/usage/timings and required-evaluator completeness into the existing artifact contract. *Projected per-case outcomes, usage snapshots, timings and R07 completeness are written through the existing `ArtifactStore`; missing/skipped/errored/failed can never report complete.*
- [x] Replay real user/assistant conversation sequences with isolated sessions. *Isolated per-case session replay with fresh generated ids is delivered; real assistant-turn history and contextual-turn metrics remain D13.*
- [x] Ensure automatic Pydantic Evals/Logfire export obeys Phase 3's content restrictions; test report export, not just model spans. The documented integration exports case inputs/outputs: D10 permits approved public/synthetic content, but verify mode-specific allowlists in the pinned version and prevent forbidden secret/patient data from leaking in either mode. *Verified in 2.31.0 (`ReportCase.inputs/output`, aggregate label keys) and gated: case content, judge reasons, string label values and aggregate label keys export only under `approved_public_synthetic_content` + `content_approved`; canary tests cover all four modes plus approval. No Logfire report export is wired.*
- [ ] Keep old evaluation CLI behavior readable/explicit while documenting new proposed command/config selectors when implemented. *Legacy CLI behaviour is unchanged; the new runner is programmatic-only (`build_dataset` → `run_dataset` → `project_report`/`write_report`) because a selectable harness needs materialized corpus/index content (D11). Selector wiring is deferred to P4-D. Intended selector shape now recorded docs-only (no wiring): [offline leftovers handoff](20261024-offline-leftovers-handoff.md).*

**P4-C delivered 2026-10-21:** [evaluation-tasks handoff](20261021-phase4c-evaluation-tasks-handoff.md) — DeepSeek V4.1 Flash implementation → GLM-5.3 Flash review (two P1, one P2, six P3) → parent repairs → closure review **CLOSED**, then three post-closure repairs (metric cleanup ownership, `error_type` projection, bounded runner concurrency); isolated gate **1,903 passed ×2**; statics clean. `judge_provider: pydantic-ai` is now wired end-to-end offline (wrapper, credential, model names, endpoint validation, honest attempt accounting) and remains opt-in. No default flip, no live calls, no CLI selector flip; generation on that route stays fail-closed until P4-D decides.**

**Offline leftovers (2026-10-24):** [handoff](20261024-offline-leftovers-handoff.md) — six collected offline tests: P4-B settings-bound acceptance (`pydantic_ai_temperature` 0.0/2.0, `pydantic_ai_timeout_seconds` 600.0), stream-cancellation usage settlement (no fabricated partial totals, no retry, transport released), repeated sync-call lifecycle reuse, and P4-C task-layer upper-bound override pass-through (`temperature=2.0`, `timeout_seconds=600`); isolated gate **1,969 passed / 5 warnings ×2**; statics green (Ruff 346 files, MyPy 164 src, 4 import contracts). Owner decision recorded: `provider="pydantic-ai"` generation preflight/`effective_roles` **stay fail-closed**. No behavior changes.

### P4-D: Matched live parity and CI

- [ ] Run a tiny approved same-model/same-route smoke for both implementations: text, stream, structured output, cancellation, and one real RAG case.
- [ ] Compare effective messages/settings and record unavoidable confounds. Equal text is not required for stochastic outputs; transport/schema/content-contract correctness is.
- [ ] Run the approved pilot with fixed judge and matched cases. Compare quality, completion, time to first token, total latency, token/cost estimates, and developer experience.
- [ ] Add offline PR gates with evaluation/provider extras installed; require no paid credentials for those tests.
- [ ] Add manually dispatched, budgeted live CI only if D16 approves; never expose secrets to untrusted pull-request execution.

**Exit:** Both implementations have usable comparison results with complete required measurements, or explicit blocked live checks. The adapter remains opt-in unless D08 promotion is separately approved.

**Rollback:** Select corrected existing clients and disable new adapter/task entrypoints. Preserve new artifacts; do not delete providers or silently translate new results into legacy scores.

### P4-E: Approved primary-UI/runner consolidation target (bounded implementation approval required)

- [ ] Make Pydantic Evals the main runner and Logfire the primary experiment UI after P4-D parity evidence; preserve the repaired metric definitions rather than cloning a second scoring stack.
- [ ] Retain versioned datasets/prompts/configuration, a small local run manifest/report, and R15 cost summaries; document offline operation/export recovery. Optional remote dataset storage is a separate access/content choice.
- [ ] Archive legacy results unchanged. In a bounded approved cutover slice, retire redundant W&B writes/custom evaluation-dashboard/API paths; preserve the chat/SSE application contract.
- [ ] Document supported CLI transition, historical access, retention, and rollback. No deletion or unrelated legacy-client rewrite is bundled into adoption.

**Acceptance:** One primary evaluation/visualization path without lost provenance, automatic content export, or indefinite dual-stack maintenance. D10 approves the consolidation direction; execute the actual cutover only after parity and a bounded change-plan approval. It need not wait for agentic work.

**Rollback:** Restore the corrected baseline runner/archived-reader configuration with content export off; preserve new reports and provenance.

## Phase 5 — Optional agentic exploration and promotion decision

**Requirements:** R14 and prior comparison/privacy/budget contracts.
**Dependencies:** Phase 4 evidence and explicit Phase 5 scope approval. **Decisions:** D05/D07/D08/D12/D13/D18.

### P5-A: Bound one useful hypothesis

- [ ] Choose a concrete task class where a loop may help, such as contextual follow-up retrieval or clarification when required information is missing.
- [ ] Approve one read-only corpus retrieval tool, its schema, citation IDs, and scenario-specific trajectory expectations.
- [ ] Define maximum calls/tokens/time/concurrency and approved routing; clarify behavior on tool failure, empty evidence, or budget exhaustion.
- [ ] Keep native history, rewriting, structured answers, and citation validation as separately named variants rather than one unexplained bundle.

### P5-B: Implement at the use-case boundary

- [ ] Add only the selected orchestration; reuse retrieval/store/source metadata and existing SSE response translation.
- [ ] Validate tool inputs/results and citations; do not reveal private reasoning traces.
- [ ] Enforce data-access and prompt-injection boundaries for retrieved content.
- [ ] Test loops, excessive/repeated calls, cancellation, partial streams, malicious documents, absent evidence, and cross-session isolation.

### P5-C: Evaluate and decide

- [ ] Run deterministic, retrieval, actual multi-turn, and reviewed safety suites against the same-model deterministic control.
- [ ] Use span/trajectory evaluators for scenario contracts, not as a substitute for answer/evidence checks.
- [ ] Report full failures, sample sizes, confounds, uncertainty, cost, latency, and practical debugging/maintenance observations.
- [ ] Apply predeclared D08 criteria. Record keep-as-experiment, promote, revise, or reject; no automatic winner/default update.
- [ ] If promotion is approved, stage rollout with an explicit fallback to the corrected deterministic control and documented operational limits.
- [ ] Consider remaining redundant clients/DeepEval dependencies only in a separate approved cleanup after metric parity; W&B/custom-dashboard consolidation may already have occurred in approved P4-E and need not wait for agentic work.

**Exit:** A written evidence-based decision. Keeping the agent opt-in or rejecting it is a valid successful outcome.

**Rollback:** Select the deterministic control; stop tool execution and new live experiments; preserve the evidence and data policies. Do not roll back to broken runtime/configuration behavior.

## Verification ladder for implementation slices

Use the existing environment or approved dependency sync. Do not run these as paid experiments implicitly.

1. Targeted new regression/contract tests with fake providers and temporary data.
2. Existing unit/integration tests with explicit marker filters and a deny-network/deny-model guard.
3. `uv run ruff check .` and `uv run ruff format --check .`.
4. `uv run mypy src/` and `uv run lint-imports`.
5. `bash scripts/check_docs_consistency.sh`, plus local Markdown-link validation for this package.
6. Frontend checks/tests when response types, diagnostics, or auth UI changes.
7. Real-lifespan/container smoke with synthetic data when lifecycle/deployment changes.
8. Separately authorized live/provider/hosted-export checks with explicit limits and saved results.

Do not claim a full gate passed when dependencies caused relevant tests to skip. Record skipped/deselected counts and why each missing check matters. The prior review's passing test counts are historical, not permanent acceptance thresholds.

## Per-slice implementation handoff template

- Slice/task IDs and approved decisions:
- Requirements satisfied and deliberate behavior changes:
- Files changed:
- Tests/commands/results, skips, and dependency versions:
- Artifact/schema/cache compatibility effects:
- Any live calls/export, approved limits, actual usage, and unknown cost:
- Rollback instructions:
- Remaining blockers and next bounded slice:
