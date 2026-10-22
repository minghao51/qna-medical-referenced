# Admission, manifest and span coverage — 2026-10-20 (second continuation)

**Status: bounded implementation slice; whole Phases 1–3 remain incomplete.** Continues the approved remaining plan after the [evaluation-tracing handoff](20261020-evaluation-tracing-handoff.md). That handoff and the [2026-10-19 integration handoff](20261019-phases-1-3-integration-handoff.md) remain historical evidence and constraint sources.

## Scope and preservation

Fresh snapshot: `/tmp/qna-eval-admission-spans-K4T7WQ`. It contains the starting diff/status/untracked hashes/lock digests, the four Luna task briefs and reports, the integrated reviewer output, and the isolated gate logs. The working tree's further preexisting Docker/frontend/configuration work was retained and is not attributed to this slice. No reset/stash/clean/commit, model/provider/profile switch, dependency installation/change, existing-data migration/deletion, credential inspection, or live/hosted export occurred. HEAD remains `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`; both lock digests are unchanged from the snapshot.

Four disjoint implementation tasks ran as explicit `openai-codex/gpt-6-luna` (`xhigh`) subagents under exclusive file ownership; the parent owned `src/infra/telemetry.py`, integration, and all OS-network/storage-isolated tests. Agent reports are not test evidence. Independent review used the `zai/glm-5.3-flash` reviewer on the slice-attributable diff.

## Changes

### Independent embedding spans

- The owned embedding boundary (batch ingestion `embed_texts_with_stats`/`_create_embeddings_with_retry`, store batch/query embedding including the injected query hook and BM25 fallback, and the chunking wrapper delegation) now emits privacy-safe `Operation.EMBEDDING` child spans: fixed enums, fresh UUID attempt IDs, model name, input/result counts, elapsed ms, SDK usage completeness, and fixed error codes.
- Only actual subsequent attempts are `RETRY`; the terminal transient attempt is labelled `RETRY_EXHAUSTED` including when the first attempt is the only one. Non-transient terminal failures remain `UPSTREAM`. Outer wrapper spans keep the existing classification.
- No content, source/doc/chunk identifiers, exception text, or lengths enter spans; parents keep their existing attributes (no SDK-usage double counting). Embedding calls, retry policy, cache semantics, and scheduling are unchanged.

### Stream retry transition spans

- The three generation adapters' existing async stream retry loops now emit a manual `Operation.RETRY` transition marker only after a first failed attempt that is transient, emitted nothing, and will actually be retried.
- The span starts after the failed attempt's usage finalization and finishes (`outcome="retry"`, fixed timeout/upstream classification, fresh attempt ID, actual retry count) synchronously before the backoff sleep; it never wraps an await that can yield, the loop, or cleanup tasks. The parent added `outcome="retry"` to `TelemetrySpan.finish()` (error status semantics preserved); no other telemetry semantics changed.
- Fire-and-forget stream cleanup, cancellation, consumer-backpressure accounting, attempt/backoff policy, and final exhaustion behavior are unchanged. Non-stream paths are untouched.

### Generalized budget admission

- `paid_operation_budget_status(records, *, utc_month, operation, ...)` evaluates any named recorded paid operation against the same shared monthly summary with the same fail-closed reason set (overage unconfirmed, incomplete usage/cash, empty month, `known_cash >= ceiling`); `paid_benchmark_budget_status` remains a byte-compatible wrapper pinned by dict-equality regression.
- The offline usage diagnostic reports admission for the benchmark class and for recorded diagnostic execution modes without running an assessment; run-manifest `execution_mode` is carried into in-memory records only (persisted schemas unchanged). Legacy records without `execution_mode` cannot be classified beyond benchmark.
- Explicit limitations are retained and extended: local records are not an operational USD-20 hard cap; interactive chat serving is not budget-gated; in-flight/delayed/outside-repository charges and automatic provider overage remain unverifiable.

### Hash-verified review-manifest attestations (mechanism only)

- Review manifests may now carry an optional `attestations` block (per-record canonical content hashes plus an overall content hash) verified alongside the existing dataset/corpus checks. Verification outcomes: `unavailable`, `manifest_asserted_not_authenticated` (legacy manifests, byte-identical behavior), or `manifest_hash_verified_not_identity_authenticated`.
- Any tampered record, mismatched overall hash, or malformed shape rejects the whole manifest exactly like an invalid manifest today (existing trusted-manifest exclusion path, reason `trusted_review_manifest_hash_verification_failed`), proven for multi-case manifests.
- `reviewed_evidence_eligible`, `cohort_eligible`, and `promotion_eligible` remain unconditionally `False`; hashes authenticate supplied-content consistency only, never reviewer identity, medical qualifications, or an external review authority. The orchestrator identity snapshot now records the computed status through three bounded edits (schema allowlist, status parameter, call-site computation).

### Parent integration repairs

- `TelemetrySpan.finish()` retry outcome (above); the isolated-gate inventory gained the four new test files; the integration `fake_chroma_embeddings` fixture now patches the embedding-module boundary plus the store's imported binding after the store consolidated on `embed_texts_with_stats`.
- Reviewer-driven fixes: terminal-embedding error-code regression (two parameters), generalized ceiling fail-closed regression, multi-case manifest tamper regression, top-level import placement, fixture docstring.

## Verification

Reproduce with **`bash scripts/verify_phase123_offline.sh`** (bubblewrap; network and repository data access denied before imports; storage private; credentials synthetic; no bare-pytest fallback). New test files are in the durable explicit inventory.

- Pre-slice gate: **1,622 passed / five warnings**.
- First integrated gate: **1,663 passed / two collection errors + five failures** (parametrize signature, optional-`chonkie` import, partial store fixtures, over-strict cleanup assertion, stale fixture boundary) — all repaired by the parent, none silently counted.
- Final gate and a fresh-process repeat: **1,673 passed / five warnings each**, zero skips/deselections.
- Ruff lint/format: **330 files**; MyPy: **159 source files**; four import contracts kept. Inherited Requests-compatibility warning appears before pytest as before.
- Independent `zai/glm-5.3-flash` review of the slice diff: contract verification passed (privacy, no cross-yield context, fail-closed manifest, budget parity, no double counting); one P1 (stale gate evidence, resolved by the fresh final/repeat logs) and P3s — three fixed as regressions/repairs above; noted-not-changed: broad `UPSTREAM` labelling of non-transient embedding failures, `_usage_budget_status` duplication, triple `_review_context_parts` recomputation, and residual test blind spots (429-status transient classification, empty-input span, outer-span usage-absence assertion).

## Remaining phase exits

- Reviewer authenticity is **still not identity-authenticated**: the new attestations verify content consistency only. `reviewed_evidence_eligible=false`, cohort/promotion guards, and the independent review-authority/pilot requirement are unchanged. Numeric qrel diagnostics are not clinical endorsement.
- Budget admission remains incomplete: admission is informational/fail-closed against local records; diagnostic modes are covered only when `execution_mode` is recorded; chat serving, delayed/in-flight/outside-repository charges, and automatic overage are not covered; no USD-20 hard-cap guarantee.
- Embedding spans now exist at the owned boundary, but complete third-party log/export boundaries, hosted destination/access/retention verification, and broad telemetry privacy certification remain open.
- Docker image/container smoke, optional reranker assets/runtime, matched generation/judge live baseline, independently reviewed frozen pilot, and provider/access/billing verification remain blocked or separately permissioned.
- No live model/embedding/judge calls, hosted export, corpus/model downloads, defaults change, deployment, real patient data, or Phase 4 is authorized by this continuation.
