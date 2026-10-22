# Evaluation tracing continuation — 2026-10-20

**Status: bounded integration and verification; whole Phases 1–3 remain incomplete.** Continues the already approved remaining plan. Preserve the earlier [integration handoff](20261019-phases-1-3-integration-handoff.md) and [configuration-only snapshot](20261019-baseline-configuration.json) as historical evidence, not fresh source/runtime/quality baselines.

## Scope and preservation

Fresh snapshot: `/tmp/qna-eval-tracing-91x1U2RV` (pointer `/tmp/qna-eval-tracing-current`). It contains the starting diff/status/untracked hashes/lock digests, bounded agent tasks/reports, independent review and isolated gate logs. The working tree contained further preexisting Docker/frontend/configuration work at this resumption; it was retained, not attributed to this slice. No reset/stash/clean/commit, model/provider/profile switch, dependency installation/change, existing-data migration/deletion, credential inspection, or live/hosted export occurred. Final preservation check retained every original status path and out-of-scope tracked/untracked byte; both locks stayed identical to the fresh snapshot. HEAD remains `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`.

Implementation slices were disjoint; separate read-only review used explicit `openai-codex/gpt-6-luna` / `xhigh`. Parent owns integration and OS-network/storage-isolated tests. Agent reports are not test evidence.

## Changes

### Evaluation owner and correlation

- Default remains **disabled**. With existing `APP__TELEMETRY__MODE=local`, an otherwise authorized evaluation owns a fresh bounded in-memory metadata sink and writes best-effort **`telemetry_metadata.json`** into its new run directory. Tracing is not permission to run a paid/live evaluation.
- Hosted settings alone do **not** create a new evaluation exporter. An explicitly supplied existing telemetry owner is reused, not closed or copied to a local artifact by the evaluation.
- Actual `ArtifactStore.execution_id` binds the root run span and child work, including replay. Contexts restore between attempts; no second identity/store is invented. Early validation failures without a store do not claim an artifact execution ID.
- Local output is explicitly a **bounded tail**, not a complete trace/export recovery log. Capacity and cleanup result are recorded; earlier spans may be evicted. Only owned local metadata is serialized, without raw exception events/descriptions/resource dumps/content. Write/cleanup failures cannot replace the business result or primary cancellation.
- Root usage counts come only from the existing run SDK accumulator. Missing dimensions remain absent/unknown; known partial counts are labelled partial. These are observed SDK counts, not pricing/billing completeness or an operational cash cap.
- Answer retrieval/generation/judging operations share fresh opaque case IDs; retrieval-only cases also get fresh IDs. Source/dataset case identifiers are never used, even if they happen to pass the identifier validator. Case correlation is through stage attributes; this slice does not fabricate a single case-parent span across helper lifetimes.
- UUIDv4 canonical and hex formats both validate, including digit-heavy generated execution IDs. Other identifier/privacy checks remain in place.

### Attempts and handled failures

- Outer medical metric attempts have fresh attempt IDs; only an actual subsequent attempt is `retry`, with its known retry index. No retry/model/token/prompt/timeout/concurrency policy was changed.
- Existing Qwen/Gemini/LiteLLM **non-stream** retry paths emit safe spans only after the first failed attempt. No SDK/framework usage is double-counted and no span context crosses a generator yield. Stream retry loops remain explicitly uninstrumented.
- A metric's reported error or invalid score is now marked with a fixed error code before leaving its attempt span. Handled failure is sticky: normal context exit cannot relabel it successful. Cancellation can still take precedence, and no error body is exported.

### Supported production logging

- Production launcher explicitly sets `access_log=False` so Uvicorn's default raw path/query/client access log is not a second unfiltered request log.
- The owned request log retains standard HTTP method names and maps arbitrary method tokens to `OTHER`. Generated request IDs and route templates remain.
- This is scoped to the supported production launcher/owned logger. Other launchers, unhandled framework errors, third-party logging and general PHI/DLP protections are not certified.

### Synchronous cleanup

- `Telemetry.close()` and async close share one lifecycle worker/state. Synchronous evaluation owners can close inside or outside an existing event loop without creating a temporary loop.
- A caller timeout does not terminate the exporter worker or prove cleanup finished. Repeated close waits reuse the admitted worker; thread-start failure is non-throwing/retryable. No hard provider-close deadline or charge-reversal promise is added.

## Verification

Reproduce with **`bash scripts/verify_phase123_offline.sh`**. It requires bubblewrap; network and repository data access are denied before imports, storage is private, credentials synthetic, and inherited explicit legacy HyDE nodes remain selected. There is no bare-pytest fallback. New test files are in the durable explicit inventory.

- Fresh pre-slice gate: **1,530 passed / five warnings**.
- First integrated gate: **1,615 passed / two failures**, both missing async test markers, not quietly counted as passes.
- After marker correction: **1,617 passed / five warnings**, zero skips/deselections.
- Independent review found two P2s: handled judge errors appeared successful; replay bypassed run-ID/store binding. Both were repaired with additional regressions. Repair gate and a fresh-process repeat: **1,622 passed / five warnings each**, zero skips/deselections. Separate Luna `xhigh` re-review: **“No new actionable findings”** in those corrections; this is not phase-wide clearance.
- Ruff lint/format: **306 files**; MyPy: **159 source files**; four import contracts (19 ignored import edges) passed after repair revalidation. Inherited Requests compatibility warning also appears before pytest.
- No frontend code changed in this slice. Prior browser/frontend results remain historical; they are not a fresh container/provider/clinical pass.

## Remaining phase exits

- Reviewer authenticity is still **not authenticated** by a JSON manifest/hash. `reviewed_evidence_eligible=false`, cohort/promotion guards and the outstanding independent review-authority/pilot requirement remain unchanged. Numeric qrel diagnostics are not clinical endorsement.
- Runtime budget admission is not complete. Existing benchmark CLI budget checks/local monthly summaries do not cover every diagnostic/programmatic/chat operation, delayed/in-flight/outside-repository charge, or automatic provider overage. Exact Console/account/billing checks remain unavailable; no USD-20 hard-cap guarantee.
- Embedding remains inside the owned search boundary; independent embedding spans, stream retry coverage and complete third-party log/export boundaries remain open. No blanket telemetry privacy certification.
- Actual Docker image/container smoke, optional reranker assets/runtime, matched generation/judge live baseline, independently reviewed frozen pilot, provider/access/billing and hosted destination/access/retention verification remain blocked or separately permissioned.
- No live model/embedding/judge calls, hosted export, corpus/model downloads, defaults change, deployment, real patient data or Phase 4 are authorized by this continuation.
