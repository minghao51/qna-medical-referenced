# Multi-harness migration plan

**Fresh-session entry (2026-10-21, latest, refreshed after P4-C):** [Remaining-work pickup brief](20261021-remaining-work-pickup-brief.md) — prepare the P4-D approvals pack and gated tiny smoke, then the bounded pilot; D11 corpus/index materialization and D17 judge pinning still block a real scored comparison. Standing roles restored for the next thread: GLM 5.3 Flash worker → GPT-6 Luna `xhigh` reviewer. **Latest delivered checkpoint:** [P4-C evaluation-tasks handoff](20261021-phase4c-evaluation-tasks-handoff.md) (gate 1,903 ×2; DeepSeek Flash implementation → GLM-5.3 Flash review → closure CLOSED plus three post-closure repairs) — Pydantic Evals task layer for both implementations, report-level content gate, and offline `judge_provider: pydantic-ai` wiring; programmatic runner only, no CLI selector flip, no live calls. Prior checkpoints: [P4-B adapter handoff](20261021-phase4b-adapter-handoff.md) (gate 1,846 ×2, Luna CLOSED), [P4-A capability report](20261021-phase4a-capability-spike.md).

**Prior fresh-session entry (2026-10-21):** [Phase 4 pickup brief](20261021-phase4-pickup-brief.md) — staged Pydantic AI / Go MiMo chat plan; start with isolated P4-A capability work, no live calls. Latest pre-Phase-4 checkpoint: [auth-preflight parity closure](20261021-auth-preflight-parity-handoff.md), gate 1,814 ×2. T1–T7 and approved fix follow-ups are complete; older status paragraphs below are historical and do not supersede this entry or the latest decision record.

**P4-A spike delivered (2026-10-21):** [Pydantic AI / Pydantic Evals / OpenCode Go capability report](20261021-phase4a-capability-spike.md) — isolated resolution plus a network-denied fake-transport probe (14/14 ×2). Latest Pydantic AI (2.59.0) requires `openai>=3.26.0` and is blocked by litellm/langchain-openai; compatible candidates `2.31.0` (recommended; `openai`→2.54.0) and `1.66.0` (zero `openai` change) are fully resolved with exact diffs. Go route documented (`mimo-v2.6-flash` listed; honest `User-Agent` + `x-opencode-session` required; schema/stream support undocumented pending the gated live smoke).

**P4-C evaluation tasks delivered (2026-10-21):** [evaluation-tasks handoff](20261021-phase4c-evaluation-tasks-handoff.md) — `src/evals/pydantic_tasks.py` (frozen-input datasets, twin baseline/adapter tasks, per-case DeepEval metric bridge with owned-model cleanup, R07 completeness, content-gated report projection, bounded runner, isolated multi-turn replay) and `src/evals/pydantic_ai_judge.py` (judge wrapper on the adapter, raw prompt, judge settings, usage attribution). Judge wiring (`judge_provider: pydantic-ai`) is complete offline and remains opt-in; generation on that route stays fail-closed; the eval CLI is unchanged because a selectable harness needs D11 corpus/index materialization. Gate **1,903 passed ×2**, statics and docs consistency clean.

**P4-B adapter delivered (2026-10-21):** [adapter handoff](20261021-phase4b-adapter-handoff.md) — owner approved candidate B; dependency applied byte-identical to the reviewed resolution; opt-in `pydantic-ai` provider implements the existing generation protocol with Qwen-mirrored retry/no-partial-retry semantics, honest identity headers (opaque per-conversation `x-opencode-session`, request-scoped), explicit fail-closed structured-output modes, and usage accounting. GLM implementation → Luna review → parent repairs (incl. a gate-caught transient-classification defect and the conversation-context leak fix) → Luna closure **CLOSED**; isolated gate **1,846 passed ×2**; statics clean. No default flip, no live calls; P4-C/P4-D/P4-E remain separately gated.

**Status:** Owner answers D01–D10 recorded on 2026-10-15; follow-up selects Go, settles incremental budget scope, and approves Logfire consolidation/public-synthetic case export. Remaining technical checks are in the decision register. P1-A1–P1-A4 and the bounded P1-B/P1-C1/P1-C2/P1-C3a generation-adapter slices are approved and verified; Phase 1 remains in progress. Handoffs: [async readiness](20261015-p1-a1-handoff.md), [initialization/concurrency](20261015-p1-a2-handoff.md), [off-loop retrieval/native-async HyDE](20261015-p1-a3-handoff.md), [synthetic HTTP/SSE lifespan and cleanup](20261015-p1-a4-handoff.md), [effective profiles and ingestion flags](20261015-p1-b-handoff.md), [stream retries/ownership and failed-generation history](20261015-p1-c1-handoff.md), [same-session admission and atomic turn commits](20261016-p1-c2-handoff.md) (verified 2026-10-16).
**Offline follow-through:** Owner approved Phase 2/3 implementation; the first bounded role/completeness and existing-export foundation is recorded in the [P2/P3 handoff](20261016-p2-p3-foundation-handoff.md). Neither phase is complete; Phase 1 and integrated comparison gates remain open. The approved [P2-B1 continuation](20261016-p2-b1-handoff.md) adds fresh attempts, bounded source provenance and atomic artifacts; actual semantic/index identity and supported replay remain unverified.
**Latest SDK fix (2026-10-17):** The owner approved and the [Gemini HTTPX follow-up](20261017-gemini-httpx-fix-handoff.md) resolves C3a's generation-adapter transport finding using the actual application constructor and owned lifecycle. Expanded isolated gate: **1,319 passed, 6 optional DeepEval skips**; 37 constructor/lifecycle cases passed 10/10 fresh processes, static checks pass and scoped Luna re-review found no actionable issues. No SDK upgrade/provider/model/profile switch. The [prior C3a handoff](20261017-p1-c3a-handoff.md) preserves the original 1,282-case gate and native-default diagnostic; direct judge SDK paths, physical per-stream release, broader workers, browser provisioning and Phases 1–3 remain open.
**Resumed bounded batch:** Following the historical documentation-only pause, the owner resumed execution. Dedicated session signing/provider/worker guards and history/API/UI non-comparability repairs are implemented; the original guard gate was **856 passed, 6 optional DeepEval skips**. Its two Luna review findings are repaired in the owner-approved [follow-up](20261017-review-repair-handoff.md): **889 passed, 6 optional DeepEval skips**, passing static/frontend type/build checks and no actionable Luna re-review findings. Browser execution remains blocked; no new packages were provisioned. The [isolated Logfire spike](20261016-logfire-compatibility-spike.md) is complete as research; candidate 5.2.0 moves OTel/protobuf and is not cleared for application tracing/lock adoption. Start with the [latest transport-fix handoff](20261017-gemini-httpx-fix-handoff.md), [prior reader/UI repair](20261017-review-repair-handoff.md) and [guard-batch context](20261016-guard-batch-handoff.md), [historical resume scope](20261016-phases-1-3-resume-handoff.md) and [decision register](decisions.md). D17 selects corrected **`baseline`** for comparison, not a serving-default switch. All phase/live/export/model-asset/broad-upgrade gates remain.
**Baseline inspected:** `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`.
**Direction requested:** Repair the baseline, make evaluation trustworthy, add privacy-safe observability, introduce Pydantic AI/Pydantic Evals alongside the baseline, then explore an agentic harness.

**Next slice prepared (2026-10-20):** See the [next-slice brief](20261021-next-slice-brief.md) for the owner-approved Logfire/OTel adoption + P3-C offline canaries, the owner-requested expansion tasks (review-polish, D11 frozen-identity snapshot, attested-manifest authoring helper, boundary docs), and the owner-directed orchestration change (GLM 5.3 Flash workers, GPT-6 Luna `xhigh` reviewer). Decisions of 2026-10-20 are in the [decision register](decisions.md).

**Current continuation (2026-10-20, second slice):** See the [admission/manifest/spans handoff](20261020-admission-manifest-spans-handoff.md) for independent embedding spans, stream retry transition telemetry, generalized budget admission, hash-verified review-manifest attestations (content consistency only), isolated verification and scoped review. Whole phases, identity-authenticated review authority, full budget admission and hosted/live/container exits remain open.

**Previous continuation (2026-10-20):** See the [evaluation-tracing handoff](20261020-evaluation-tracing-handoff.md) for opt-in local run/case-correlated stage/attempt traces, supported-launcher log repairs, isolated verification and scoped review. Whole phases, authenticated review authority, full budget admission and hosted/live/container exits remain open.

**Previous integration checkpoint (2026-10-19):** The consolidated remaining Phases 1–3 plan and narrow dependency/browser provisioning are approved. See the [integration handoff](20261019-phases-1-3-integration-handoff.md) for current code, isolated gates, exact dependency changes, review repairs, and open exits. Earlier no-install/browser-blocked statements below describe their historical slices. **Whole phases remain incomplete; no live/model/corpus/export/default-switch/Phase 4 permission is inferred.**

## Read in this order

1. [Decision register](decisions.md) — questions, recommendations, and approval boundaries.
2. [Implementation specification](implementation-spec.md) — requirements, contracts, compatibility, and acceptance criteria.
3. [Phased implementation plan](phases.md) — executable work packages, dependencies, verification, and rollback.
4. [Environment and credentials](environment-and-credentials.md) — what is needed now versus before live calls.

The phase plan references requirement IDs in the specification and decision IDs in the register. The register is the single source of truth for owner decisions; recommendations elsewhere are not approvals.

## Scope and guardrails

- Keep FastAPI, SvelteKit, SSE, Hamilton ingestion, Chroma, and source metadata. Approved consolidation: Pydantic Evals runner + Logfire primary experiment UI, retaining small local/versioned reproducibility records rather than a second dashboard stack. Implement through bounded, parity-checked slices (D10).
- Keep the current deterministic RAG implementation as a comparison control.
- Async-first server orchestration, with thin sync CLI wrappers. Offload existing synchronous work rather than relabeling it async or maintaining duplicate implementations.
- Reuse the existing `LLMClient` protocol, use-case boundary, configuration models, and composition roots. Do not build a plugin platform or universal orchestration layer.
- Separate generation implementation, model/provider selection, embedding identity, judge selection, and telemetry.
- Preserve historical results, but label them as legacy rather than silently comparing changed metric definitions.
- Private research lab; public/synthetic data only; reference-heavy engineering evaluation, no clinical-suitability claims.
- Monthly budget: USD 20 across incremental generation/judge/embedding/enrichment/metered-telemetry charges; existing Go subscription separate. Simple run/month summaries, no billing platform or mandatory per-run dollar cap. Exact Go account/quota billing is not yet programmatically verified.
- OpenCode Go with DeepSeek V4.1 Flash or MiMo V2.6 Flash is selected; owner reports checking eligibility. Verify honest `User-Agent`, stable per-conversation `x-opencode-session`, account/model access, and usage capabilities before a live smoke.
- Public/synthetic case inputs/outputs may be exported to the chosen Logfire project after local policy tests and destination setup; metadata-only/offline modes remain. No secrets or real patient data.
- No arbitrary paid runs, immediate uploads, destructive reindexing, production deployment, or default harness switch is authorized by these planning choices.

## Phase map

| Phase | Outcome | Credentials | State |
|---|---|---|---|
| 0 | Resolve the decisions needed for the next implementation slice | None | P1-A1–P1-A4/P1-B/P1-C1/P1-C2 approved; later decisions remain phase-specific |
| 1 | Working baseline and effective configuration | None for offline implementation/tests | In progress: async retrieval/lifespan and effective-profile/ingestion fixes and bounded stream/no-partial-history fixes verified; same-session rejection/atomic commits verified; dedicated signing/provider/single-worker guards verified; remaining P1-C SDK/worker-cleanup, retry-policy, setup/preflight/container and baseline-capture gates pending |
| 2 | Versioned, reproducible, fail-closed evaluations + simple monthly usage/cost accounting | None for deterministic tests; approved credentials for live calibration | Bounded offline foundations: role/measurement/winner checks and fresh-attempt/source/atomic-artifact safety; history comparisons suppressed with nullable diagnostics; full identity, metrics, isolation, reviewed pilot and accounting remain open |
| 3 | Privacy-safe tracing across the baseline | No hosted token for local verification; token for approved hosted export | Existing W&B/confidence hardening and isolated Logfire compatibility research delivered; dependency approval, application tracing/policy/canaries/lifecycle and hosted verification remain open |
| 4 | Pydantic generation adapter and cross-implementation Pydantic Evals tasks | None for mocked tests; approved provider keys for live parity | Not started |
| 5 | Optional tool-driven harness and evidence-based default decision | Approved providers, budgets, and reviewed cases | Not started; separately gated |

The phase ordering is deliberate. The owner-approved offline Phase 2/3 foundations do not waive Phase 1 exit or subsequent integration gates. A framework migration must not hide baseline defects or change the benchmark halfway through a comparison. Deployment work within Phases 1/3 can be prepared independently, but no public rollout is implied.

## Review evidence and limits

The preceding repository review used three GPT-6 Luna `xhigh` scouts and parent verification. Filtered offline runs reported:

- Unit tests: 508 passed, 8 skipped, 22 deselected.
- Integration tests: 92 passed, 3 skipped, 53 deselected.
- Live/network/DeepEval tests were excluded. These results do not prove the server's real async chat path works.

The review reproduced the async initializer failure, profile retrieval settings not taking effect, partial-stream replay, incomplete model cache identity, missing-metric threshold bypass, and a null checksum for a Chroma directory. This is historical investigation evidence, not a substitute for regression tests on an implementation branch.

No Pydantic AI, Pydantic Evals, or Logfire integration was implemented or live-tested during the review. Dependency versions and exact supported APIs must be resolved and locked during implementation.

## Relationship to existing plans

- [Structural refactor roadmap](../20260910-structural-refactor-roadmap.md): retain its completed boundaries, import-linter contracts, and monkeypatch-safe composition conventions. Its deferred configuration defect is addressed here.
- [Medical co-pilot design](../20260416-medical-copilot-design.md): historical approved product direction includes vision, differential generation, and other tools. This migration does not implement or revoke those approvals. Scope conflict/deferral requires an explicit decision under D12.
- [Exploration design](../20260416-phase1-exploration-design.md): retain the experiment-oriented approach; old metric targets cannot be carried forward uncalibrated after scoring changes.

## Definition of done for this planning package

- [x] Record implementation requirements and phased delivery gates.
- [x] Identify user decisions, credentials, and spend/export boundaries.
- [x] Record the owner's first-round D01–D10 answers, including partial/tentative decisions.
- [x] Propagate accepted choices, Go owner confirmation/header requirements, incremental-budget/tracking limits, and approved consolidation/content boundaries into this package.
- [x] Approve and verify bounded offline slices P1-A1–P1-A4, P1-B, P1-C1, and P1-C2, retaining individual evidence and limits.
- [ ] Resolve remaining live-run/export/cutover conditions as needed.
- [ ] Implement and verify each slice, updating code and operational docs together.

Updating this package is not authorization to execute all phases. Each implementation slice must follow `AGENTS.md`: analyze first, present its bounded change plan, obtain approval, and keep scope minimal.
