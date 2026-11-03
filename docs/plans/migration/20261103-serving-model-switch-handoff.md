# Serving model switch — OpenCode Go MiMo + LongCat — 2026-11-03

**Status:** implemented and smoke-tested. The running app now serves chat through
OpenCode Go with `pydantic-ai` / `mimo-v2.6-flash` and judges with
`longcat-2.0`. Embeddings remain on Qwen `text-embedding-v4`; the D11 index was
not rebuilt or re-embedded.

## Approval

Owner approved making the running app’s text roles consistent on OpenCode Go,
selected MiMo V2.6 Flash for chat instead of DeepSeek V4.1 Flash, confirmed the
LongCat judge and the remaining plan, and reconfirmed that the Go route is
acceptable for the public/synthetic medical Q&A workload under D03.

## Runtime tuple

| Role | Provider | Model |
|---|---|---|
| Chat generation | `pydantic-ai` / OpenCode Go | `mimo-v2.6-flash` |
| Judge light/heavy | `pydantic-ai` / OpenCode Go | `longcat-2.0` |
| Embeddings | Qwen / DashScope | `text-embedding-v4` (unchanged) |
| Reranker | Disabled | unchanged |

`judge_max_tokens` is `16384`. The generator and judge share the OpenCode Go
route; model-family independence is preserved, route independence is not.

## Changes

- `config/settings.yaml`: provider/judge defaults and MiMo/LongCat models.
- `docker-compose.yml`: passes the pydantic-ai key, base URL, model, judge
  models and judge cap.
- `.env.example`, `.env.demo.example`: OpenCode Go key placeholders and current
  defaults; Gemini remains an explicit fallback.
- `src/cli/preflight.py`: `pydantic-ai` is now a supported generation provider
  and reports `pydantic_ai_model`. This supersedes the earlier fail-closed
  posture.
- `src/evals/deepeval_models.py`: `_generation_details`/`effective_roles`
  record pydantic-ai generation instead of raising.
- `src/usecases/runtime_config.py`: reports the pydantic model instead of the
  Qwen fallback name.
- `src/evals/pydantic_ai_judge.py`: reuses a caller conversation scope or binds
  one stable opaque session per judge instance, because OpenCode Go requires
  `x-opencode-session` and DeepEval may call the judge outside a chat request.
- Tests updated/added for preflight, effective roles, runtime config, container
  wiring, judge session binding, and provider inheritance.

No dependency or lockfile change: `pydantic-ai-slim[openai,evals]` was already a
main dependency.

## Verification

- `bash scripts/check_backend.sh fast`: **2371 passed, 1 skipped, 115
  deselected**.
- `bash scripts/check_backend.sh offline`: **2392 passed, 1 skipped, 94
  deselected**.
- `bash scripts/check_backend.sh lint`: Ruff, format, MyPy, import-linter,
  Bandit and docs consistency all passed.
- `frontend: npm run check`: 0 errors, 0 warnings.
- `frontend: npm run build`: passed.
- Preflight with the real local `.env`: `ok=true`; generation
  `pydantic-ai`/`mimo-v2.6-flash`, judge `longcat-2.0`, embedding
  `text-embedding-v4`; all required credentials ready.

## Bounded live smoke

Synthetic prompts only; no corpus, patient data or secrets were sent.

- MiMo text generation: succeeded (17.8 s, 1,338 characters). The prompt asked
  for exactly `smoke ok`; the model returned a longer response, so no
  instruction-exactness or quality claim is made.
- MiMo SSE stream: succeeded (18 chunks, 219 characters, 5.4 s).
- Full app `POST /chat` through retrieval and D11: HTTP 200 SSE, coherent
  answer with source metadata, no backend errors.
- Client disconnect during `/chat`: request completed without backend errors.
- LongCat judge through the wrapper with no caller conversation scope:
  succeeded (8 characters, 10.8 s) after the session-binding fix.
- Earlier direct calls without `x-opencode-session` were rejected with
  `MissingSessionID`; the chat path already bound a scope, and the judge wrapper
  now does too.

## Recorded limits

- No quality score, baseline, or clinical claim is inferred from the smoke.
- Structured/tool output on the live Go route remains unverified; the adapter
  stays fail-closed for unsupported structured modes.
- The 16,384-token judge cap, judge latency/usage accounting, and all DeepEval
  metric prompts were not exercised live.
- A separate manual task-cancellation harness that closed the pydantic-ai stream
  from an outer task emitted pydantic-ai 2.31 teardown warnings. The actual ASGI
  `/chat` disconnect path did not log errors; clean provider-side billing stop is
  still not claimed.
- Local Docker preview remains blocked on this session’s stale `docker` group
  membership. The dev-server `/chat` path is verified; the Compose/Caddy path is
  still to be rebuilt after the session restart.

## Local-only artifacts

`.env.demo.local` is gitignored, mode 600, and now contains the OpenCode Go and
DashScope keys for the local preview, plus the MiMo/LongCat tuple. No secrets were
printed or committed.
