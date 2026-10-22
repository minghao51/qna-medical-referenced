# Phase 4-A Pydantic AI / Pydantic Evals / OpenCode Go capability spike — 2026-10-21

**Status: spike complete. No project dependency, lock, or application code was changed.** Isolated PyPI resolution plus a network-denied synthetic probe against fake OpenAI-compatible transport. All 14 capability checks passed in two fresh sandboxed processes with zero network attempts. Latest Pydantic AI (`2.59.0`) is **incompatible** with the current lock family because it requires `openai>=3.26.0`, which `litellm 1.82.1` (any current litellm, `<3.0.0`) and the evaluation group's `langchain-openai<1` cannot accept. Two compatible candidates were fully resolved and probed: **B (recommended) `pydantic-ai-slim[openai,evals]==2.31.0` with `openai` bumped 2.24.0→2.54.0** (within 2.x), and **A `pydantic-ai-slim[openai,evals]==1.66.0` leaving `openai` untouched**. Stop per plan: owner review before any project-lock change or P4-B implementation.

## Scope and reproducibility

Work was confined to `/tmp/qna-p4a-7pVksyWl/` (`snapshot/`, `resolution/`, `probe/`, `uv-cache/`) plus this report and the `phases.md`/`README.md` index updates. Python 3.12.13, uv 0.12.1, bubblewrap 0.11.1. The repository tree was verified clean (`git status -uall` empty; `git diff --binary` and staged patch empty; zero untracked non-ignored files) before and after the spike. Project file digests: `pyproject.toml` `1d1ccdb1d71b71339de39941b954ca5ad67c1f21c979941bcc5ac77c93cb78cf`, `uv.lock` `16764a6cad2039b17821e8a99f4905d3d2083f835d7d93e73f4ee3fc29e9d340` (unchanged at close).

Registry access: public PyPI only (`pypi.org`, `files.pythonhosted.org`) for metadata, wheels, and scratch `uv lock`/`uv sync`. Official OpenCode documentation fetched from `opencode.ai`. No credential file or environment value was inspected or printed; no provider/hosted/app runtime call was made; no project test was run.

Reproduction artifacts (SHA-256):

- Full-project scratch resolutions: `resolution/cand-a/` (candidate A lock `63eefb6bfbd0df923fb809ce95e7a86f0adc75dc2ea291a232831edae589b250`), `resolution/cand-b/` (candidate B lock `7d63f1ce0a02249c2efe7c2ef3de1c37c3eb1d770d278a7ad5845865eb8d6499`), base copy `resolution/uv.lock.base`, resolver logs `resolution/lock-attempt-*.log`.
- Isolated probe manifest and environment: `probe/` (`probe/uv.lock` `c70d4cf91299247b5185a58d19ac173c139eab08503002c412f33533f6ef3528`), mirroring candidate B's relevant pins (`pydantic-ai-slim 2.31.0`, `pydantic-evals 2.31.0`, `openai 2.54.0`, plus `pydantic==2.12.5`, `anyio==4.12.1`, `tiktoken==0.12.0`, `httpx 0.28.1` to match the project family).
- Probe: `probe/probe.py` (`d3c8b68f98aac45bd93edbbae977053d4e8ed7283500a0c5fe90693d5521bf58`), outputs `probe/probe-output.json` (`97abb451492a7e21529c52f386cf490b136b65bde4309f6372983c930a170949`) and `probe/probe-output-repeat.json`.

The probe process ran under `bwrap --unshare-net` with `env -i` (clean environment, scratch `HOME`/`TMPDIR`), with Python socket/DNS monkeypatches installed **before** importing Pydantic AI/OpenAI, and a fake `httpx` transport standing in for the documented OpenCode Go OpenAI-compatible endpoint. Command shape (mirrors the approved Logfire spike):

```sh
bwrap --unshare-net --ro-bind / / --dev /dev --proc /proc \
  --bind /tmp/qna-p4a-7pVksyWl/probe /tmp/qna-p4a-7pVksyWl/probe \
  /usr/bin/env -i PATH=/usr/bin:/bin \
  HOME=/tmp/qna-p4a-7pVksyWl/probe/home TMPDIR=/tmp/qna-p4a-7pVksyWl/probe/tmp \
  PYTHONDONTWRITEBYTECODE=1 \
  /tmp/qna-p4a-7pVksyWl/probe/.venv/bin/python \
  /tmp/qna-p4a-7pVksyWl/probe/probe.py /tmp/qna-p4a-7pVksyWl/probe/probe-output.json
```

## OpenCode Go documentation — verified 2026-10-21 (documented claims only)

From `https://opencode.ai/docs/go/` (official):

- Chat Completions endpoint path: `https://opencode.ai/inference/go/openai/v1/chat/completions`; a models list exists at `https://opencode.ai/inference/go/v1/models`. **Note:** this supersedes the abbreviated base recorded in the decision register (`https://opencode.ai/inference/go/v1`) — the OpenAI-compatible path nests under `/go/openai/v1`. The adapter must pin the full base `https://opencode.ai/inference/go/openai/v1` and keep the separate Console pay-as-you-go base (`https://opencode.ai/inference/v1`) a distinct, explicitly selected route.
- Model ID **`mimo-v2.6-flash` is currently listed** on the Go route (MiMo-V2.6-Flash: $0.14 in/$0.28 out/$0.0028 cached per 1M tokens; monthly limit $60 on Go, $120 on Go Plus; 5-hour/weekly caps at 20%/50% of monthly).
- Documented client conditions: identify with an honest own `User-Agent` (example `my-coding-agent/1.0`), send a stable `x-opencode-session` per conversation; Go is designed for coding-agent-like traffic and is monitored for abuse. Owner-reported workload eligibility stands (D03); no impersonation or fabricated tool traffic.
- "Extra usage" beyond plan limits **can fall back to pay-as-you-go balance** — the adapter/config plan must keep any spillover/auto-top-up off (D18 no-fallback; budget posture), which is an account-level setting to verify at the separately approved live stage, not testable offline.
- Authentication: API key from OpenCode Console; the page does not document the exact header format (OpenAI-compatible clients send `Authorization: Bearer`), streaming behavior, or structured-output support. **Streaming/JSON-schema/tool support on the Go gateway is undocumented → offline fake-transport proof covers only request construction; actual route behavior remains untested until the P4-D gated live smoke.**

## Dependency resolution against the current lock (Python 3.12, frozen family)

Current lock family relevant here: `openai` **2.24.0**, `litellm` **1.82.1**, `langchain-openai` **0.3.35** (evaluation group, `<1`), `deepeval` 3.9.7, `pydantic` 2.12.5, `pydantic-settings` 2.12.0, `logfire` 5.2.0, OTel 1.45.1 + protobuf 6.33.6, `httpx` 0.28.1, `tiktoken` 0.12.0, `anyio` 4.12.1.

Findings from PyPI metadata and full-project scratch `uv lock` runs (all declared groups included, scratch copies only):

- **Latest `pydantic-ai-slim` 2.59.0 (and ≥2.32 generally): unsatisfiable.** Its `openai` extra requires `openai>=3.26.0` (2.40+: ≥3.8.0; 2.32+: ≥3.0.0), but `langchain-openai` ≤0.3.35 caps `openai<3.0.0`, and latest `litellm` 1.106.2 also caps `openai<3.0.0`. Resolving an `openai` 3.x lock would require removing/upgrading litellm (main dependency) and the evaluation group — an unrelated major stack change. **Stopped per plan; alternatives below.**
- **Candidate B (recommended): `pydantic-ai-slim[openai,evals]==2.31.0`** — newest release whose `openai` extra still accepts 2.x (`openai>=2.45.0`), resolved successfully with all groups: adds 9 packages (`pydantic-ai-slim`/`pydantic-evals`/`pydantic-graph` 2.31.0, `logfire-api` 5.2.0, `genai-prices` 0.1.13, `httpx2` 2.16.0, `httpcore2` 2.16.0, `httpx2-jsfetch` 1.0, `truststore` 0.10.5; `griffelib` 2.0.2 is already in the base lock and stays unchanged), updates `idna` 3.11→3.20 and `openai` 2.24.0→**2.54.0**; no removals; `pydantic`, `logfire`, OTel, litellm, deepeval, langchain family all unchanged. `httpx2` is a parallel stack (classic `httpx` 0.28.1 remains the OpenAI SDK transport).
- **Candidate A (fallback): `pydantic-ai-slim[openai,evals]==1.66.0`** — newest release accepting the locked `openai` 2.24.0 unchanged (`openai>=2.11.0`; 1.67+ needs ≥2.25). Same 9 additions and `idna` bump; **no** `openai` change. 1.x API line is older; would need its own probe pass before P4-B if selected.
- Python requirement `>=3.11` at both versions (3.12 ✓); base deps (`httpx>=0.27`, `opentelemetry-api>=1.28`, `pydantic>=2.12`, `anyio>=4.7`, `typing-inspection>=0.4`) are satisfied by the current family without changes. `pydantic-evals` 2.31.0 additionally requires `logfire-api>=3.14.1` (no-op shim; satisfied by `logfire-api` 5.2.0), `pyyaml`, `rich`.

**Proposed project dependency diff (candidate B, for owner review — NOT applied):** in `pyproject.toml` `[project.dependencies]`, add `"pydantic-ai-slim[openai,evals]==2.31.0"`. Resulting `uv.lock` diff exactly: `openai` 2.24.0→2.54.0, `idna` 3.11→3.20, plus the 9 additions listed above (full list in `resolution/cand-b/uv.lock`; 312→321 packages). The `openai` minor bump touches the existing Qwen/OpenAI-SDK baseline client — a recorded comparison confound (R12): baseline re-capture and adapter runs must use one resolved environment.

## Offline capability probe — matrix (fake transport, network denied)

All against candidate B versions (pydantic-ai-slim 2.31.0 / pydantic-evals 2.31.0 / openai 2.54.0 / pydantic 2.12.5 / httpx 0.28.1). 14/14 passed in two fresh runs; zero socket/DNS attempts recorded. **These prove request construction and framework behavior against a fake endpoint, not actual OpenCode Go route support.**

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | Version pins load | PASS | exact versions above import and interoperate |
| 2 | Sync generation | PASS | `Agent.run_sync` (via worker thread; cannot run inside a live loop), output + usage (`requests`/`input_tokens`/`output_tokens`/`total_tokens`) |
| 3 | Async generation | PASS | `await agent.run(...)` |
| 4 | Streaming deltas | PASS | true per-token deltas with `stream_text(delta=True, debounce_by=None)` (["Hel","lo"]); **default `debounce_by=0.1` groups deltas** — SSE pass-through must pass `debounce_by=None` or accept batching; final output and usage correct |
| 5 | Structured output — tool mode | PASS | default `output_type=Answer` sends `tools` (name `final_result`), returns validated `Answer` |
| 6 | Structured output — native JSON schema | PASS | `output_type=NativeOutput([Answer])` sends `response_format {type: json_schema}` and validates the parse — **whether the Go route honors json_schema is untested until the live smoke**; mode selection must be explicit and fail closed |
| 7 | Cancellation mid-stream | PASS | `task.cancel()` during streaming raises `CancelledError` at the caller; client remains usable afterwards |
| 8 | Per-conversation headers, shared client | PASS | `ModelSettings(extra_headers={"x-opencode-session": ...})` is request-scoped: stable within a conversation, distinct across conversations, absent when not set — no shared-client mutation |
| 9 | Transport identity | PASS | requests go to `<base>/chat/completions` with `Authorization: Bearer`; **provider overrides `User-Agent` to `pydantic-ai/<version>`** — honest app identification requires per-request `extra_headers["User-Agent"]` (verified to override) |
| 10 | Ownership/closure | PASS | framework does not close an injected `httpx.AsyncClient`; owner closes it (`aclose`) |
| 11 | Framework deny-live flag | PASS | `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` (or `override_allow_model_requests(False)`) makes model requests raise `RuntimeError` — usable in the P4-B offline guard, in addition to (not instead of) guarding existing non-Pydantic clients |
| 12 | Test model offline | PASS | `TestModel` runs with requests denied (for offline adapter tests) |
| 13 | Pydantic Evals local run | PASS | `Dataset(name=..., cases=[Case(...)], evaluators=[...])` + `await dataset.evaluate(task)`; `EvaluationReportAdapter.dump_json` serialization works; **serialized reports include case `inputs` and `output`** → P4-C must apply the Phase 3 content-policy allowlists to report export, not just spans |
| 14 | No auto telemetry | PASS | only `logfire-api` (no-op shim) is active without `logfire.configure()`; no OTel export started; real-`logfire` instrumentation interplay remains governed by existing Phase 3 controls and needs a project-context test in P4-B/P4-C |

API shapes pinned by this probe (2.31.0): `OpenAIProvider(base_url=..., api_key=..., http_client=httpx.AsyncClient)` → `OpenAIChatModel("mimo-v2.6-flash", provider=...)`; `Agent(model, output_type=...)`; `ModelSettings` keys include `extra_headers`, `temperature`, `max_tokens`, `timeout`; `result.usage` is an attribute (`RunUsage`); streamed results expose `get_output()`/`stream_text()`; run-level `model_settings`, `message_history`, `usage_limits`, `cancellation_token` exist.

## Risks and honest limitations

- **Unverified until the gated live smoke:** actual Go-route acceptance of `tools`, `response_format json_schema`, and SSE streaming for `mimo-v2.6-flash`; real account/key/region access; usage/cached-token reporting accuracy; session-header behavior server-side; billing spillover settings. Offline work cannot certify these.
- `pydantic-ai-slim 2.31.0` is 28 releases behind latest (2.59.0). Future upgrades hit the `openai>=3` wall until litellm/langchain-openai move; recorded as a maintenance constraint, not silently accepted.
- The `openai` 2.24.0→2.54.0 bump (candidate B) affects the existing Qwen baseline client; must be one resolved environment for any matched comparison, and existing transport tests re-run.
- Pydantic AI's `retry` behavior on invalid structured output defaults to bounded retries (`Exceeded maximum output retries` observed during probe development) — the adapter must bound and account for these (R12).
- Probe covered the slim `[openai]` model path only; no other provider SDKs were installed (per plan). Pydantic Evals Logfire report export was not exercised (no hosted destination configured; content-policy tests belong to P4-C).

## Concrete P4-B adapter/configuration plan (proposal, not implemented)

- New `src/infra/llm/pydantic_ai_client.py` implementing the existing `LLMClient` protocol (sync/async/text-stream/structured) on `OpenAIChatModel` + `OpenAIProvider` with an app-owned `httpx.AsyncClient` (honest `User-Agent` via per-request `extra_headers`; opaque stable per-conversation `x-opencode-session` from the chat session; no shared-state mutation; owner closes the client in app cleanup, mirroring `QwenClient.aclose`).
- Settings (R05, non-secret precedence unchanged): extend the provider literal to include `pydantic-ai`; add small allowlisted fields for the Go base URL (default `https://opencode.ai/inference/go/openai/v1`), API key (`SecretStr`), model (default `mimo-v2.6-flash`), temperature/max-tokens, and an explicit structured-output mode (`tool`|`native-json-schema`) that **fails closed** when the route rejects it. Unknown providers/combos must raise, never fall back to Qwen. No fallback/substitution (D18).
- Wire `get_client()` factory + app lifespan ownership; keep Qwen/Gemini/LiteLLM selectable with no new tokens; diagnostics/cache identity must report the actual model+route.
- Offline tests: fake-transport contract tests in the existing MockTransport style (sync/async/stream/structured/cancel/headers/usage), a session-isolation test, plus a deny-live guard that sets `ALLOW_MODEL_REQUESTS=False` **and** blocks the non-Pydantic clients' network (the Pydantic flag does not protect existing clients).
- Exact files: `src/infra/llm/pydantic_ai_client.py`, `src/infra/llm/__init__.py`, `src/config/settings.py`, `src/app/factory.py`, tests under `tests/unit/infra/llm/` — pending the owner's dependency decision here.

## Stop point (per P4-A authorization)

Owner review requested on: (1) candidate choice — **B (2.31.0, `openai`→2.54.0)** recommended, A (1.66.0, unchanged `openai`) as the zero-bump fallback; (2) the exact project dependency diff above. No project lock change, P4-B implementation, live call, credential inspection, hosted export, or default switch has occurred or is implied by this report. GLM/Luna worker split applies from P4-B implementation onward; this spike was parent-owned per the pickup brief.
