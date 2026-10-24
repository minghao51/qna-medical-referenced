# Remaining-work pickup brief — Phase 4 continuation and earlier-phase exits

*Updated 2026-10-21 after P4-C delivery. Supersedes the previous version of this brief in place; it remains documentation only and grants no new implementation, dependency, live-call, export, or default-switch permission by itself.*

## Start here in a new session

Read `AGENTS.md`, the relevant `.planning/codebase/` references, this brief, [decisions](decisions.md), [phases](phases.md) (Phase 4 sections and open exits), R05/R12/R13/R14 in the [implementation spec](implementation-spec.md), the [P4-A capability report](20261021-phase4a-capability-spike.md), the [P4-B adapter handoff](20261021-phase4b-adapter-handoff.md), and the [P4-C evaluation-tasks handoff](20261021-phase4c-evaluation-tasks-handoff.md) — the latest verified checkpoint.

**Purpose of this brief:** continue, in one fresh thread, all remaining authorized-but-unstarted work: prepare **P4-D** approvals and gated live validation, close the small offline leftovers, and address the still-open earlier-phase operational exits. P4-E stays gated on P4-D parity evidence plus a separate bounded approval.

## Fresh-state verification (read before touching anything)

- Recorded code state: `44b1e6b` (`Deliver gated Stage A live-capable runner behind owner-confirmation and env-credential gates`), on top of `76fbfc1` (offline Stage A harness), `3d18434` (P4-C), `26f511b` (P4-B) and `2e01e6b` (Phase 4 pickup docs). The gated live-capable runner slice is delivered and review-CLOSED (see the [live-runner handoff](20261021-phase4d-stage-a-live-runner-handoff.md)); NO live call has been made. Commits after `44b1e6b` must be documentation-only — confirm with `git diff 44b1e6b..HEAD --name-only` listing nothing outside `docs/` — and `git status -uall --porcelain` must be clean apart from ignored files.
- If a later session finds uncommitted work instead, verify the tree against the Stage A offline handoff delivery inventory before any change; do not reset/stash/clean/checkout or mix in unrelated work.
- Integration gates re-run in this session before the commit: isolated offline gate **1,961 passed / five warnings ×2** in fresh bwrap processes; Ruff check + format 346 files, MyPy `src` 164 files, docs consistency — all passing.
- Dependencies are unchanged from the owner-approved P4-B pin: `pydantic-ai-slim[openai,evals]==2.31.0`, lock SHA-256 `7d63f1ce0a02249c2efe7c2ef3de1c37c3eb1d770d278a7ad5845865eb8d6499`. P4-C added **no** dependency; `pydantic-evals` 2.31.0 was already in the lock.
- Latest verified gates (P4-C session): isolated offline gate **1,903 passed / five warnings ×2** in fresh bwrap processes; Ruff check+format 339 files, MyPy `src` 164 files, docs consistency — all passing. Scratch evidence under `/tmp/qna-p4c-1792678346/` is ephemeral; the P4-C handoff records the numbers and findings.

## What is already done (do not redo)

- **P4-A** capability spike complete and owner-reviewed: latest Pydantic AI blocked by `openai>=3` (litellm/langchain-openai caps); Go route documented (`mimo-v2.6-flash`, `https://opencode.ai/inference/go/openai/v1`, honest `User-Agent` + stable `x-opencode-session`, limits $60/mo Go; streaming/JSON-schema support undocumented offline).
- **P4-B** opt-in adapter delivered and closed (GLM → Luna **CLOSED**): provider literal `pydantic-ai`, default remains `qwen`; Qwen-mirrored retry/no-partial-retry semantics; request-scoped identity headers; explicit fail-closed structured modes (`tool` | `native-json-schema`); usage accounting; conversation-context scoping per token pull.
- **P4-C** delivered and closed (DeepSeek Flash → GLM-5.3 Flash **CLOSED**, plus three post-closure repairs): `src/evals/pydantic_tasks.py` task layer for both implementations (frozen inputs, twin tasks, normalized outcomes/usage/timings, per-case DeepEval metric bridge with owned-model cleanup, R07 completeness, content-gated report projection, bounded runner, isolated multi-turn replay) and `src/evals/pydantic_ai_judge.py` with full offline `judge_provider: pydantic-ai` wiring (credential, judge model names, endpoint validation, honest attempt accounting, `max_completion_tokens` mapping). The runner is **programmatic only**; the eval CLI is unchanged; **generation** on that route remains fail-closed.

## Next primary work: P4-D approvals, then a gated tiny smoke (nothing may run before explicit approval)

A documentation-only [P4-D approvals pack](20261021-phase4d-approvals-pack.md) now proposes separate stage allocations and lists the still-required execution addendum; it grants no live permission. The subsequently approved [Stage A offline harness](20261021-phase4d-stage-a-offline-handoff.md) and the [gated live-capable runner](20261021-phase4d-stage-a-live-runner-handoff.md) are delivered and review-CLOSED (1,961 tests ×2): the live path enforces owner-confirmation + environment-credential gates, admission-before-delegation, and digest-only sanitized metadata. The owner selected Stage A only: $1 included Go quota value / $0 incremental cash; the owner's account confirmations (addendum items 1-3) were recorded 2026-10-23; the ONLY remaining live blocker is the owner's final stage-specific run confirmation after reviewing the frozen hashes, effective settings and numeric reservations in the live-runner handoff. B and C remain unapproved and blocked.

Before any live call, obtain the pack's run-specific execution addendum with exact wire/token caps, quota/cash allocations, input/case counts, safe route wiring and route confirmation. Obtain separate explicit run permission for each unblocked stage:

1. A: protocol-only same-model/same-route smoke for both implementations (text, stream, structured output, cancellation); no retrieval or embeddings.
2. B: one real-RAG smoke case, blocked on D11 materialization and explicit query-embedding permission.
3. C: bounded matched pilot, additionally blocked on independent judge pinning, review-authority exercise and frozen matched configuration.

Record confounds honestly, including the adapter's `max_completion_tokens` wire mapping, tool vs native-json-schema request shapes, and judge/generator family overlap. Compare quality, completion, TTFT, total latency, token/cost estimates and maintenance trade-offs. Keep pay-as-you-go spillover/auto-top-up off (D18/budget posture). Honest `User-Agent` and `x-opencode-session` only; stop on route rejection with no substitution. Offline CI gates stay first; paid/manual/scheduled live CI remains a separate D16 decision.

**P4-C's judge wiring does not satisfy D17.** The default `pydantic-ai` judge shares the OpenCode Go route and model family with the generator, so a matched run cannot claim independent-judge scoring. Pin an independent judge (different family) before stage C or any quality comparison; without that pin C stays blocked. Same-family scoring is not an approved substitute.

## Prerequisites that still block a real scored comparison (do not pretend readiness)

- **Corpus/index materialization with provenance** — the D11 snapshot is honestly unverified/empty. This blocks an actual scored P4-C run and blocks wiring a selectable `pydantic_evals` CLI harness; reindex/embedding changes are separately named variants.
- **Named review-authority exercise** through the fail-closed hash-attestation mechanism — no manifest is verified yet; reviewed/cohort/promotion eligibility stay false.
- **D17 remainder** — independent judge pinning plus a matched baseline configuration snapshot (exact judge ID/prompts/temperature/token limits).
- **Hosted Logfire configuration + permissioned smoke** (destination/access/retention under D06/D15; content modes only after canaries), **Docker/container smoke**, **reranker asset selection/download**, **live baselines**.
- **Budget limitation disclosure** — chat serving stays ungated by design; no hard billing cap is claimed.

## Optional offline leftovers (small, worker-sized; pick or skip)

- P4-B: exact settings-bound acceptance tests (temperature 0/2, timeout 600), stream usage totals on cancellation, repeated sync-call lifecycle coverage.
- P4-C: upper-bound override acceptance coverage (`temperature=2.0`, `timeout_seconds=600`); decide whether `provider="pydantic-ai"` **generation** preflight/`effective_roles` is widened for P4-D (currently fail-closed and unguarded beyond the new preflight test); record the intended `--harness` selector shape without wiring it before D11.
- `max_completion_tokens` mapping and Go-route schema/stream acceptance are **live-only** questions (P4-D).

## P4-E — bounded cutover (only after P4-D parity evidence + explicit approval)

Pydantic Evals main runner / Logfire primary experiment UI; versioned datasets/prompts/config; small local manifest/report/cost records; archive legacy results; retire redundant W&B/custom dashboard paths only in a separately approved bounded slice.

## Open decisions

D12 (co-pilot scope deferral), D13 (native history/structured answers), D14 (deployment/auth), D15 (retention/access/deletion), D16 (live CI cadence), D17 remainder (judge pinning + matched snapshot), D18 (operational-resilience variants; no-fallback accepted for Phase 4 comparison work only). D11 is accepted as recorded; P4-C session decisions are recorded in the register.

## Workflow (restored standing pairing)

- **Roles for this next thread:** worker `glm-worker` = `zai/glm-5.3-flash`; reviewer `luna-reviewer` = `openai-codex/gpt-6-luna:xhigh`. The P4-C thread's temporary pairing (DeepSeek Flash worker → GLM-5.3 Flash reviewer) applied to that run only and is not the standard workflow; that temporary reviewer was also a weaker model, so P4-C got one review round plus a closure round rather than Luna's deeper pass.
- Inspect before proposing; owner approves each bounded slice; minimal scope; no new abstractions.
- Snapshot before changes (tracked binary patch, NUL `status -uall`, lock digests, untracked hashes + copies of owned pre-existing untracked sources); preserve worker/review responses verbatim; allowed-set preservation on close.
- Parent owns integration/gates: `bash scripts/verify_phase123_offline.sh` twice in fresh processes, then statics (Ruff/format all files, MyPy `src`, import contracts, docs consistency). No bare pytest/application imports outside the approved isolation.
- Disjoint file ownership; workers run no tests/imports/network; parent manages repairs and closure.
- No secrets in tasks/outputs/artifacts; no `.env`/credential inspection; no existing-data deletion/migration; no model/corpus downloads; no hosted export; no public exposure. Deny-live protection for both Pydantic AI and existing SDK paths. No serving-default flip.
- Budget posture: USD 20/month incremental ceiling with simple tracking; existing Go subscription separate; no live spend authorized by any record in this tree.
