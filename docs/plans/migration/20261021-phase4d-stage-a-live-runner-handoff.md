# P4-D Stage A live-runner handoff — gated live path delivered; run still gated

**Status: the gated live-capable runner is delivered and review-CLOSED (Luna, three rounds). No live call has been made.** Executing Stage A still requires the owner's final stage-specific run confirmation after the frozen hashes, effective settings and numeric reservations below. The owner's account confirmations (execution-addendum items 1-3: route/workload eligibility, ≥$1 included quota with spillover/top-up off, runtime-secret credential source) were recorded in-session on 2026-10-23 and are operator attestations, not code-verifiable facts.

## Delivered (this slice)

- `scripts/manual/phase4_go_smoke.py` — gated live mode: `main(["--live", "--owner-confirmed"])` resolves the credential ONLY from `APP__LLM__PYDANTIC_AI_API_KEY` in the environment (never argv, never `.env`, placeholder-denied); `authorize_stage_a_live` is the single gate; `StageALiveRun` is a provenance-enforced handle (module-private token; direct construction raises `unauthorized_live_run_handle`) with a fixed redacted repr, so no supported entry path reaches client construction without both gates, and no path can print the key.
- `LiveGateTransport`/`AsyncLiveGateTransport` (lazy via cached factory + PEP 562 `__getattr__` to preserve the lightweight-import probe): identical identity-header validation as the offline gate — exact per-implementation honest `User-Agent`, exact opaque `x-opencode-session`, and a raw-conversation-id substring scan across URL, header names, header values and body — plus the shared admission gate (exact route allowlist, ASCII 4096-byte ceiling, 12-POST cap, Decimal reservations) ALL BEFORE delegation. A refused request never leaves the process.
- `build_baseline_qwen_client_live` / `build_adapter_pydantic_ai_client_live`: mirror the offline builders (per-instance settings views, `max_retries=0`, `trust_env=False`, no redirects) with the gated live transports; transports are tracked from construction inside the awaited-cleanup `try` block, so no construction-failure path leaks a delegate.
- `cancel_stream_live`: best-effort live cancellation (first nonempty delta, settle window, task cancel, no retry after content). WHERE the cancel lands is not deterministic without offline signals and is NOT claimed; the blocked-read delivery proof remains owned by the offline tests.
- `run_stage_a_live` runs the same nine operations (`_STAGE_A_OPS_LIVE`, timed) and returns sanitized metadata with honest live values: `transport_mode: "live_https_gate"`, `handler_boundary: "live_https_delegate_gate_only_no_retention"`, `quota_rates_basis: "p4a_historical_reference_not_verified_billing"`, per-op `duration_seconds`/`first_delta_seconds`, digests only.
- `tests/unit/infra/test_phase4_go_smoke.py`: 31 added cases (synthetic delegates only, zero network): CLI refusals incl. placeholder keys, authorize refusals, forgery/redaction, transport refusal matrix (headers, route, caps, byte ceiling, raw-ID variants), one-POST identity checks, structured-mode wire selection, cancel helper contract, builder failure-injection cleanup (both constructors and second-transport failure), metadata canary/key/session absence. Existing 27 cases untouched.

## Review and verification

GLM worker implementation; Luna read-only review ×3. Round 1: P1 raw-key runner bypass plus P2s (false offline `handler_boundary` in live metadata, incomplete raw-ID enforcement, transport cleanup gap, stale operator/docs text). Round 2: P1 refined — handle forgeable; plus construction-ordering gap and repr exposure. Round 3: **CLOSED** (structural provenance token, immediate per-transport tracking, redacted repr; no new findings). Parent repairs were made between rounds; the stale offline-handoff/addendum "no live runner" lines are superseded by this document.

Parent-owned fresh isolated gates: **1,961 passed / five warnings ×2** in fresh bwrap processes; Ruff check + format 346 files, MyPy `src` 164 files, docs consistency — all passing. Snapshot: `/tmp/qna-stage-a-live-slice-1792804284/` (ephemeral). Dependency lock digest unchanged: `7d63f1ce0a02249c2efe7c2ef3de1c37c3eb1d770d278a7ad5845865eb8d6499`.

## What a live run still requires (in order)

1. Owner reviews the frozen inputs, effective settings and reservations below.
2. Owner gives the stage-specific run confirmation in chat.
3. **The owner** runs, in their own shell (key exported by them, never pasted in chat or argv):
   `python scripts/manual/phase4_go_smoke.py --live --owner-confirmed`
   Output is sanitized JSON metadata only (digests, counts, timings, Decimal reservations). Any route/account rejection, unknown quota accounting or unexpected charge → stop, no substitution, report incompleteness.

## Frozen Stage A wire contract (unchanged from the addendum)

- Route `https://opencode.ai/inference/go/openai/v1` / `chat/completions`, model `mimo-v2.6-flash`, temperature 0.7, max output 2048, 30 s request timeout, 30-minute overall stop, one total transport attempt, ≤1 structured repair per structured op, 12-POST global admission cap.
- Frozen input hashes are recorded in every run's metadata (`frozen_hashes`: system prompt, user-prompt template, both fixed prompts, canonical answer schema); the exact outbound body of every admitted request is frozen as a SHA-256 digest in `admission`/per-op `payload_sha256`.
- Reservations at `LIVE_REFERENCE_RATES` (historical P4-A reference $0.14/M input, $0.28/M output — NOT verified billing): per-call reservation ≈ $0.000629 quota-value; 12 admitted calls ≈ **$0.0075 quota-value ≈ 0.75% of the $1 allocation**; cash reservation $0 (confirmed no cash billing). Missing usage retains its reservation. These are admission bounds, not provider billing guarantees; Go quota conversion remains owner-attested.
