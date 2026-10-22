# Gemini HTTPX transport — P1-C3a review fix

**Status:** Approved GeminiClient transport fix implemented and verified; separate Luna `xhigh` read-only review reported **no actionable findings**. The original P2 finding is resolved on the application constructor path. **Phases 1–3 and the broader P1-C/R01/R03 gates remain incomplete.**
**Approval:** The owner said **“proceed with the fix”** after the explicit proposal to select Gemini's public HTTPX async transport, own its cleanup and add constructor/lifecycle regressions, **without an SDK upgrade**. This is an approved SDK-transport change, not a provider/model/profile switch.
**Prior authority:** [P1-C3a](20261017-p1-c3a-handoff.md), which recorded the original default-aiohttp nested-retry finding. Preserve its evidence and the entire dirty/untracked tree.

## Repair

- `GeminiClient.__init__` creates one application-owned `httpx.AsyncClient(follow_redirects=True)` and supplies it through the SDK's **public** `HttpOptions.httpx_async_client` option. This selects HTTPX on the actual application path instead of allowing default aiohttp's separate connection-error retry.
- Redirect behavior matches the SDK's HTTPX default. HTTPX TLS verification and environment-proxy defaults are retained; the application does not inject a custom transport that would silently disable environment proxy selection.
- The installed SDK does not close an injected HTTPX client. `GeminiClient.aclose()` therefore attempts SDK async cleanup, owned HTTPX cleanup on the calling loop, and sync SDK cleanup off-loop even if an earlier cleanup fails. Cancellation takes priority over ordinary errors; multiple ordinary cleanup failures propagate together. No new cleanup framework or fire-and-forget task was introduced.
- Only the client created by this constructor is owned. Existing `__new__`/manually injected SDK cases without the ownership attribute do not acquire ownership of external HTTPX clients.
- The synchronous SDK path, public request interfaces, per-call retry/timeout settings, stream retry-before-content/no-replay rules, prompts, schemas, temperature/tokens, provider/model/profile defaults and dependencies are unchanged.

### Constructor-failure boundary

If synchronous SDK construction itself raises, the newly allocated HTTPX object has performed no I/O/opened no connections. The exception propagates; synchronous construction does not promise awaited disposal of that never-used Python object. No extra loop/thread/background cleanup workaround is started. The regression retains that unused object only for inspection, then disposes it in fixture teardown. This is distinct from **successfully constructed** clients: subsequent history/store startup, body and cleanup failures close the owned pool through the existing application lifecycle.

## Files

- `src/infra/llm/gemini_client.py` — constructor transport selection/ownership and three-part cleanup only.
- `tests/unit/infra/test_gemini_client.py` — existing mocked-SDK fixture also mocks HTTPX construction, avoiding real client allocation in those legacy fake-SDK tests.
- `tests/unit/infra/test_gemini_httpx_transport.py` — **29 cases**, actual application constructor and installed public SDK over in-memory HTTPX transports; fail-if-used public aiohttp request hook. Covers connection/read-timeout/500 failures at total attempts one/three across async text/structured/stream, successful shared-pool reuse, model/redirect/trust-env behavior, normal cleanup, single/multiple cleanup failures/cancellation and zero-I/O SDK-constructor failure.
- `tests/integration/app/test_gemini_transport_lifecycle.py` — **8 cases**, real app lifespan with synthetic storage/native SDK transport: history/store/body failures × SDK-cleanup failure, normal shutdown and owned cleanup drained through repeated asyncio cancellation.
- This handoff and migration decision/status/index pointers. No other application files, SDK internals, package manifests/locks, storage or frontend code were changed.

The actual constructor is tested, not a `__new__` fixture that preselects HTTPX on behalf of the application. Pool-closed assertions happen before fixture fallback disposal, so test teardown cannot disguise an application cleanup leak. Sync SDK cleanup and async owned cleanup thread/loop behavior are checked.

## Verification

| Gate | Result |
|---|---|
| Inherited isolated gate before edits | **1,282 passed, 6 skipped**, seven inherited warnings |
| New cases against saved pre-fix Gemini module | **37 failed**; separate isolated process loading the source snapshot, no working-tree rollback |
| New constructor/lifecycle gate | **37 passed**, no skips/deselections |
| Repeated fresh-process 37-case gate | **10/10 passed**, **370 case executions** |
| Expanded isolated gate | **1,319 passed, 6 skipped, 0 deselected**, seven inherited warnings |
| Ruff lint/format | Four touched Python files passed |
| Source MyPy | 154 source files passed |
| Import-linter | Four contracts kept, zero broken |
| Separate read-only Luna xhigh review | **No actionable findings**; reviewer ran no tests |

One disjoint implementation subagent and a separate read-only reviewer use explicit `--model openai-codex/gpt-6-luna --thinking xhigh`. Parent owns the new regressions, integration, isolated execution and documentation. No SDK upgrade: google-genai remains **2.6.0**, OpenAI **2.24.0**, LiteLLM **1.82.1**. Native calls use synthetic keys and in-memory HTTPX transport; default aiohttp request use fails the test. No sockets, actual provider/embedding/judge calls or model/corpus assets are involved.

All six expanded-gate skips require unavailable optional DeepEval; they are not compatibility passes. Seven inherited warnings remain (protobuf/Requests and deprecated history routes). The new-file gate has only the three inherited import warnings. No dependencies were changed to silence warnings. Frontend type/build/browser checks were not rerun for this backend-only fix; previous browser provisioning/execution and optional SDK gates remain open.

The published isolated command below was independently rerun: **1,319 passed / 6 skipped**. Docs consistency, local Markdown links/anchors/fences/whitespace across 23 files and `git diff --check` passed. Preservation checks confirmed byte-identical out-of-scope tracked diffs/prior untracked files, all previous status paths retained, only approved files changed/added and both lock digests unchanged. All implementation/reviewer/gate processes exited.

### Why the older diagnostic can still show two requests

The [C3a default-aiohttp diagnostic](20261017-p1-c3a-handoff.md#durable-default-aiohttp-finding-probe) intentionally bypasses `GeminiClient.__init__` and directly constructs the SDK with its native default transport. That underlying SDK behavior is not patched/upgraded. The repair is explicit selection of the supported HTTPX transport by the **application constructor**, verified by the new regressions and rejected aiohttp hook. Do not use the native-default diagnostic alone to judge the repaired application path, or claim the SDK's default aiohttp path was fixed.

## Durable isolated reproduction

From repository root, retain C3a's published C2/guard pre-import network/storage isolation and previous targets, adding only the two new files:

```bash
uv run --offline --no-sync python - <<'PY'
from pathlib import Path
handoff = Path('docs/plans/migration/20261017-p1-c3a-handoff.md').read_text()
runner = handoff.split(
    "```bash\nuv run --offline --no-sync python - <<'PY'\n", 1
)[1].split('\nPY\n```', 1)[0]
exec(compile(
    runner.rsplit('\nraise SystemExit(pytest.main([', 1)[0],
    '<published-Gemini-HTTPX-pre-import-isolation>', 'exec',
))
repair = [
    'tests/unit/infra/test_gemini_httpx_transport.py',
    'tests/integration/app/test_gemini_transport_lifecycle.py',
]
raise SystemExit(pytest.main([
    '--no-cov', '-q', *targets, *new, *repair,
    '-m', 'not live_api and not live_openrouter and not e2e_real_apis '
          'and not network and not deepeval',
]))
PY
```

For the **37-case** gate, use `*repair` without `*targets, *new` in the same isolated runner. Repeat in fresh processes. Do not substitute bare pytest or the full legacy HyDE file; no session-local `/tmp` script is required. Isolation sets synthetic credentials/temp history/rate-limit/Chroma paths and denies Python network/DNS/repository SQLite before application/test imports.

```bash
files=(
  src/infra/llm/gemini_client.py tests/unit/infra/test_gemini_client.py
  tests/unit/infra/test_gemini_httpx_transport.py
  tests/integration/app/test_gemini_transport_lifecycle.py
)
uv run --offline --no-sync ruff check "${files[@]}"
uv run --offline --no-sync ruff format --check "${files[@]}"
uv run --offline --no-sync mypy src/
uv run --offline --no-sync lint-imports
bash scripts/check_docs_consistency.sh
git diff --check
```

## Remaining work and boundaries

- This fixes the approved `GeminiClient` generation adapter, not every SDK transport/auth/router/callback configuration. The separate `GeminiJudgeModel` in `src/evals/deepeval_models.py` still constructs its own default SDK client; judge/optional DeepEval transport compatibility is outside this fix and remains unverified. No all-Gemini-call retry, real-provider billing/clinical quality or blanket privacy certification is inferred.
- Native Gemini per-stream **physical** HTTP response release remains unverified; shared-pool close at application shutdown is not proof of immediate per-request response release. No private SDK patch, forced thread termination or hard cleanup deadline was added.
- Broader P1-C3b request/response-worker ownership, abandoned/never-entered iterators, remaining server/send-error/shutdown paths, preflight/container parity, approved assets and frozen D17 `baseline` capture remain open. Inspect and present the next bounded plan before edits.
- Phase 2 semantic/index identity, evidence metrics/failure denominators, reviewed cases, actual-chunk evaluation, isolation/replay and usage/cost accounting remain open. Comparison/promotion/reuse remains fail closed.
- Phase 3 application tracing/modes/allowlists/canaries/exporter lifecycle/access/retention and Logfire/OTel/protobuf dependency adoption remain separately gated. Browser/runtime provisioning, optional DeepEval compatibility and all live/export/model/corpus/data/default/Phase 4 permissions are unchanged.

## Preservation / rollback

No installs, credentials inspection, live application-provider calls, hosted exports, model/corpus downloads, data/index migration/cleanup, commits/reset/stash/clean or provider/model/profile changes occurred. Preserve every prior dirty/untracked file and disclosed earlier storage side effects. If necessary, reverse only this incremental Gemini constructor/cleanup/test slice while preserving the entire earlier tree; doing so restores the known default-aiohttp attempt-bound gap and is not a safe live-provider completion state. No stored-data rollback/migration is required.

HEAD remains `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`. Locks unchanged: `uv.lock` SHA-256 `10a308c18f3078abcade42024541464d3623d730af532b5f777f9298a0f7f8f5`; `frontend/bun.lock` SHA-256 `c524e8e748022723e3eb257ebbf7420ae734d22990ee53415ed882941ce82eaa`.
