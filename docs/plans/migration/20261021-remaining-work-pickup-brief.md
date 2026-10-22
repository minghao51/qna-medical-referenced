# Remaining-work pickup brief — Phase 4 continuation and earlier-phase exits

## Start here in a new session

Read `AGENTS.md`, the relevant `.planning/codebase/` references, this brief, [decisions](decisions.md), [phases](phases.md) (Phase 4 sections and open exits), R05/R12/R13/R14 in the [implementation spec](implementation-spec.md), the [P4-A capability report](20261021-phase4a-capability-spike.md), and the [P4-B adapter handoff](20261021-phase4b-adapter-handoff.md) — the latest verified checkpoint.

**Purpose of this brief:** continue, in one fresh thread, all remaining authorized-but-unstarted work: propose and (after owner approval) implement **P4-C**, prepare **P4-D** approvals, and address the still-open earlier-phase operational exits listed below. This brief is documentation only; it grants no new implementation, dependency, live-call, export, or default-switch permission by itself.

## Fresh-state verification (read before touching anything)

- Recorded history: `2e01e6b` (Phase 4 pickup docs) is the last commit. **All P4-A/P4-B delivery from 2026-10-21 is uncommitted on top of it.** Before starting the new thread, the owner should commit it (suggested message: `Apply approved Pydantic AI dependency and deliver opt-in P4-B adapter`). The new session then verifies `git log -1` contains that commit and `git status -uall` is clean apart from ignored files.
- If the work is still uncommitted when the new session starts, verify the tree against the P4-B handoff's file inventory instead (13 modified + 5 new paths listed there) before any change; do not reset/stash/clean/checkout or mix in unrelated work.
- Expected committed content: `pyproject.toml` + `uv.lock` (`pydantic-ai-slim[openai,evals]==2.31.0`; lock SHA-256 `7d63f1ce0a02249c2efe7c2ef3de1c37c3eb1d770d278a7ad5845865eb8d6499`), adapter/wiring/settings/usage/factory/answer-eval-map changes, the three new test homes, the extended gate inventory, and the four Phase 4 docs (P4-A report, P4-B handoff, updated `phases.md`/`README.md`).
- Latest verified gates (prior evidence, from the P4-B session): isolated offline gate **1,846 passed / five warnings ×2** in fresh bwrap processes; Ruff check+format 340 files, MyPy `src` 162 files, four import contracts, docs consistency — all passing. Scratch evidence paths under `/tmp/qna-p4a-*` and `/tmp/qna-p4b-*` are ephemeral; the handoff documents record their digests. Local `.venv` was re-synced with `uv sync --all-groups`; runtime artifacts are unaffected.

## What is already done (do not redo)

- **P4-A** capability spike complete and owner-reviewed: latest Pydantic AI blocked by `openai>=3` (litellm/langchain-openai caps); Go route documented (`mimo-v2.6-flash`, `https://opencode.ai/inference/go/openai/v1`, honest `User-Agent` + stable `x-opencode-session`, limits $60/mo Go; streaming/JSON-schema support undocumented offline).
- **P4-B** opt-in adapter delivered and closed (GLM → Luna review → parent repairs → Luna **CLOSED**): provider literal `pydantic-ai`, default remains `qwen`; Qwen-mirrored retry/no-partial-retry semantics; request-scoped identity headers; explicit fail-closed structured modes (`tool` | `native-json-schema`); usage accounting; conversation-context scoping per token pull. Confounds and limitations are recorded in the adapter docstring and both reports.

## P4-C — shared evaluation machinery (next primary work; concrete plan required first)

Per the staged plan, **inspect first, then present a bounded P4-C plan for owner approval before implementation** (same pattern as P4-A → P4-B). Expected shape from R13/phases:

- Wrap the plain-Python baseline tasks and the Pydantic AI adapter tasks in Pydantic Evals (`pydantic-evals` 2.31.0 already in the lock) on identical frozen inputs with normalized result fields; ordinary task API only — the baseline must not require Pydantic AI to be evaluated.
- Preserve ingestion checks, repaired retrieval metrics, DeepEval evaluator definitions during calibration (no duplicate rubrics), required-evaluator completeness (R07), usage/timings capture, isolated multi-turn session replay.
- **Content export controls:** the P4-A probe proved serialized `EvaluationReport`s include case `inputs`/`output` — test report-level export controls (not just spans) against Phase 3 policy allowlists before any Logfire report integration.
- Judge wiring: `judge_provider: pydantic-ai` is currently config-valid but fail-closed in `resolve_judge_provider`/preflight; decide and wire explicitly in P4-C or leave fail-closed with a recorded decision.
- Keep legacy evaluation CLI behavior readable; document new command/config selectors.

**Stop point:** offline machinery ready and gated; missing prerequisites (below) stay explicitly blocked rather than invented.

## P4-D — separately permissioned live validation (nothing may run before explicit approval)

Before any live call, return with exact approvals: quota/cash budget for the smoke and pilot, input/case counts, pinned judge model ID/route/settings (different family from the generator), and route confirmation. Then: tiny same-model/route smoke for both implementations (text, stream, structured, cancellation, one RAG case), followed by the bounded matched pilot; record confounds (including the adapter's `max_completion_tokens` wire mapping and tool/native structured mode differences), quality/completion/TTFT/latency/usage, and maintenance trade-offs. Keep pay-as-you-go spillover/auto-top-up off (D18/budget posture). Honest `User-Agent` and `x-opencode-session` only; stop on route rejection, no substitution. Offline CI gates first (evaluation/provider extras installed, no paid credentials); paid/manual/scheduled live CI is a separate D16 decision.

## P4-E — bounded cutover (only after P4-D parity evidence + explicit approval)

Pydantic Evals main runner / Logfire primary experiment UI; versioned datasets/prompts/config; small local manifest/report/cost records; archive legacy results; retire redundant W&B/custom dashboard paths only in a separately approved bounded slice.

## Earlier-phase operational exits still open (do not pretend integrated-comparison readiness)

From the auth-preflight closure and decision register — these remain blockers for integrated/live comparisons:

- **Corpus/index materialization with provenance** (current D11 snapshot honestly unverified/empty); reindex/embedding changes are separately named variants.
- **Named review-authority exercise** via the fail-closed hash-attestation mechanism (no manifest verified yet; reviewed/cohort/promotion eligibility stay false).
- **Independent judge pinning + matched baseline tuple capture** (D17 remainder: exact judge ID/prompts/temperature/token limits in a matched-run configuration snapshot).
- **Hosted Logfire configuration + permissioned smoke** (destination/access/retention under D06/D15; content modes exercised only after canaries).
- **Docker/container smoke**, **reranker asset selection/download**, **live baselines**.
- **Budget limitations disclosure:** chat serving stays ungated by design; no hard billing cap claimed.

Open decisions: D12 (co-pilot scope deferral), D13 (native history/structured answers), D14 (deployment/auth), D15 (retention/access/deletion), D16 (live CI cadence), D17 remainder (judge pinning), D18 operational-resilience variants (no-fallback is accepted for Phase 4 comparison work only).

## P4-B minor leftovers (small optional slice or fold into P4-C)

- Exact settings-bound acceptance tests (temperature 0/2, timeout 600), stream usage totals on cancellation, repeated sync-call lifecycle coverage.
- `max_completion_tokens` wire mapping and Go-route schema/stream acceptance are **live-only** questions (P4-D).

## Workflow (unchanged)

- Inspect before proposing; owner approves each bounded slice; minimal scope; no new abstractions.
- Snapshot before changes (tracked binary patch, NUL `status -uall`, lock digests, untracked hashes + copies of owned pre-existing untracked sources); preserve worker/review responses verbatim; allowed-set preservation on close.
- Parent owns integration/gates: `bash scripts/verify_phase123_offline.sh` twice in fresh processes, then statics (Ruff/format all files, MyPy `src`, import contracts, docs consistency). No bare pytest/application imports outside the approved isolation.
- GLM implementation (`glm-worker`) → Luna read-only review (`luna-reviewer`), disjoint file ownership, parent-managed repair/closure. Workers run no tests/imports/network; parent owns permissioned compatibility/network/live work.
- No secrets in tasks/outputs/artifacts; no `.env`/credential inspection; no existing-data deletion/migration; no model/corpus downloads; no hosted export; no public exposure. Deny-live protection for both Pydantic AI and existing SDK paths. No serving-default flip.
- Budget posture: USD 20/month incremental ceiling with simple tracking; existing Go subscription separate; no live spend authorized by any record in this tree.
