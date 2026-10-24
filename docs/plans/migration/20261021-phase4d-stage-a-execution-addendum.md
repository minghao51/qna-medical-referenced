# P4-D Stage A execution addendum — blocked pending harness approval

## Owner instruction

Following approval to prepare the [planning pack](20261021-phase4d-approvals-pack.md), the owner selected Go subscription quota only. The assistant stated the bounded interpretation: **Stage A only, at most $1 of included Go quota value, $0 incremental cash, no spillover/top-up**; the owner replied “proceed.” This does not authorize consuming all available quota, B/C, paid overage, downloads, hosted export or serving changes.

## Bounded proposed execution contract

- Generator: `mimo-v2.6-flash`, exactly `https://opencode.ai/inference/go/openai/v1`, both implementations. No substitution or fallback.
- Nine logical operations, sequential: text, stream and mid-stream cancellation per implementation; existing JSON-object structured output; adapter tool and native-json-schema structured output.
- Two synthetic prompts: “Reply with exactly: smoke ok” for text/structured testing; “Count from one to twenty, one number per line” for streaming/cancellation. Structured schema: one required string field `answer`, no additional properties. Exact assembled medical instructions/messages/schema must be frozen and hashed before execution; these short prompts alone are not the full request.
- Generation temperature 0.7; output limit 2048 per wire request; 30-second request timeout; 30-minute overall stop.
- Proposed **global admission cap: 12 outbound generation POST attempts** across all nine operations, counting transport retries and structured repair calls alike. Disable client transport retries for this tiny smoke (one total attempt); permit at most one structured repair call for each of the three structured operations. This is a proposal for the isolated harness, not a claim about current defaults.
- Proposed per-wire input cap: 4096 conservatively counted tokens including instructions, schema and any repair history. Total admitted input at most 49,152 tokens and declared output at most 24,576 tokens. An uncountable payload fails closed. Metering must account conservatively for model-specific tokenization and reasoning/hidden-token accounting; these bounds are not provider billing guarantees.
- Reserve quota against every admitted request before sending, including cancelled requests. Missing usage must retain its conservative reservation, never become zero. At $0.14/M input and $0.28/M output (historical P4-A reference only), those admitted bounds would be approximately $0.0138. **Current Go quota accounting must be confirmed before relying on this estimate**; list-price arithmetic is not proof of subscription consumption. Stop before the $1 allocation would be exceeded; if quota accounting cannot be bounded, do not run.

## Verified code constraints and required bounded harness slice

Static inspection only; no application imports or network were used.

- `src/infra/llm/qwen_client.py`: constructor binds both SDK clients to `dashscope_api_key` and shared `qwen_base_url`; requests hard-code temperature 0.7/output 2048. No Go-specific identity-header wiring is present. Avoid changing shared application settings or accidentally routing embeddings/judges to Go.
- `src/infra/llm/pydantic_ai_client.py`: identity headers are request-scoped; structured agents do not explicitly pin structured-validation retry count. Transport total attempts derive from `settings.retry.max_retries`. Existing defaults alone do not enforce the proposed global cap.
- Proposed implementation: an isolated manual smoke harness with an allowlisted exact route, explicit generation-only credential-source mapping for both clients, honest per-implementation User-Agent and opaque session headers, outbound request admission/counting, request-shape validation, conservative quota reservation, cancellation cleanup and sanitized local metadata reporting. No generation preflight bypass or CLI selector widening. Any temporary client configuration must be process-local and restored/closed; no persistent shared settings changes.
- Tests must deny live calls for both SDK paths, verify rejection before sending request 13, structured repair accounting, route/header rules, cancellation reservation and absence of secret/raw-session/body artifacts. Workers run no tests/imports/network; parent uses approved isolation and standing gates.

**The owner subsequently approved the bounded offline harness slice; it is now delivered and reviewed:** see the [offline handoff](20261021-phase4d-stage-a-offline-handoff.md). Its SDK path uses MockTransport with trusted synthetic handlers under OS isolation; CLI live execution remains unavailable. The 4096-byte payload bound and simulated reservations do not establish provider token/billing bounds. A live-capable runner and verified accounting still need a separately approved slice; no new framework abstraction is proposed.

## External confirmations required before live execution

Owner confirms, without sharing credentials or account screenshots containing secrets:

1. Account permits this workload/model/route, at least $1 of included quota remains, and all spillover/pay-as-you-go/auto-top-up are off.
2. Current Go quota valuation applicable to the admitted token limits, including any reasoning/hidden-token treatment, and no cash billing for these requests.
3. Credential can be supplied through the approved runtime secret source without reading `.env` or exposing its value. No key should be pasted into chat or artifacts.

After offline harness review/gates, present frozen messages/schema hashes, exact effective settings and numeric reservations, then obtain final stage-specific run confirmation. Stop on route/capability rejection, unknown quota accounting, missing safety confirmation or any unexpected charge; no fallback. B/C remain blocked as described in the pack.
