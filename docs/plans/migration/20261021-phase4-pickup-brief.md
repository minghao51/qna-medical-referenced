# Phase 4 pickup brief — Pydantic AI / OpenCode Go

## Start here in a new session

Read `AGENTS.md`, the relevant `.planning/codebase/` references, this brief, [decisions](decisions.md), [Phase 4 tasks](phases.md#phase-4--pydantic-ai-adapter-plus-shared-evaluations), and R05/R12/R13 in the [implementation spec](implementation-spec.md). Latest verified implementation checkpoint: [auth-preflight parity closure](20261021-auth-preflight-parity-handoff.md).

**Primary objective:** get OpenCode Go-powered chat working through an opt-in Pydantic AI adapter. Shared evaluations and later consolidation support that goal; this is not an agentic rewrite or default switch.

**Status:** planning/handoff only. No Pydantic AI compatibility installation, provider capability test, adapter implementation, or live call has started in this continuation. The app currently selects existing Qwen/OpenAI-SDK, Gemini, or LiteLLM clients; Pydantic AI is not wired into generation. Earlier proposed `LITELLM_API_BASE`/`LITELLM_API_KEY` settings are not implemented and are not the selected Phase 4 design.

## Owner answers and authorization

Owner answered the Phase 4 interview and accepted the staged plan, then requested a fresh-session handoff:

1. Priority **A: working Go-powered chat through Pydantic AI**, rather than comparison as the primary outcome.
2. Scope **C: broader staged Phase 4 plan with explicit stop points**. Start with P4-A; return with concrete findings before P4-B changes. This is not unconditional approval of all later phases or cutover.
3. Dependency investigation allowed: registry access and isolated compatibility installs. Report exact proposed project-lock changes before applying them; stop on unrelated major upgrades.
4. Selected generator **MiMo V2.6 Flash via OpenCode Go**, replacing the earlier DeepSeek choice for the upcoming Phase 4 route/matched comparison. Exact model ID, API path, current availability and capabilities must be verified; do not guess, substitute another model, or rewrite historical snapshots.
5. **No live calls now.** Testing against live services is deferred to the end and needs an explicit quota/spend/input approval. No provider-key inspection or requests merely because credentials may exist.
6. Schema-validated structured output required for **both internal tasks and user-facing generation**. This does not itself authorize a chat UI/protocol redesign. If route support is insufficient, stop and present options; no silent downgrade to unvalidated text.
7. Recommend an independent judge after capability findings; different model family from the generator. Exact judge ID, route, settings and budget must be pinned before the pilot.
8. Confirmed: local telemetry initially; no hosted uploads, automatic provider/model fallback, real patient data, serving-default flip or legacy-path removal.
9. Acceptance priorities: streaming/cancellation/history/citation/completeness correctness; comparable quality; explicit latency/usage trade-offs; maintenance burden. No numeric promotion threshold or automatic adoption decision inferred.

Existing USD 20/month incremental project-spend posture remains; Go subscription cost/quota is separate. No current live-spend authorization follows from this planning record. Owner previously reported workload eligibility; actual current account/route acceptance remains unverified. Use honest client identification, never coding-agent impersonation or fabricated tool traffic.

## Stages and stop points

### P4-A — dependency/provider capability spike (next authorized work)

- Inspect current protocol, factories, settings, lifecycle/retry/usage/telemetry contracts and existing tests before proposing the concrete bounded work.
- Resolve minimal Pydantic AI slim/provider and Pydantic Evals compatibility against Python 3.12/current dependency family in isolation; record exact versions. Avoid speculative SDKs or unrelated upgrades.
- Verify official current Go route/model documentation and pinned APIs; distinguish documented claims, offline transport proof and untested account access.
- Fake-transport checks for sync/async generation, stream deltas, structured schemas, cancellation, ownership/closure, usage and content controls. Test honest `User-Agent` and opaque stable per-conversation `x-opencode-session`; isolate case/variant/judge sessions without shared-state mutation.
- Include deny-live protection. No automatic Logfire/Evals body/report export; retain owned manual telemetry controls.
- Produce capability matrix, exact dependency diff proposal, risks and concrete adapter/configuration plan.

**Stop:** owner reviews capability/dependency findings before project dependency changes and P4-B implementation. Unsupported schema support, unrelated major upgrades, unclear endpoint eligibility or required protocol changes must be surfaced, not hidden.

### P4-B — opt-in working chat

Implement the existing sync/async/text-stream/structured interface via Pydantic AI. Separate implementation selection from provider/model and future agentic harness. Preserve prompts/history/context semantics, citations, SSE, resource lifecycle and partial-output retry restrictions. Keep existing clients selectable with no new token requirement. Keep DashScope embedding role/configuration independent of Go generation; no reindex or embedding switch.

Offline model/transport contract tests, deny-live guard, diagnostics/cache actual-model identity and configuration guide required. Return for concrete slice approval after P4-A, not blanket code permission from this brief.

**Stop:** review + offline gates; runnable opt-in configuration, no default flip and no live smoke yet.

### P4-C — shared evaluation machinery

Run baseline and adapter on matched frozen cases/index/settings using Pydantic Evals, existing repaired retrieval metrics and existing DeepEval definitions during calibration. Preserve artifact readers/normalized outcomes, required-evaluator completeness, usage/timings and isolated multi-turn sessions. Test report-level content/export controls, not just spans.

**Stop:** offline machinery ready, with missing corpus/index/review prerequisites explicitly blocked rather than invented.

### P4-D — separately permissioned live validation

Return for exact quota/cash budget, input/case count, judge and route approval. Tiny text/stream/structured/cancellation/RAG smoke followed by a bounded matched pilot when prerequisites exist. Record effective prompts/settings, confounds, quality/completion/TTFT/latency/usage and maintenance trade-offs. Offline CI first; paid/manual/scheduled live CI permissions remain separate (D16).

**Stop:** compare evidence; adapter remains opt-in. No promotion without D08 decision.

### P4-E — separate bounded cutover

Only after parity evidence and explicit approval: Pydantic Evals main runner / Logfire primary UI, preserving local provenance/history and rollback. Retiring W&B/custom evaluation paths or hosted setup is not authorized by P4-A or provision of a key.

## Fresh-state verification and workflow

- **Owner-approved checkpoint:** runtime/config/tests committed as `9802e5d` (Phase 1–3 runtime, evaluation, telemetry and regression fixes), followed by the documentation/Phase 4 handoff commit containing this brief. Start from that documentation commit; verify `git log -2` and clean `git status`. Earlier `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a` dirty-tree references in historical handoffs describe the pre-checkpoint state. Do not reset/stash/clean/checkout or commit unrelated new work. Ignored local credentials/data/dependencies remain untouched and are not part of these commits.
- Latest checkpoint gate: **1,814 passed / five warnings ×2**, `/tmp/qna-checkpoint-verify-7gRcqi/gate.log` and `gate-repeat.log`. Statics: Ruff/format 337 files, MyPy `src` 160 files, four import contracts, docs consistency; frontend `npm run check` and `npm run build` passed with existing warnings recorded in the logs. Pending-file audit found no matches in a limited credential-pattern scan (not a comprehensive secret certification), no binary files and no non-example environment files. No ignored files were staged. These are prior evidence, not new-session verification.
- Use `bash scripts/verify_phase123_offline.sh`; no bare pytest/application imports outside the approved isolation. Parent owns integration/gates twice in fresh processes and explicit test inventory `scripts/verify_phase123_offline.py`.
- Continue GLM implementation (`glm-worker`) → Luna read-only review (`luna-reviewer`), disjoint file ownership and parent-managed repair/closure. Workers do not run tests/imports/network unless a concrete new permission changes that boundary; parent owns permissioned compatibility/network work.
- New snapshot before changes: tracked binary patch, NUL status `-uall`, lock digests, untracked hashes **and copies of owned pre-existing untracked source files** (prior hash-only baseline limited exact review). Preserve complete task/review responses verbatim and perform allowed-set preservation.
- No secrets in tasks, outputs or artifacts. No `.env`/credential inspection, existing-data deletion/migration, model/corpus downloads, public exposure, or hosted export. Eligibility guards remain false; no hard billing cap or medical/identity-authentication claims.

## Dependencies still open, not waived

Earlier-phase operational exits are still open. Offline P4-A work may proceed without pretending integrated-comparison readiness: corpus/index materialization with provenance (current D11 corpus/index snapshot honestly unverified/empty), actual named review-authority exercise, independent judge pinning, budget limitations/chat ungated, hosted setup/smoke, Docker smoke, reranker assets and live baselines. Integrated/live comparisons must explicitly account for these prerequisites.

Approved T1–T7 and subsequent HyDE-log/auth-preflight fixes are complete. Review-context revalidation deliberately retained; API-key `SecretStr` migration optional and not bundled. No new runtime fixes are inferred from this handoff.
