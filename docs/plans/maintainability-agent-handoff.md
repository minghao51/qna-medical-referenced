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

## Progress log

### M0 — baseline reproduced (unchanged from verification)

2,284 passed / 2 skipped / 117 deselected, 82% coverage, all static gates green.
The run also proved the suite wrote project data (details under M1).

### M1 — test opt-ins and data isolation (commit `4c8a35f`)

- `tests/conftest.py` gates `live_api`, `live_openrouter` and `e2e_real_apis`
  independently (2^3 matrix covered without provider calls).
- Session-level mutation guard fingerprints the whole `data/` tree and fails the
  run on any created/modified/removed file; `tests/unit/test_test_isolation_policy.py`
  statically rejects unisolated `ChromaVectorStore(...)` constructions.
- Tests that reached the real index, `data/processed` or `data/raw` are isolated.
  The guard found three leaks that content hashes had hidden: the raw-corpus PDF
  loader in two tests and the dataset builder, which rewrote ten artifacts with
  identical bytes.
- Placeholders replaced with real contracts: `download_with_retry` attempts and
  terminal failure, `ArtifactStore` write failures leaving no residue, and two
  offline artifact tests extracted from the live-marked eval module.

### Data cleanup (not a commit; `data/` is gitignored)

Removed the three test collections (`test_empty`, `test_embedding`,
`test_source_metadata`) and six `/tmp`-sourced artifacts. Re-ran the offline
identity builder: corpus identity (`data/raw`, 121 files) and index identity
(`medical_docs`, 2,473 docs, fingerprint `a0dc5d29…`) match the recorded frozen
identity exactly. Backup: `/tmp/cleanup-backup`. The local corpus no longer
matches any earlier R2 upload; re-upload remains an owner decision.

### M2 — command surface and coverage (commit `4d38a1e`)

`scripts/check_backend.sh` (with `Makefile`) is the single source of the marker
selection: `fast`, `offline`, `unit`, `integration`, `coverage`, `lint`,
`smoke`, `frontend-check`, `frontend-test`. Coverage left pytest `addopts`; the
coverage mode reports project-wide with an explicit 80% floor against a measured
82% baseline. CI uses one offline coverage job plus smoke, attaches no secrets
and has job timeouts. Shell-policy tests pin selection, quoting, exit codes and
read-only lint.

Measured after M1+M2: fast 2,315 passed / 1 skipped / 115 deselected (~41 s);
offline 2,336 passed (~44 s); coverage 82% (floor 80); all of `data/` unchanged
across every mode.

### Also fixed: telemetry canary flake (commit `7a7815e`)

The two hosted-export canary tests asserted `aclose()` against a 100 ms budget;
under CPU contention the lifecycle thread hand-off exceeded it and returned
False. Test budget is now 1 s, with the bounded-lifecycle contract still
asserted by the blocking-exporter unit tests.

### Still open

M3 dependency-audit repair, M4 docs/config truth-sync, M5/M6 artifact
containment and HTTP contracts, M7 frontend parser tests, M8/M9 extraction,
M10 serving metadata, M11 strict sync integrity, M12 deployment hardening — all
under their existing approval gates. R2 re-upload/re-freeze is a separate
owner decision.
