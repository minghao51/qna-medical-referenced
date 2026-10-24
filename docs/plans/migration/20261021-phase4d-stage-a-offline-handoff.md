# P4-D Stage A offline harness handoff

**Status: offline harness delivered; live execution unavailable and blocked.** Owner approved the bounded harness slice after selecting Stage A only: at most $1 included Go quota value, $0 incremental cash. No account safety confirmations, current quota valuation or final live-run permission are inferred from credential preparation or “proceed.”

## Delivered

- `scripts/manual/phase4_go_smoke.py`: injectable, trusted synthetic-handler harness exercising actual existing Qwen and Pydantic AI async client paths for nine logical operations. SDK requests use harness-created MockTransport; arbitrary handlers are trusted Python code, not sandboxed. Run only with synthetic keys under OS network/storage isolation. CLI always refuses live execution.
- Exact-route/model/settings/header checks; shared 12-POST admission; one total transport attempt and one structured repair; sanitized metadata with exact outbound-body digests; deterministic blocked-read cancellation and cleanup; per-instance method-global copies avoid changing application module settings. This method-copy approach is maintenance-sensitive and covered by retry/isolation tests, not a new production client implementation.
- `tests/unit/infra/test_phase4_go_smoke.py`: 27 added cases, synthetic transport only; explicit isolated-gate inventory entry in `scripts/verify_phase123_offline.py`.
- Failure construction cleanup is awaited on the owning loop. SDK and supplied HTTP resources may both close idempotently; tests require every close to finish before the failure escapes.

The ASCII 4096-byte ceiling is an **offline payload-shape bound, not a verified model input-token bound**. Decimal reservations are simulated accounting only. Provider chat-template overhead, hidden/reasoning tokens and current quota conversion remain unverified; no live $1 enforcement or $0-cash guarantee is claimed.

## Review and verification

GLM worker, Luna read-only review, worker repairs and parent gate repairs; final Luna verdict **CLOSED** for the remaining two P2 findings under the explicitly narrowed trusted-handler/OS-isolated scope. Initial findings included injected transport bypass, failure continuation, false byte/token bound, global settings swaps, ineffective cancellation, header enforcement, payload hashes and construction cleanup. Repaired before final gates.

Parent-owned fresh isolated full gates: **1,930 passed / five warnings twice**. Ruff check and format all files, MyPy `src` (164 files), four import contracts and docs consistency passed. No application imports/tests outside the approved isolation; no live calls, secret inspection or dependency changes.

Snapshot, verbatim worker/review responses and gate logs: `/tmp/qna-stage-a-harness-JvI1Rb5G/` (ephemeral). Final review: `luna-final-closure.md`; final gates: `gate-6.log`, `gate-7-repeat.log`. Snapshot preserves pre-existing documentation and `.env.example` changes; no prior untracked source was overwritten. Project-lock digest remains `7d63f1ce0a02249c2efe7c2ef3de1c37c3eb1d770d278a7ad5845865eb8d6499`.

## Still blocked

See [execution addendum](20261021-phase4d-stage-a-execution-addendum.md) and [planning pack](20261021-phase4d-approvals-pack.md). A live-capable transport/runner is **not implemented**. It needs separately approved implementation with verified model/provider token accounting, quota reservation and actual account eligibility/remaining quota/spillover/top-up confirmations, then final stage-specific execution approval. No existing offline helper may be repurposed with a network-forwarding handler as a bypass.

B/C remain unapproved and blocked on their corpus/embedding/judge/review/configuration prerequisites. No eval selector widening, hosted export, live CI, default flip or phase completion.
