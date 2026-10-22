# Guard-batch review repair — 2026-10-17

**Status:** Both owner-approved code findings are repaired. Separate GPT-6 Luna `xhigh` read-only follow-up review reported **no actionable findings**. Browser execution remains blocked; **Phases 1–3 remain incomplete**.
**Approval:** Owner said “approve the repair slice” after the [two-finding review](20261016-guard-batch-review.md). This covers nullable individual-summary handling, numeric median sanitization and focused regressions, not dependency upgrades, browser provisioning or broader phase implementation.
**Prior authority:** [Guard-batch handoff](20261016-guard-batch-handoff.md). Preserve the entire dirty/untracked tree; HEAD alone does not reproduce this implementation.

**Subsequent progress:** The [approved Gemini HTTPX fix](20261017-gemini-httpx-fix-handoff.md), following [C3a](20261017-p1-c3a-handoff.md), is the latest authority: its generation-adapter finding is repaired, expanded gate 1,319 passed / 6 optional DeepEval skips, no actionable scoped Luna re-review findings. The completed reader/UI repair evidence below is historical to this preceding slice.

## Repairs

### Individual diagnostic summaries

- Individual summary duration, failed-threshold count and status are optional/nullable in TypeScript. Status remains a string so diagnostic states such as `incomplete` are representable, not falsely limited to successful/failed completed runs.
- The evaluation detail header reuses `formatDecimal` for unavailable duration/count values, displaying N/A instead of calling `.toFixed()` on null/missing data. Null/missing status displays N/A with a neutral badge. Real numeric zeroes remain `0.00s` and `0`.
- The CSV summary consumer uses N/A for missing/null values while preserving measured zeroes; there is no export-format redesign or health-score semantic change.
- Five new mocked selection cases cover null fields, missing fields in a nonempty incomplete summary, explicit incomplete status, valid zeroes and finite values. They select the partial **detail** response, check the header and selected state, collect page errors and exercise subsequent Quality/Ingestion tab navigation. Existing filtering, non-comparability and empty-history assertions remain.
- Mocked tests reject unexpected fetch/XHR, API and off-origin traffic. No real backend/index/provider is used.

### Median measurements

- The existing numeric-suffix projection now recognizes `_median`. This covers the actual emitted `retention_ratio_median` (L1), `chars_per_page_median` (L2) and `chunk_length_median` (L3), without changing scoring formulas or persisted artifacts.
- **33 new backend cases:** ten invalid/valid inputs across those three fields, plus three absent-field cases. Booleans, nonnumeric strings, null and non-finite values are unavailable; finite values and integer/float zeroes are preserved. Missing fields are not invented as zeroes.
- Regressions exercise aggregate and record projection, configuration metadata preservation, legitimate boolean L5 findings, strict JSON serialization and unchanged source-artifact bytes.

## Files changed

- `src/evals/artifact_service.py` — one additional recognized numeric suffix.
- `tests/unit/evals/test_history_comparability.py` — the 33 new cases above.
- `frontend/src/lib/types.ts` — individual-summary presence/nullability.
- `frontend/src/routes/eval/+page.svelte` — guarded header/status formatting.
- `frontend/src/lib/utils/export.ts` — minimal coordinated nullable CSV consumer.
- `frontend/tests/history-comparability.spec.ts` — partial-detail selection regressions and API interception guard.
- This handoff and migration review/status/index/decision pointers. No other application behavior or dependency/configuration defaults were changed.

## Verification

| Gate | Result |
|---|---|
| Reproduced inherited isolated gate before edits | **856 passed, 6 skipped**, seven inherited warnings |
| New median cases before production fix | **9 failed, 24 passed**; booleans/strings survived the old projection |
| New median cases after fix | **33 passed**, no skips/deselections |
| Expanded isolated gate | **889 passed, 6 skipped, 0 deselected**, seven inherited warnings |
| Ruff lint/format | Two touched Python files passed |
| Source MyPy | 154 files passed |
| Import-linter | Four contracts kept, zero broken |
| Frontend type check | 0 errors, 0 warnings |
| Frontend production build | Passed |
| Synthetic formatting/CSV runtime assertions | Five missing/null/incomplete/zero/finite cases passed using actual formatter/export functions and a synthetic DOM/Blob sink; not a browser test |
| Mocked browser attempt | **Seven blocked before test bodies**: locked Chromium headless-shell revision 1208 is absent |
| Independent read-only Luna xhigh follow-up | **No actionable findings; both in-scope findings appear resolved**; reviewer ran no tests |

All six expanded-gate skips require unavailable optional DeepEval. They are not optional API-compatibility passes. Seven inherited warnings remain (protobuf/Requests and deprecated legacy history routes); no packages were changed to silence them.

The published reproduction command below was independently rerun with the same **889 passed / 6 skipped** result. Docs consistency, local Markdown links/anchors/fences/whitespace across 21 files and `git diff --check` passed. Out-of-scope tracked diffs and all pre-existing untracked file bytes outside the approved paths remained unchanged; every prior status path remains present and both lock digests match the starting snapshot.

One disjoint GPT-6 Luna `xhigh` implementation subagent handled frontend types/header/CSV/mocked tests. Parent implemented the median repair and regressions, coordinated diagnostic status typing and fixtures, reviewed the changes and ran the gates. A second isolated subagent used explicit `--model openai-codex/gpt-6-luna --thinking xhigh` for the read-only follow-up. Its result does not certify browser execution, live providers, clinical quality or full application privacy.

No browser assets/system libraries were installed or downloaded. The browser attempt started only a loopback Vite frontend, used a non-serving synthetic API address, and failed before test bodies. The five synthetic runtime assertions are narrower than rendering/navigation verification and do not replace the blocked browser regressions.

## Durable reproduction

The original guard-batch runner retains the C2 pre-import synthetic credentials, temporary history/rate-limit/Chroma storage, and denied Python network/DNS/repository SQLite access. Its complete evaluation-test selection automatically includes the new median cases. Run the published command without relying on a temporary session script:

```bash
uv run --offline --no-sync python - <<'PY'
from pathlib import Path
handoff = Path('docs/plans/migration/20261016-guard-batch-handoff.md').read_text()
runner = handoff.split(
    "```bash\nuv run --offline --no-sync python - <<'PY'\n", 1
)[1].split('\nPY\n```', 1)[0]
exec(compile(runner, '<published-isolated-review-repair>', 'exec'))
PY
```

Do not substitute bare pytest. The new focused node IDs in `tests/unit/evals/test_history_comparability.py` are `test_median_projection_preserves_finite_measurements_and_diagnostic_metadata` and `test_missing_median_is_not_invented_as_zero`; use the same isolation prefix if narrowing the selection.

```bash
uv run --offline --no-sync ruff check src/evals/artifact_service.py tests/unit/evals/test_history_comparability.py
uv run --offline --no-sync ruff format --check src/evals/artifact_service.py tests/unit/evals/test_history_comparability.py
uv run --offline --no-sync mypy src/
uv run --offline --no-sync lint-imports
bash scripts/check_docs_consistency.sh
git diff --check
```

Frontend, from `frontend/` using already provisioned frozen-lock dependencies:

```bash
VITE_API_URL=http://127.0.0.1:9 bun run check
VITE_API_URL=http://127.0.0.1:9 bun run build
# Blocked until browser/runtime provisioning is separately approved:
VITE_API_URL=http://127.0.0.1:9 API_URL=http://127.0.0.1:9 PLAYWRIGHT_PORT=4187 \
  bun run test -- history-comparability.spec.ts
```

## Remaining work and boundaries

- Browser rendering/navigation execution and real optional DeepEval compatibility remain unverified. These code repairs do not close those validation gates.
- Subsequent [P1-C3a](20261017-p1-c3a-handoff.md) implements bounded SDK wrapper retries/public cleanup; its approved [Gemini transport fix](20261017-gemini-httpx-fix-handoff.md) resolves the generation-adapter review finding. Broader C3b request-worker work and judge SDK compatibility retain separate approval boundaries. Preflight/container parity/assets and frozen D17 baseline capture remain open.
- Phase 2 semantic/index identity, evidence metrics/coverage, reviewed pilot, actual-chunk evaluation, subprocess/index isolation and usage/cost accounting remain open. No comparison/reuse/promotion eligibility was enabled.
- Phase 3 application tracing/modes/content allowlists/canaries/exporter lifecycle remain open. The Logfire/OTel/protobuf-major dependency proposal is not adopted; destination/access/retention and hosted validation keep their separate gates.
- No new permission for packages/model assets, real provider/judge/embedding work, hosted export, corpus/index migration, stored-data cleanup, public deployment, Phase 4 or default switches is inferred.

## Preservation and rollback

All earlier dirty/untracked work remains present. HEAD remains `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`. Both locks are unchanged: `uv.lock` SHA-256 `10a308c18f3078abcade42024541464d3623d730af532b5f777f9298a0f7f8f5`; `frontend/bun.lock` SHA-256 `c524e8e748022723e3eb257ebbf7420ae734d22990ee53415ed882941ce82eaa`.

No commits, installs, application-credential inspection, live application-provider calls, hosted exports, model/corpus downloads, data migrations or stored-data cleanup occurred in this repair slice. Existing disclosed storage side effects remain untouched. Restore only this slice's incremental changes if needed, preserving all earlier work; do not operationally reintroduce the nullable-detail crash or misrepresent boolean medians as valid measurements. No data rollback/migration is required.
