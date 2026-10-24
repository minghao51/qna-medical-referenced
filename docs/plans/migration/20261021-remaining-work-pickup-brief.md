# Remaining-work pickup brief — leftover stages after Stage A closure

*Updated 2026-10-23 after Stage A execution and closure (owner accepted incomplete: structured rejected). Supersedes the previous version of this brief in place; it remains documentation only and grants no new implementation, dependency, live-call, export, or default-switch permission by itself.*

## Start here in a new session

Read `AGENTS.md`, the relevant `.planning/codebase/` references, this brief, [decisions](decisions.md), [phases](phases.md) (open exits per phase), R05/R12–R15 in the [implementation spec](implementation-spec.md). Phase 4 history (all closed, do not redo): [P4-A capability report](20261021-phase4a-capability-spike.md), [P4-B adapter handoff](20261021-phase4b-adapter-handoff.md), [P4-C evaluation-tasks handoff](20261021-phase4c-evaluation-tasks-handoff.md), [P4-D approvals pack](20261021-phase4d-approvals-pack.md), [Stage A offline handoff](20261021-phase4d-stage-a-offline-handoff.md), [gated live-runner handoff](20261021-phase4d-stage-a-live-runner-handoff.md), and the [Stage A live run record](20261023-phase4d-stage-a-live-run-record.md) — the latest verified checkpoint.

**Purpose of this brief:** start the remaining work in a fresh thread. P4-D's approved live work is finished and closed; what remains is the earlier-phase operational exits, the keystone D11 materialization, the blocked Stage B/C prerequisites, small offline leftovers, and open owner decisions. P4-E stays gated on parity evidence plus a separate bounded approval (no parity evidence exists and none is currently being produced).

## Fresh-state verification (read before touching anything)

- Recorded code state: `18ea375` (`Report sanitized partial metadata when the Stage A smoke stops early`) — the last CODE commit. Commits after it (`a47593d`, `de274e2`, and this refresh) are documentation-only: confirm with `git diff 18ea375..HEAD --name-only` listing nothing outside `docs/` — and `git status -uall --porcelain` must be clean apart from ignored files.
- If a later session finds uncommitted work instead, verify the tree against the delivered slice inventories (Stage A harness, live runner, partial-metadata repair) before any change; do not reset/stash/clean/checkout or mix in unrelated work.
- Latest verified gates (this session, before the run-record commits): isolated offline gate **1,963 passed / five warnings ×2** in fresh bwrap processes; Ruff check + format 346 files, MyPy `src` 164 files, docs consistency — all passing.
- Dependencies are unchanged from the owner-approved P4-B pin: `pydantic-ai-slim[openai,evals]==2.31.0`, lock SHA-256 `7d63f1ce0a02249c2efe7c2ef3de1c37c3eb1d770d278a7ad5845865eb8d6499`.
- One live smoke ran under the owner's Stage A permission (2026-10-23): 12 POSTs, ≈ $0.0155 of the $1 quota-value allocation, $0 cash. No further live work is approved; Stage B/C remain blocked (below).

## What is already done (do not redo)

- **P4-A/B/C**: capability spike; opt-in `pydantic-ai` adapter (default stays `qwen`; generation on that route fail-closed); Pydantic Evals task layer + offline `judge_provider: pydantic-ai` judge wiring (programmatic runner only, CLI unchanged).
- **P4-D Stage A**: offline harness + gated live-capable runner delivered and review-CLOSED; the live smoke RAN and was **accepted by the owner as incomplete**: text, streaming (TTFT 2.68 s baseline / 3.86 s adapter) and cancellation PASSED for BOTH implementations on the Go route; the baseline structured-output op failed validation and the adapter's structured modes were never reached. Structured output through the Go route is NOT established — recorded as a hard boundary, not a TODO. Cumulative spend ≈ $0.0155 quota-value reserved, $0 cash. No cutover inference; adapter stays opt-in.

## Next work — the leftover stages (each needs its own bounded approval; nothing runs before it)

Priority order below is dependency-driven, not mandatory sequencing; pick with the owner.

1. **D11 corpus/index materialization with provenance** — THE keystone. The D11 snapshot is honestly unverified/empty. Materializing the frozen index (existing corpus only; reindex/embedding changes are separately named variants) unblocks: Stage B (real-RAG smoke), the selectable `pydantic_evals` CLI `--harness` wiring, and phase-2 evaluation identity/replay. Needs: owner-approved bounded implementation slice + owner confirmation of which frozen corpus/snapshot identity to materialize. Context: [T5 D11 snapshot handoff](20261021-t5-d11-snapshot-handoff.md), D11 in [decisions](decisions.md).
2. **Review-authority exercise** — the fail-closed hash-attestation tool exists ([T6 handoff](20261021-t6-review-manifest-tool-handoff.md)); no manifest is verified yet, so reviewed/cohort/promotion eligibility stay false. Needs: owner names the authority and runs the attestation; small.
3. **D17 remainder: independent judge pinning** — the default `pydantic-ai` judge shares the MiMo family/route with the generator and CANNOT score a matched comparison. Needs an owner-pinned different-family judge (exact model ID, endpoint, credential source, prompts, temperature, token limits, prices) plus a frozen matched baseline configuration snapshot. Owner decision first; no availability is asserted.
4. **Hosted Logfire configuration + permissioned smoke** — destination/access/retention under D06/D15, owner-supplied hosted token; canaries before any content modes. Context: [logfire canaries handoff](20261021-logfire-canaries-handoff.md), [compatibility spike](20261016-logfire-compatibility-spike.md) (5.2.0 not cleared for lock adoption).
5. **Docker/container smoke** — small; owner-approved bounded slice; context: [T7 boundaries handoff](20261021-t7-boundaries-handoff.md).
6. **Reranker asset selection/download** — owner decision on asset, then a download-permission slice (downloads are gated).
7. **Live baselines** (phase 2) — needs approved credentials for live calibration; separate permission.
8. **Offline leftovers (small, worker-sized; pick or skip)**: P4-B settings-bound acceptance tests (temperature 0/2, timeout 600), stream usage totals on cancellation, repeated sync-call lifecycle coverage; P4-C upper-bound override coverage (`temperature=2.0`, `timeout_seconds=600`); decide whether `provider="pydantic-ai"` generation preflight/`effective_roles` is widened (currently fail-closed); record the intended `--harness` selector shape without wiring it before D11.
9. **Open owner decisions**: D12 (co-pilot scope), D13 (native history/structured answers — note Stage A's structured rejection is relevant input), D14 (deployment/auth), D15 (retention/access/deletion), D16 (live CI cadence — moot until live work resumes), D18 (operational-resilience variants).

**Stage B / Stage C status:** B blocked on D11 + explicit query-embedding permission. C blocked on judge pinning (3), review authority (2), frozen matched configuration, AND structured-output capability (Stage A boundary). The P4-D approvals pack's allocations remain proposal-only; any new live stage needs a fresh run-specific addendum.

## P4-E — bounded cutover (only after parity evidence + explicit approval)

Pydantic Evals main runner / Logfire primary experiment UI; versioned datasets/prompts/config; small local manifest/report/cost records; archive legacy results; retire redundant W&B/custom dashboard paths only in a separately approved bounded slice. **Current standing: no parity evidence exists or is being produced; P4-E is dormant by owner decision (Stage A accepted without follow-on).**

## Budget posture (unchanged)

USD 20/month incremental ceiling with simple tracking; existing Go subscription separate (≈ $0.0155 quota-value consumed of the $1 Stage A allocation; $0 cash). Chat serving stays ungated by design; no hard billing cap is claimed. Keep pay-as-you-go spillover/auto-top-up off.

## Workflow (restored standing pairing)

- **Roles for this next thread:** worker `glm-worker` = `zai/glm-5.3-flash`; reviewer `luna-reviewer` = `openai-codex/gpt-6-luna:xhigh`.
- Inspect before proposing; owner approves each bounded slice; minimal scope; no new abstractions.
- Snapshot before changes (tracked binary patch, NUL `status -uall`, lock digests, untracked hashes + copies of owned pre-existing untracked sources); preserve worker/review responses verbatim; allowed-set preservation on close.
- Parent owns integration/gates: `bash scripts/verify_phase123_offline.sh` twice in fresh processes, then statics (Ruff/format all files, MyPy `src`, import contracts, docs consistency). No bare pytest/application imports outside the approved isolation.
- Disjoint file ownership; workers run no tests/imports/network; parent manages repairs and closure.
- No secrets in tasks/outputs/artifacts; no `.env`/credential inspection (exception recorded 2026-10-23: owner instructed blind `.env` sourcing for the Stage A run; value never displayed or stored); no existing-data deletion/migration; no model/corpus downloads; no hosted export; no public exposure. Deny-live protection for both Pydantic AI and existing SDK paths. No serving-default flip.
