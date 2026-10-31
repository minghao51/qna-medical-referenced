# Agent pickup: maintainability and setup improvements

## Read first

1. Repository `AGENTS.md` and `.planning/codebase/*`.
2. [Verified findings/corrections](maintainability-verification.md).
3. [Full implementation specification](maintainability-implementation-plan.md).
4. Existing [structural roadmap](20260910-structural-refactor-roadmap.md),
   [migration decision register](migration/decisions.md), and applicable current
   migration pickup documents. Historical work is not unimplemented just because
   an old roadmap lists it.
5. [Earlier F-01–F-11 follow-ups](migration/20261030-audit-followups.md), qualified
   by the new verification report rather than accepted verbatim.

Baseline: `66cb168`, clean at review start. Planning package itself will be an
additional uncommitted diff unless the owner commits it. Recheck HEAD/status;
never discard existing work. No application implementation was performed here.

## Suggested first message / approval request

> I have read the verification and implementation specification. I propose M0
> baseline reproduction, then M1 independent live-test opt-ins and meaningful
> offline tests. I will not touch dependencies, data, providers, auth policy or
> deployment posture. After targeted tests and the full offline gate, I will
> report evidence and propose M2 separately. May I proceed?

Do not interpret the user's request to draft a handoff as approval to implement
every proposed slice. Present the concrete file-level plan before changes per
AGENTS.md. Decision-gated tasks need specific approval, not a broad implied yes.

## Current evidence

- Offline suite: **2,284 passed, 2 skipped, 117 deselected, 4 warnings, 51.78s**.
- Playwright collect-only: **58 tests in 6 files**. No new browser execution.
- Historical coverage: 82%; clean CI-group coverage needs reproduction.
- Test hooks contain a real independent-opt-in bug. CI coverage interpretation in
  the earlier review was incorrect: integration inherits `--cov=src`, and unit
  coverage arguments append to it. Fix truthfully, not to the earlier narrative.
- Equal-size R2 drift is checked, but 1–100 byte unequal-size drift is accepted
  by current verify. No R2 operations were run during verification.
- No fresh live-provider, dependency-audit network, Docker runtime, or clinical
  validation evidence is implied.

## Minimum safe commands before M2

```sh
uv run --frozen python -m pytest --no-cov -q \
  -m 'not slow and not live_api and not live_openrouter and not e2e_real_apis and not deepeval and not network'
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy src
uv run --frozen lint-imports
uv run --frozen bandit -r src/ -ll
bash scripts/check_docs_consistency.sh
```

Use targeted tests first. Optional-group availability is environment-specific;
`uv run --frozen` does not prove the environment is identical to a fresh CI sync.
Do not call `uv sync` casually in a shared working environment: it can remove
optional packages. Use an isolated approved environment for clean-install gates.

No secrets/identifiers in reports. No test may rebuild the frozen index or reuse
project chat/rate state. Scratch files under `/tmp`; do not create source fixtures
from private history. Never run live tests merely to reproduce a long run.

## Task-to-follow-up crosswalk

| Earlier follow-up | This specification |
|---|---|
| F-01 profile ratification | Explicit owner decision; M4 records current truth only |
| F-02 roles/admin | Still deferred; draft policy only until newly approved |
| F-03 metadata/read-only | M10; revision invalidation separate from read-only policy |
| F-04 schema drift | M6 OpenAPI/SSE contract guard |
| F-05 SSE parser | M7; no auto-retry/reconnect for POST generation |
| F-06 API hardening | M5 containment/counts, M6 body/error contract |
| F-07 sync integrity | M11; includes unequal-size verify blind spot |
| F-08 live/offline tests | M1 |
| F-09 legacy index clarity | M4, no backfill or data move |
| F-10 proxy/NAT | M12 deployment decision |
| F-11 dependency bounds | M3 actual audit + deliberate lock-refresh policy |

## Work and review protocol

- One file owner; do not let two agents edit workflow/settings/lockfiles at once.
- Prefer one patch per M-task/sub-extraction. No broad cleanup alongside a fix.
- Report observed defects, assumptions and deferred decisions separately.
- Parent owns final gates, diff review, staging/commit/push. Workers must not
  commit/reset/stash, alter dependencies, or act on remote services by default.
- Every task report includes changed files, acceptance evidence, limitations,
  data-write checks, rollback and next approval request.
- Stop on data mutation, provider calls from offline tests, changed fingerprint/
  artifact schemas during extraction, new cycles/exemptions, or failed baseline.
- Do not substitute a numerical grade for evidence or give unsupported day estimates.

## Final delivery format

1. Implemented slices and commit IDs (if owner approved commits).
2. Exact test/static/browser/container/audit commands and outcomes.
3. Measured coverage/timings with environment/group scope.
4. Contract/parity and runtime-data safety evidence.
5. Open decision gates, environmental blocks and residual risks.
6. Updated plan checklist and docs/current-status links.

Do not mark gated tasks done because their implementation was skipped.
