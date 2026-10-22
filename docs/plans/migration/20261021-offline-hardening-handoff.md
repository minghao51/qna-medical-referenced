# Offline hardening closure — 2026-10-21

Approved follow-up to the [T7 boundary handoff](20261021-t7-boundaries-handoff.md). T1–T7 remain delivered; this is not whole-phase or operational certification.

## Delivered

- `src/rag/hyde.py` and `src/rag/query_expansion.py`: removed raw query/prefix and exception strings from the owned success/error logs. Events contain fixed text and numeric counts only. Returns, fallback behavior and cancellation semantics unchanged; pre-existing asynchronous retrieval work retained.
- `tests/unit/rag/test_hyde_log_privacy.py`: seven tests exercise success/failure in both modules, functional outputs, fallback behavior, cancellation, canary absence and absent exception capture. Added to the explicit isolated gate inventory.
- Updated current data-processing documentation to describe the repaired paths without claiming global privacy protection.

## Assessed; deliberately not changed

- **Review-context reuse:** retained repeated validation in the orchestrator/evaluator path. Some recomputation is redundant in the current flow, but caching shared mutable context introduces staleness/integrity coupling; no new abstraction or helper-signature churn was justified for this cleanup. Existing fail-closed checks remain intact. This residual is accepted for this bounded slice, not falsely reported as optimized away.
- **API-key masking:** no type migration. App authentication directly JSON-parses/splits plain-string settings; preflight already supports secret unwrapping. A future `SecretStr` migration needs coordinated authentication consumers and the configuration type-expectation test. Existing no-key development behavior remains unchanged.

## Verification and preservation

GLM implementation and read-only assessment → Luna review: **approve**, no actionable slice-attributable findings. Complete reviewer evidence: `/tmp/qna-eval-final-hardening-qkd6ey/review.md`; assessments and implementation report alongside it.

Parent checks: Ruff/format (337 files), MyPy `src` (160 source files), four import contracts, docs consistency. Offline isolated gate **1,794 passed / five warnings ×2** in fresh processes; logs `gate-final.log` and `gate-final-repeat.log` in the snapshot. Closing preservation checker verifies out-of-scope tracked patches, existing untracked bytes, status-path retention, new-path allowlist and unchanged lock digests. HEAD remains `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`; no commits/reset/stash/clean, credential inspection, live calls, data deletion, dependency/default changes or hosted setup.

## Explicit remaining work

A separate **pre-existing P2** was confirmed during assessment and review: preflight can report a legacy SHA256 API-key record ready while production runtime rejects it (`src/cli/preflight.py` versus `src/app/security.py`). Fixing that mismatch was not part of the approved logging/assessment scope; it was subsequently closed in the [auth-preflight parity follow-up](20261021-auth-preflight-parity-handoff.md) with regression tests. Masking migration is optional coordinated hardening, not delivered here.

Operational exits remain unchanged: named review-authority exercise, corpus/index materialization and provenance, judge pinning/matched baseline, budget limitations, hosted destination/access/retention configuration and permissioned smoke, Docker smoke, reranker assets and live baselines. Phase 4 remains excluded. Automatic body/exception capture stays off; eligibility guards remain false.
