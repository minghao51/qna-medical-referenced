# Environment, credentials, and live-run authorization

**Status:** Planning guide. No secrets have been requested, read, created, or validated by this documentation task.
**Decision dependencies:** D02/D03/D04/D06/D07/D14/D15/D16 in the [decision register](decisions.md).

**Current continuation (2026-10-20):** See the [evaluation-tracing handoff](20261020-evaluation-tracing-handoff.md) for opt-in local run/case-correlated stage/attempt traces, supported-launcher log repairs, isolated verification and scoped review. Whole phases, authenticated review authority, full budget admission and hosted/live/container exits remain open.

**Previous integration checkpoint (2026-10-19):** The consolidated remaining Phases 1–3 plan and narrow dependency/browser provisioning are approved. See the [integration handoff](20261019-phases-1-3-integration-handoff.md) for current code, isolated gates, exact dependency changes, review repairs, and open exits. Earlier no-install/browser-blocked statements below describe their historical slices. **Whole phases remain incomplete; no live/model/corpus/export/default-switch/Phase 4 permission is inferred.**

## Current owner approval — 2026-10-16

The owner selected corrected **`baseline`** for D17 and approved installing the frozen-lock frontend dependencies and checking/installing packages in the bounded Logfire compatibility spike. Package-registry access is allowed for that work; no actual model, embedder, reranker asset, hosted telemetry, corpus download or live benchmark is authorized. Exact Logfire/API/lock effects must be documented before adoption. The selected benchmark profile does not silently change application provider/harness/runtime-profile defaults, and generation/judge request settings still need an explicit matched snapshot.

The documentation-only pause is historical. The owner resumed the approved bounded batch in the next thread; see the [resume handoff](20261016-phases-1-3-resume-handoff.md). Dedicated session signing and provider/worker guards are implemented. Frontend frozen-lock dependencies were installed; project dependency locks and application-provider defaults remain unchanged. Browser execution remains blocked; both Luna review findings are repaired in the owner-approved [follow-up](20261017-review-repair-handoff.md), with no actionable re-review findings. Browser/runtime provisioning remains separately gated; no package/live/export permissions were extended. The [Logfire compatibility report](20261016-logfire-compatibility-spike.md) records a network-denied 5.2.0 SDK probe and OTel/protobuf-major dependency effects; separate review/approval is required before project-lock adoption or tracing.

**2026-10-17 SDK slice:** The owner approved bounded [P1-C3a](20261017-p1-c3a-handoff.md) wrapper retries/public cleanup, then explicitly approved its [Gemini HTTPX constructor/lifecycle fix](20261017-gemini-httpx-fix-handoff.md). That generation-adapter finding is repaired and re-reviewed; the SDK transport choice was authorized, not silently enabled. No SDK upgrade, application credentials, live calls, exports, browser/model assets or provider/model/profile switch was authorized. Direct judge SDK compatibility remains separate.

## 1. Do we need `.env` or keys now?

**No** for planning, baseline defect fixes, deterministic regression tests, synthetic lifecycle tests, metric/cache tests, and fake-model Pydantic AI/Pydantic Evals integration.

**Yes, later**, for the particular live operations you explicitly approve. Having a key available does not authorize using it, choosing a model, exporting content, or spending an unspecified amount.

| Operation | External access required? | Required credential/access |
|---|---|---|
| Edit these plans or answer decisions | No | None |
| Run isolated fake-provider/fake-embedding tests | No | None; dummy test values must never reach real services |
| Install/resolve approved new dependencies | Package-registry network, normally no paid model calls | Normal package access; dependency change approval |
| Read an existing local index without query embedding | No model call by itself | Local file access; no content dump needed |
| Real semantic retrieval using the current embedder | Yes on query-embedding cache miss | DashScope embedding access, even if generation uses Gemini/OpenRouter |
| Download/rebuild the real corpus/index | Source network; paid embeddings/enrichment if enabled | Approved source inventory, embedding key, any enabled enrichment provider, separate storage |
| Existing Qwen generation | Yes | DashScope model access in the selected region |
| Existing Gemini generation | Yes | Google API key with access to the exact configured model |
| Existing LiteLLM/OpenRouter generation | Yes | OpenRouter key, or the separately configured upstream gateway/provider credential |
| Selected OpenCode Go route | Yes | Console-issued API key, model access, honest `User-Agent` and stable `x-opencode-session`; owner reports eligibility checked, account/capabilities still need validation |
| Direct OpenAI/Anthropic/new provider adapter | Yes | Provider-specific key/model entitlement after the adapter's settings support is implemented |
| Judge already-saved outputs | Yes if using a live judge | Independently selected judge credential; no unrelated generation key requirement |
| Pydantic AI test/function model | No | None |
| Pydantic Evals deterministic/custom evaluators | No | None |
| Local/disabled Logfire tracing | No hosted export | No hosted Logfire account/token required |
| Hosted Logfire traces/eval results | Yes | Write/export token, approved project/region/access/retention/content policy |
| Optional Logfire-hosted dataset management | Yes | Separate API key with `project:read_datasets` and/or `project:write_datasets`; experimental SDK/version review and explicit dataset-content permission |
| W&B hosted aggregates/artifacts | Yes | Approved account/project access; separate permission for content-bearing artifacts |
| Private production-mode server | Not necessarily external model calls during preflight | Application auth records plus `APP__API__SESSION_SIGNING_SECRET` |

[P1-B](20261015-p1-b-handoff.md) retains **DashScope/Qwen for index-time HyPE, keywords, and summaries**, independently of the selected generation provider. Those enabled build operations need DashScope model access; turning on Gemini/Go generation does not migrate them. Zero sampling now generates nothing, while positive sampling still uses existing finite configured limits. Next-build flags do not prove that a loaded index contains those features. D17 now selects corrected `baseline` for comparison capture. The existing configured runtime profile string is unchanged by that decision; corrected `baseline_cross_encoder` remains an optional, unselected condition that really reranks and requires separately approved provisioning before a real run. Do not launch a benchmark as a download test.

An existing vector index does not eliminate live query-embedding costs. A deterministic fake embedder proves wiring, not real semantic quality. Downloads of NLTK/reranker assets are network operations even when they are not paid LLM requests.

## 2. Current secret/configuration contract

The actual settings implementation uses nested environment overrides (`APP__` prefix and `__` delimiter), YAML defaults, and explicit initialization overrides. Several older docs still describe flat names or automatic `.env` loading incorrectly. Do not assume those instructions are authoritative until Phase 1 aligns them.

The currently declared secret fields are:

| Environment variable | Current purpose |
|---|---|
| `APP__LLM__DASHSCOPE_API_KEY` | Existing DashScope generation/embedding and provider-bound roles |
| `APP__LLM__GEMINI_API_KEY` | Existing Gemini client/judge |
| `APP__LLM__OPENROUTER_API_KEY` | Existing LiteLLM/OpenRouter route |
| `APP__WANDB__WANDB_API_KEY` | Optional W&B integration |
| `APP__API__API_KEYS` or `APP__API__API_KEYS_JSON` | Application caller authentication; not a model-provider credential |
| `APP__API__SESSION_SIGNING_SECRET` | Dedicated cookie HMAC secret, independent of caller/provider keys; required outside development |

`config/settings.yaml` currently selects Gemini while the Python default is Qwen. A supplied DashScope key alone therefore does not guarantee local chat startup. The current `.env.example` has an active DashScope placeholder and a commented Gemini field: copying it unchanged is not a complete working setup for the selected route. Phase P1-D must make the example provider-conditional after the route/profile decision; this documentation-only change intentionally does not select a provider or modify the example. The current generation selector is `APP__LLM__PROVIDER`; exact provider/profile/model configuration is a non-secret decision, not something to infer from installed keys.

The app's settings declaration does not currently configure a project `.env` file as `env_file`; use explicit environment injection, such as the existing dotenvx wrapper. Do not silently add a second secret-loading scheme as part of this plan.

The bounded [P2/P3 foundation](20261016-p2-p3-foundation-handoff.md) adds the non-secret `APP__LLM__JUDGE_PROVIDER` selector (`qwen`, `gemini`, `litellm`); omission inherits generation provider for compatibility. Judges use the existing selected provider's nested credential above. This is not a new judge-account secret or permission to run live evaluation. Answer-suite activation is explicit, never inferred from installed keys.

### Session signing and remaining future settings

`APP__API__SESSION_SIGNING_SECRET` must be independently generated and contain at least 32 UTF-8 bytes after trimming outer whitespace. A missing secret is allowed only in development, where a process-random fallback invalidates cookies on restart; an explicitly weak secret is rejected in every mode. Rotation and the move away from the old API-key/environment-derived signer invalidate existing cookies without deleting/migrating historical messages. There is no insecure legacy-signature fallback. The production CLI rejects worker counts other than one; independent processes/store instances sharing file history remain unsupported. See [local constraints](../../local-workflows.md#private-lab-production-mode-constraints).

OpenCode/direct-provider fields, additional judge-account secret settings, telemetry configuration, and adapter/experiment selectors require further Phase 1–4 implementation. Their eventual names must be added to `.env.example` and configuration docs when supported. Do not assume a vendor SDK's `OPENAI_API_KEY` or `LOGFIRE_TOKEN` environment convention is already an application setting or overrides the app's explicit client credentials.

Pydantic AI/Pydantic Evals do not require a special paid framework key to run locally. An optional gateway account is a separate provider choice, not mandatory for adopting the framework.

## 3. Secret storage and safe handling

**Recommended default:** Keep the existing dotenvx approach unless there is a concrete reason to replace it. Secret management is not the focus of this migration.

- Store provider credentials locally through your approved secret-management workflow or inject them through a secret manager/CI secret store.
- Use nested secret names supported by the selected implementation; keep model IDs, endpoints/regions, and ordinary configuration in non-secret settings.
- Never paste values into chat, commit plaintext, put tokens in experiment YAML, embed them in browser code, or print whole settings/environment dictionaries for debugging.
- Do not commit `.env.keys`, backups, decrypted output, credential files, or generated content artifacts. Verify ignore rules before creating files.
- Avoid exposing secret arguments through shell history/process listings. Use your secret tool's approved input workflow; do not ask the coding agent to echo/decrypt values for confirmation.
- Existing `.env` ciphertext, if used, still requires access control; do not change its tracked/ignored policy without approval. The current repository ignores `.env` and most `.env.*` files except `.env.example`.
- Use separate development/evaluation and production credentials where available. Grant minimum scopes and apply provider-side spend limits or prepaid balances.
- Treat Logfire/W&B tokens as export permissions with their own scope. Content authorization is separate from possession of an export token.

Pi/Codex/subscription access used for the review scouts is **not automatically a supported application-provider credential or permission to extract/reuse session tokens**. Decide an explicit supported route for the application. Do not repurpose agent OAuth credentials as part of `.env` setup.

## 4. What the owner should provide before live validation

Provide metadata, not secret values:

1. D02 is settled: public/synthetic only. Confirm the exact approved smoke dataset/cases.
2. OpenCode Go account profile/tier, initial model ID and endpoint/region. D03 records owner-confirmed eligibility; technical checks still cover account/model access, session headers, capabilities, and usage reporting.
3. Which supported secret names are configured locally, confirmed by you or a value-free readiness check.
4. The independent judge choice and approved judge request settings.
5. D04 is USD 20/month for all incremental project charges (generation/judges/embeddings/enrichment/metered telemetry); existing Go subscription separate, no mandatory per-run dollar cap. Approve finite case/request/token/concurrency/time settings and acknowledge exact Go account billing requires Console reconciliation unless a supported API is verified.
6. D06/D10 permit Logfire consolidation and allowlisted public/synthetic input/output export after local validation. Provide destination/access/retention; no patient data, secrets, or unrelated uploads.
7. Whether index rebuilds, remote corpus downloads, reranker model downloads, or W&B export are permitted.
8. The exact command/run configuration or bounded experiment plan approved for execution.

Do not request every provider's key up front. Start with one working existing route plus the selected comparison route; keep the embedder fixed unless D11 changes that scope.

### Selected OpenCode Go route: owner confirmation and client headers

The [official Go docs](https://opencode.ai/docs/go/) inspected on 2026-10-15 list `deepseek-v4.1-flash` and `mimo-v2.6-flash`, a Console-issued key, and OpenAI-compatible Chat Completions. They also describe Go as designed for coding agents and say clients should send typical coding-agent traffic. The owner subsequently reports checking this workload's eligibility and selected Go. Record that as owner confirmation, not an independently provider-tested guarantee; account/model access and capabilities still need a bounded live smoke. Do not disguise traffic or silently switch to another route on rejection.

The documented client settings are:

- An honest application-specific `User-Agent`, for example `qna-medical-referenced/0.1`, rather than a generic SDK name or impersonating OpenCode.
- `x-opencode-session`: an opaque session ID stable for one conversation, including its retries/turns. Separate unrelated case/variant/judge conversations, and do not use raw cookies, patient identifiers, secrets, or the current agent's session credentials.
- Inject session headers per request with the smallest supported client/adapter hook; never mutate shared default headers across concurrent conversations. Test text, streaming, and structured paths with fake transports before live validation. Header spelling is `x-opencode-session`, not `opencode-x`.

| Documented route | SDK base URL | Full Chat Completions URL | Billing/permission distinction |
|---|---|---|---|
| Go subscription | `https://opencode.ai/inference/go/v1` | `https://opencode.ai/inference/go/v1/chat/completions` | Subscription/included limits; owner-confirmed workload eligibility, technical smoke pending |
| Console pay-as-you-go | `https://opencode.ai/inference/v1` | `https://opencode.ai/inference/v1/chat/completions` | Separate credits/metered application route; exact model/access/data policy must be approved |

These are documentation findings, not implemented app settings or authenticated smoke results. Older search snippets referenced `/zen/go/v1`; use the current officially documented route only after rechecking at implementation. Do not pass a full `/chat/completions` URL as an SDK base URL. Neither streaming behavior nor native JSON-schema/tool support is proven merely by endpoint compatibility.

The [Console model list](https://opencode.ai/docs/zen/) includes route-specific variants such as `mimo-v2.6-flash-free`. A `-free` variant is not the Go model ID and can have data-use conditions unsuitable for private inputs. Do not silently substitute it. The owner's public/synthetic-only policy does not authorize a silent model substitution or different provider training terms; D10's Logfire case-export permission is destination-specific.

### Budget and hosting follow-up

The owner clarified USD 20/month for all incremental project charges: generation, judges, embeddings, expansion/enrichment, and metered telemetry. Existing Go subscription fees are separate; any new paid tier/subscription requires approval. Current Go docs express included usage limits using token-price values; quota depletion is not automatically an extra cash invoice. No automatic recharge/overage is authorized: confirm the Go Console **Use balance** option is off, since it can spill requests into paid credits after subscription limits. Go also has 5-hour/weekly/monthly allowances, so remaining monthly quota alone does not prove current request availability. Planned R15 tracking adds compact cost summaries to existing run manifests/logs, monthly totals, and manual subscription/console adjustments; cash/estimated usage, included quota, and unknowns stay distinct. No new billing database/request-event ledger is planned, nothing is implemented yet, and no cap is guaranteed. No supported programmatic Go account-level quota/billing endpoint has been verified: initially rely on reported tokens/nullable estimates and Console/manual reconciliation for exact remaining allowance, balance deductions, and invoices. Disclose missing usage and estimated-only records to the owner, rather than claim exact Go spending visibility.

Pydantic Evals can remain local/offline while Logfire becomes the approved primary UI. Its [documented integration](https://ai.pydantic.dev/evals/how-to/logfire-integration/) exports case inputs/outputs by default, independently of model-message instrumentation. D10 now explicitly permits allowlisted public/synthetic case inputs/outputs; verify the chosen project's content/access policy and both metadata-only and approved-content modes locally before exporting. Secret/patient-data canaries remain forbidden in both modes; wholesale HTTP-body/history/document capture is not approved. Keep versioned cases/prompts/configs and small reproducibility records even after a UI cutover; hosted trace retention is not a replacement for benchmark source control. [Hosted datasets are supported separately](https://pydantic.dev/docs/logfire/evaluate/evals-in-code/); their [experimental management SDK](https://pydantic.dev/docs/logfire/evaluate/datasets-sdk/) uses dataset-scoped API keys rather than a trace-export token. If adopted, freeze/export and hash the exact case snapshot for each run; editable hosted names alone are not reproducible dataset identity.

## 5. Live preflight and authorization contract

Phase 1/4 will implement a value-free preflight. Until then, do not document an invented command as if it already exists.

Before launching a live attempt, it must show:

- Explicit live-run opt-in, selected dataset/case count, harness/implementation, generator/judge/embedding roles, exact models, and sanitized regions/endpoints.
- Credential-name readiness only, not values/hashes/token lengths or complete environment dumps.
- Required extras/model assets and capability checks that do not themselves make paid requests unless explicitly authorized.
- Monthly cost summaries against the approved USD 20 accounting scope, plus a request/token/cost envelope including retries, tool loops, HyDE/enrichment, and judging. Unknown price/usage stays unknown; included quota is not extra cash spend.
- Provider concurrency, timeouts, request/token/tool limits, provider-side caps if available, and whether strict dollar limits are actually enforceable.
- Fresh/read-only index fingerprint, separate writable artifacts/cache/history paths, and export mode.
- Exact stop behavior for missing requirements, quota/rate limits, budget exhaustion, and interrupted runs.

A rejected or incomplete preflight must not fall back to another model/provider automatically. Benchmarks have fallback disabled unless the fallback behavior itself is the approved experiment.

## 6. Safe progression

1. **Offline regression:** no actual keys, network denied, fake models/embeddings, temporary data.
2. **Local telemetry canaries:** no hosted export, inspect serialized metadata for leaks.
3. **Tiny live provider smoke:** a small explicitly approved synthetic set on the selected route, with usage accounting and no automatic broad benchmark.
4. **Matched pilot:** fixed index/cases/judge/settings, each implementation isolated; content exports still off unless approved.
5. **Broader benchmark or hosted export:** separate authorization after inspecting pilot cost, completion, and data handling.
6. **Public deployment/default promotion:** separate security and product decision; passing a provider smoke is not approval.

No `.env` setup is needed to start offline work. The first-round decisions are recorded; only the remaining route/budget/export choices and bounded implementation approval are needed next, not a bundle of API keys.
