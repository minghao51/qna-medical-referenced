# Phases 1–3 — Resumed security and history guard batch

**Status:** Bounded code repairs implemented and isolated compatibility research complete; **Phases 1–3 remain incomplete**. The [Luna review findings](20261016-guard-batch-review.md) were repaired in the owner-approved [2026-10-17 follow-up](20261017-review-repair-handoff.md), with 889 passed / 6 optional DeepEval skips and no actionable re-review findings. Browser execution remains blocked. Evidence below describes the original guard batch; no application tracing or dependency adoption is claimed.
**Approval:** The owner resumed [the approved next batch](20261016-phases-1-3-resume-handoff.md), requesting OpenAI Codex GPT-6 Luna `xhigh` implementation subagents and OpenCode Go MiMo V2.6 Flash review. Prior dirty/untracked work remains present; HEAD alone does not reproduce this tree.

## Delivered boundaries

### A. Dedicated signing, provider validation and worker topology

- `APP__API__SESSION_SIGNING_SECRET` is a separate `SecretStr` setting. Outside development it is required and must contain at least 32 UTF-8 bytes after trimming outer whitespace. An explicitly weak value fails in every mode. Caller API keys and environment names are never signing-key sources.
- Development without a configured secret uses a process-random key. Restarting that process, rotating a configured secret, or moving from the old signer invalidates existing cookies and starts fresh sessions. Historical messages are not deleted/migrated; old insecure signatures are not accepted.
- Startup security validation and the signing-key boundary both fail with neutral errors for invalid configuration, including plaintext and JSON caller authentication. Tampering, malformed/non-ASCII signatures, caller-key independence and rotation have synthetic regressions.
- Generation providers are constrained to `qwen`, `gemini`, and `litellm`; the client factory independently rejects unknown runtime values rather than falling back to Qwen. Existing provider/profile defaults remain unchanged.
- The production CLI rejects `--workers` values other than `1` before invoking Uvicorn. Existing host/port defaults remain. Independent processes/store instances sharing file history remain unsupported; this is not cross-process locking.
- `.env.example` and [local operating constraints](../../local-workflows.md#private-lab-production-mode-constraints) document the supported setting and topology. Broader setup/preflight/container parity remain pending.

### B. Diagnostic history, not cross-run comparisons

- History retains artifact-bearing incomplete/failed records alongside legacy/versioned/unsupported records. Every projected record remains non-comparable; an arbitrary persisted boolean or matching hash cannot establish a comparison cohort.
- Aggregate hit rate, MRR, latency and duration are `null`, including empty history. Total/source counts remain available. This deliberately changes history counts to include diagnostic attempts; the separate legacy run-list/latest-selection policy is not redesigned.
- Missing, boolean and non-finite numerical measurements project as unavailable rather than measured zeroes. Individual payload/list responses remain JSON-safe without rewriting source artifacts. Valid zeroes, configuration/metadata and legitimate boolean L5 findings are preserved.
- Nullable TypeScript fields, N/A formatting and a visible notice replace invalid historical charts/metric selectors. Individual filtering/selection and legacy detail access remain. No new cohort/dashboard framework or verified comparison eligibility is introduced.
- Mocked browser regressions deny unexpected API/off-origin traffic and cover N/A, absent charts, filtering/selection and empty history. They are added and type-checked, **not browser-executed successfully** in this environment.

### C. Logfire compatibility boundary

The approved spike is complete as isolated research, using scratch environments/copies rather than the project environment/lock. Candidate **Logfire 5.2.0** resolves with the declared evaluation-group/Chroma constraints, but moves OTel **1.27.0 → 1.45.1** and protobuf **4.25.9 → 6.33.6**. That major transitive change blocks project adoption pending separate review/approval. The 4.6.0 metadata-only alternative also moves dependencies and is not a runtime-validated fallback.

Parent independently reran the network-namespace-isolated synthetic SDK probe: no network attempts or console output; manual span correlation worked. Default FastAPI instrumentation captured body values; exception text/stack paths and custom-scrub notes can retain content; a controlled mapper/callback removed the tested canaries. SDK flush/shutdown timeout arguments did not impose a hard wall-clock bound on a slow synchronous processor. These are adoption/privacy/lifecycle blockers, not a tracing implementation.

The separate [compatibility report](20261016-logfire-compatibility-spike.md) records exact pins, resolver changes, official links and a durable standalone probe/installed closure. Application tracing, a project dependency pin, exporter adoption and hosted export remain unimplemented. Synthetic SDK probes certify neither whole-application privacy nor a hard shutdown deadline.

## Files in this slice

- Backend: `src/config/settings.py`, `src/app/{session,security}.py`, `src/infra/llm/__init__.py`, `src/cli/serve_production.py`, `src/evals/artifact_service.py`, and the history documentation in `src/app/routes/evaluation.py`.
- Tests: new `tests/unit/app/test_session_security.py`, `tests/unit/infra/test_llm_provider_selection.py`, `tests/unit/cli/test_serve_production.py`, `tests/unit/evals/test_history_comparability.py`; updated `tests/integration/app/test_app_security.py` synthetic production fixture and `tests/unit/app/test_evaluation_routes.py` history assertions.
- Frontend: `frontend/src/lib/{types.ts,utils/eval.ts,components/TrendingTab.svelte}`, the minimal prop coordination in `frontend/src/routes/eval/+page.svelte`, and new `frontend/tests/history-comparability.spec.ts`.
- Configuration/docs: `.env.example`, local workflow constraints, migration status/decision/environment pointers and this handoff. Preserve all earlier changes outside this slice.

## Verification and review limits

| Gate | Result |
|---|---|
| Inherited isolated gate before edits | **819 passed, 6 skipped**, seven inherited warnings |
| Expanded isolated gate after integration | **856 passed, 6 skipped, 0 deselected**, seven inherited warnings |
| Focused security gate after malformed-cookie fix | **42 passed, 1 skipped** (included in expanded gate) |
| Ruff check/format | **13 touched Python files passed** |
| Source MyPy | **154 files passed** |
| Import-linter | **Four contracts kept, zero broken** |
| Frozen-lock frontend installation | Succeeded; Bun **1.2.23**, Node **24.18.1**, locked Playwright **1.58.2** |
| Frontend type check | **0 errors, 0 warnings** |
| Frontend production build | Passed |
| Synthetic formatting assertions | Passed for missing/null/boolean/non-finite values and valid zeroes; not a browser test |
| Isolated Logfire SDK probe | Subagent evidence reproduced by parent in a clean environment/network namespace; unsafe capture and timeout-overrun findings confirmed |
| Mocked browser attempt | **Two blocked before test bodies**: required Chromium/headless-shell revision **1208** absent |
| Original MiMo review attempt | **Unavailable**: `opencode-go/mimo-v2.6-flash` returned HTTP 400 `model_coming_soon` |
| Original owner-approved Luna replacement review | Two findings (nullable detail duration and numeric medians), subsequently repaired/re-reviewed in the [follow-up](20261017-review-repair-handoff.md). |

All six expanded-gate skips require unavailable optional DeepEval. They are not optional API-compatibility passes. The seven inherited warnings are protobuf/Requests and deprecated legacy history-route warnings; no dependencies were changed to silence them.

Three disjoint implementation/spike subagents used explicit `--model openai-codex/gpt-6-luna --thinking xhigh`. Parent integrated/reviewed the code and ran the expanded/static/frontend gates. Integration reproduced and fixed a non-ASCII signature exception, corrected a fixture ordering expectation, preserved configuration/legitimate boolean findings during projection, added a JSON-safe run-list regression and removed unused frontend CSS. Parent checks did not replace the original requested review. The owner subsequently approved a separate GPT-6 Luna `xhigh` read-only reviewer; it found two issues and ran no tests. Passing type/build checks and the earlier gate did not cover the missing/null detail-duration path. The owner-approved [follow-up](20261017-review-repair-handoff.md) repairs both issues and adds regressions; its browser execution is still blocked.

Browser cache revision 1243 is present but is not the locked revision; its executable also lacks `libnspr4`, NSS and ALSA libraries. No browser assets/system packages were downloaded/installed, and no successful browser validation is claimed. The attempted test command ran only a loopback Vite frontend, with a non-serving synthetic API address; no backend/index/provider was started.

Documentation/preservation checks passed: docs consistency, local links/anchors/fences/whitespace across 19 Markdown files, and `git diff --check`. Out-of-scope tracked diffs remained byte-identical to the captured starting patch; every prior dirty/untracked status path remains present. Both lock digests are unchanged, and the project environment still has no Logfire and OTel SDK 1.27.0. The published Python runner below was independently rerun with the same **856 passed / 6 skipped** result. The durable SDK appendix matches the executed probe byte-for-byte and retains its 40 installed package pins.

## Durable isolated reproduction

Use the C2 pre-import storage/network isolation and the foundation's expanded selection, adding only the actual new files and existing route tests. From the repository root:

```bash
uv run --offline --no-sync python - <<'PY'
import os
from pathlib import Path

os.environ['APP__API__SESSION_SIGNING_SECRET'] = 'synthetic-offline-session-signing-secret'
handoff = Path('docs/plans/migration/20261016-p1-c2-handoff.md').read_text()
runner = handoff.split(
    "```bash\nuv run --offline --no-sync python - <<'PY'\n", 1
)[1].split('\nPY\n```', 1)[0]
exec(compile(
    runner.split('raise SystemExit(pytest.main([', 1)[0],
    '<C2-isolated-guard-batch>', 'exec',
))
extra = ['tests/unit/evals/', 'tests/unit/experiments/']
targets = [
    target for target in targets
    if not any(target.startswith(directory) for directory in extra)
] + extra + [
    'tests/unit/app/test_session_security.py',
    'tests/unit/infra/test_llm_provider_selection.py',
    'tests/unit/cli/test_serve_production.py',
    'tests/unit/app/test_evaluation_routes.py',
]
raise SystemExit(pytest.main([
    '--no-cov', '-q', *targets,
    '-m', 'not live_api and not live_openrouter and not e2e_real_apis '
          'and not network and not deepeval',
]))
PY
```

The prefix denies Python network/DNS/repository SQLite access before collection, uses synthetic credentials and redirects history/rate-limit/Chroma storage to temporary paths. Do not replace it with bare pytest. No session-local `/tmp` script is required.

Frontend validation after the approved installation:

```bash
cd frontend
bun install --frozen-lockfile
bun run check
bun run build
# Currently blocked on browser provisioning; no implicit asset download:
VITE_API_URL=http://127.0.0.1:9 API_URL=http://127.0.0.1:9 PLAYWRIGHT_PORT=4187 \
  bun run test -- history-comparability.spec.ts
```

## Next bounded work and stop conditions

- The two [Luna findings](20261016-guard-batch-review.md) are repaired and re-reviewed in the [follow-up](20261017-review-repair-handoff.md). Provision locked browser/runtime dependencies only with approval, then execute all seven mocked browser regressions without a real application backend. Do not treat the new backend/type/build checks as browser execution.
- Review the Logfire 5.2.0/OTel/protobuf-major change before any project-lock adoption, or approve a focused compatible-version/constraint investigation. Unsafe automatic capture and exporter lifecycle remain implementation gates, not solved by a package spike.
- Propose a concrete P1-C3 request-worker/SDK cancellation and nonstream retry slice. P1-D preflight/assets/container parity and corrected D17 baseline capture remain open.
- P2 effective semantic/index snapshots, reviewed metrics/coverage, subprocess/index isolation and monthly usage/cash/quota accounting remain open. All current runs remain non-comparable/non-promotion-eligible.
- P3 tracing/modes/all-boundary canaries/lifecycle remain open. D07/D08/D15 and remaining D17 matched generation settings retain their gates. Phase 4, live provider/judge/embedding work, corpus/model assets, hosted export, data migrations/cleanup, public deployment and default switches are not authorized by this batch.

## Identity, preservation and rollback

HEAD remains `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`; work is uncommitted. Python remains **3.12.13**. Project `uv.lock` SHA-256 remains `10a308c18f3078abcade42024541464d3623d730af532b5f777f9298a0f7f8f5`; `frontend/bun.lock` remains `c524e8e748022723e3eb257ebbf7420ae734d22990ee53415ed882941ce82eaa`.

Package-registry access/installations were limited to the approved frozen frontend dependencies and isolated compatibility work. No application credentials were inspected, no application-provider calls or hosted exports were made, no real stored data was migrated/cleaned/reindexed, and no model assets were downloaded. The attempted coding-review model call is not an application-provider smoke. Earlier disclosed storage side effects remain untouched.

Rollback only this slice's incremental changes while preserving the full earlier tracked/untracked tree. Do not operationally restore predictable signing, unknown-provider fallback, unsupported multiworker file writes or invalid historical comparisons. Disable new presentation behavior only without relabeling artifacts or deleting history. There is no stored-data rollback/migration to run.
