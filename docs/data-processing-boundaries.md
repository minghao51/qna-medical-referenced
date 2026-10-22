# Data Processing Boundaries

Reference for what this repository stores, where it flows, who can access it, how long it
lives, and where third parties are involved. Written for the P3-B boundary task; it
describes **actual behavior verified in the working tree sources** and the
**approved-but-unconfigured** hosted-export policy. It is not an approved retention
schedule — decision **D15** (explicit durations, access, and deletion policy) remains open.

Related: [anonymous-sessions.md](./anonymous-sessions.md),
[configuration.md](./configuration.md),
[public-app-deployment.md](./public-app-deployment.md),
`docs/plans/migration/decisions.md` (D02, D06, D10, D15).

## Non-negotiable boundary statements

- **No automatic PHI scrubbing exists.** No module classifies, redacts, or anonymizes
  patient-identifying content. The only content checks are bounded, allowlisted telemetry
  span attributes plus narrow regex canaries that are explicitly *"defense-in-depth for
  known test markers, not a general secret detector or a PHI-classification mechanism"*
  (`src/infra/telemetry.py`, `_FORBIDDEN_CONTENT_CANARIES`). `MAX_MESSAGE_LENGTH`
  truncation is a cost/token limit, not scrubbing (`config/settings.yaml`).
- **Permitted inputs are public/synthetic only (D02).** The ingestion corpus is public
  clinical-guideline web/PDF sources plus a local reference CSV
  (`config/sources.yaml`, `docs/data/sources.md`). Real and de-identified patient cases
  are out of scope for models, artifacts, and telemetry.
- **Hashing is not anonymization.** SHA-256 run identities, corpus/content hashes, review
  manifest attestations, and the HMAC-SHA256 session-cookie signature bind or authenticate
  content and sessions; none of them removes identifying content from stored data
  (`src/evals/artifacts.py`, `src/app/session.py`,
  `src/evals/assessment/retrieval_eval.py`).
- **Metadata allowlists are not global DLP.** The telemetry attribute allowlist
  (`_span_attributes`, fixed enum metadata and counts only) constrains *telemetry spans
  only*. Chat bodies, history, artifacts, caches, and provider payloads are unaffected.
- **No scheduled erasure exists for durable stores.** The only automatic expiry of
  durable data is lazy TTL pruning of chat history on read/write, plus a sliding cleanup
  of rate-limit events on each limiter check. Nothing deletes artifacts, caches, backups,
  or hosted copies automatically. Ephemeral in-memory state is different and expires on
  its own: the W&B history cache drops entries on lookup after
  `wandb_cache_ttl_seconds` (default 60 s) and evicts beyond 256 entries
  (`src/experiments/wandb_history.py`), and the embedding cache is a 512-entry in-memory
  LRU (`src/ingestion/indexing/embedding.py`) — these evictions leave nothing durable.

## Boundary matrix

| # | Store / flow | Content | Access | Retention & deletion (actual behavior) | Third-party boundary |
|---|---|---|---|---|---|
| 1 | Chat session cookie `chat_session_id` (`src/app/session.py`) | Server-generated random session ID + HMAC-SHA256 signature | One browser; `HttpOnly`, `SameSite=Lax`, `Secure` outside development | Cookie `max_age` default 2592000 s / 30 days (`CHAT_SESSION_COOKIE_MAX_AGE_SECONDS`). Cookie expiry is **not** deletion of the stored history (row 2). `DELETE /history` clears the record and rotates the cookie (`src/app/routes/history.py`) — but only on success: while a chat turn is active for the session, the store's turn guard rejects the clear with **409 `chat_session_busy`** (`src/infra/storage/file_chat_history_store.py`), in which case nothing is cleared and the cookie is **not** rotated; retry after the turn ends and require success | None |
| 2 | Chat history file `data/chat_history.json` (`src/infra/storage/file_chat_history_store.py`, `src/config/paths.py`) | Full message text per anonymous session: `role`, `content`, `timestamp`; schema v2; per-session `updated_at`; last 100 messages per session (`chat_history_max_messages_per_session`) | Server-side only; keyed by the cookie-bound session ID; not exposed cross-session; single-instance (no shared storage) | **Lazy TTL pruning** during `get_history`/save only (`_prune_expired_sessions`; `CHAT_HISTORY_TTL_SECONDS` default 2592000 s). TTL `<= 0` disables pruning. No background/scheduled deletion; an idle file is never pruned. `DELETE /history` pops one session. Atomic temp-file replacement writes; corrupt files are copied to `chat_history.json.corrupt.<epoch>` backups that **no TTL or DELETE removes** | None (file stays on the host; Docker bind-mounts `./data:/app/data`) |
| 3 | Anonymous browser cookie `anon_browser_id` (`src/app/middleware/rate_limit.py`) | Random token, no account link | One browser; `HttpOnly` | `max_age` 1 year; exists only to key anonymous `/chat` rate limiting | None |
| 4 | Rate-limit events `data/rate_limits.db` (SQLite, same file) | Event rows: rate key + timestamp. Keys embed **client IP** (`ip:<ip>`), or IP + browser token (`anon-chat:<ip>:<token>`), or API-key ID (`auth:<id>`) | Server-side only | Sliding cleanup deletes events older than 2× the 60 s window, but only when a limiter check runs (lazy). The DB file itself persists indefinitely | None |
| 5 | Application logs (`src/app/logging.py`) | stderr/stdout only — no log files are written by the app. Structured JSON events: generated `request_id`, HTTP method, route path template, status, latency, auth key ID; the app's HTTP/chat *route* failure logs carry fixed messages without session IDs, prompt content, or SDK exception text. **That content-free property does not certify all loggers**. The formerly query/exception-bearing HyDE paths in `src/rag/hyde.py` and `src/rag/query_expansion.py` now emit fixed success/failure events with numeric counts only; dedicated canary tests cover those owned paths. This is not a global logging or third-party SDK privacy guarantee | Whoever reads the process/console/container logs (Docker captures stdout) | Whatever the surrounding runtime retains — the app sets **no** log retention and makes no cleanup promise | A log shipper, if the operator adds one (none is configured here) |
| 6 | Browser chat state incl. PipelineTrace (`frontend/src/routes/+page.svelte`, `src/rag/trace_models.py`, `src/usecases/chat.py`) | Chat transcript and, when `include_pipeline=true` (frontend default on), the full `PipelineTrace` in the terminal SSE `done` event: **raw query text**, expanded queries, **retrieved chunk content**, context preview, timings, model name. Rendered by `PipelinePanel.svelte` | The one browser that made the request; held in Svelte `$state` (memory). **No `localStorage`/`sessionStorage` use anywhere in `frontend/src`** — lost on reload; re-fetched server history excludes traces | Nothing persists client-side; closing/refreshing the tab discards it. Server-side history (row 2) does not contain traces | None (unless the operator fronts the app with a proxy/CDN that logs response bodies — out of app scope) |
| 7 | Evaluation reports & artifacts `data/evals/<run>/` (`src/evals/artifacts.py`, `src/evals/assessment/orchestrator.py`) | `manifest.json` (config, git/input provenance, identity hashes, `review_manifest_sha256`), `summary.json`, step metrics, `retrieval_dataset.json`, `retrieval_results.jsonl` — rows contain the **raw query text and retrieved chunk content**, `l6_answer_quality.jsonl` (query, answer, sources, trace), `telemetry_metadata.json` (metadata-only span dump plus `usage_summary` token/counts) | Local filesystem; JSON served via `/evaluation/*`, which requires `X-API-Key` **only when API-key records are configured** — the auth middleware admits requests anonymously when no records are loaded (`src/app/middleware/auth.py:69-71`), and development mode is explicitly keyless (`src/app/security.py:217-222`) | **No TTL, no automatic cleanup, ever.** Deleting is manual; D10 authorizes no bulk deletion. Gitignored (`data/`), so the repo carries no copies — host/filesystem backups may | W&B raw artifact export only if an experiment sets `tracking.wandb.log_artifacts: true` (row 14); hosted telemetry never receives artifacts |
| 8 | Review manifests (operator-supplied path; `src/evals/assessment/orchestrator.py`, `retrieval_eval.py`, `review_manifest_tool.py`) | Schema-v1 JSON binding review labels to frozen dataset/corpus content via SHA-256 hashes and optional attestations. Run artifacts record only `review_manifest_sha256`, not the manifest | Operator-managed local file (read bound: 64 MiB); verification yields fixed statuses (`manifest_asserted_not_authenticated`, `manifest_hash_verified_not_identity_authenticated`); `reviewed_evidence_eligible` stays false until a recorded authority's manifest verifies (D07-ext) | Never modified or deleted by the app; lifetime is entirely operator-owned | None |
| 9 | Evaluation caches `data/evals/cache/<ns>/` and per-run `cache/` (`src/evals/assessment/answer_eval.py`, `settings.deepeval.*`) | **Content-bearing**: `retrieval_cache.json` (query, full context, sources, trace), `generation_cache.json` (query, answer), `metric_cache.json`. Enabled by default (`deepeval_answer_cache_enabled`/`metric_cache_enabled`) | Local filesystem | No TTL, no eviction, no automatic cleanup | Judge/generation providers are called only on cache misses |
| 10 | Vector index `data/chroma/` (local default) or remote Chroma server + in-process caches (`src/ingestion/indexing/store.py`, `embedding.py`) | ChromaDB holds **corpus chunk text, embeddings, metadata** for the public corpus — local by default (`PersistentClient` at `data/chroma/`, `chroma.sqlite3` + collection dirs); when `storage.chroma_server_host` is set the client is `chromadb.HttpClient` and the same content resides on that remote server instead (`src/ingestion/indexing/store.py`); BM25 index and document mirrors are in-memory only; embedding LRU cache (512 entries) is in-memory only | Server-side; the read-only fixed index is shared by chat/evals | No TTL. Manual deletion = destructive re-ingestion (index loss requires rebuilding). In-memory caches vanish on restart | Embedding API calls send query/chunk text to the embedding provider (row 13) |
| 11 | Explicit telemetry (`src/infra/telemetry.py`, `TelemetryConfig` in `src/config/settings.py`) | Manual, allowlisted OTel spans: operation/stage/route enums, generated UUID/identifier correlation IDs, counts, timings, model IDs, error-code enums, token counts. **Metadata-only spans — modes `disabled`/`local`/`hosted_metadata` — carry no message bodies, prompts, raw exceptions, or source IDs**; `record_exception=False`; automatic SDK capture stays off. This property is scoped to metadata-only spans, not categorical over all modes: in `approved_public_synthetic_content` mode (explicit `content_approved=true`), `record_case_content` (`src/infra/telemetry.py:796-850`) attaches bounded `content.input`/`content.output` span attributes (public/synthetic case fields, consented + reviewed, ≤2048 chars per input/output field, canary-checked). Those content spans are retained **locally** in the bounded in-memory exporter (ring below) even when `export_enabled=false`; sending them to a host is a separate, optional, explicit step (row 12). Local mode keeps a bounded memory ring of spans — default 256, configurable via `local_span_capacity` (1–4096) — that is never persisted (except the metadata-only `telemetry_metadata.json` dump, row 7) | Default `mode="disabled"` (no tracer at all). `local` keeps spans in-process. `hosted_metadata` exports to the configured region host only; `approved_public_synthetic_content` additionally records the approved case content described in the Content cell | Nothing written to disk by default; in-memory ring is bounded and dies with the process. Hosted retention would be the configured `retention_days` (row 12) | **Hosted export is configured-only**: requires explicit token + HTTPS endpoint + approvals; fails closed when any of the eight residual header/certificate/client-certificate/client-key variables enumerated in `_RESIDUAL_OTLP_ENV_VARS` (`src/infra/telemetry.py:127-136`: `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_EXPORTER_OTLP_TRACES_HEADERS`, `OTEL_EXPORTER_OTLP_CERTIFICATE`, `OTEL_EXPORTER_OTLP_TRACES_CERTIFICATE`, `OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE`, `OTEL_EXPORTER_OTLP_TRACES_CLIENT_CERTIFICATE`, `OTEL_EXPORTER_OTLP_CLIENT_KEY`, `OTEL_EXPORTER_OTLP_TRACES_CLIENT_KEY`) is present — a presence-only check at hosted-construction time (`src/infra/telemetry.py:507-509`); the environment is never unset or sanitized; exporter failure logs are rewritten to a fixed message. **No export has been performed** |
| 12 | Hosted Logfire destination (policy, not an implementation fact) | Would receive the row-11 metadata spans; case content only in `approved_public_synthetic_content` mode after explicit content approval (public/synthetic, consented, reviewed, ≤2048 chars **per input/output field, not combined** — `record_case_content`, `_MAX_CONTENT_CHARS`, canary-checked) | Approved policy: dedicated project, **minimal named access** | Approved policy: **30-day retention** — vendor enforcement not independently verified; no invented guarantee is claimed | **Approved but unconfigured.** Per decisions.md (2026-10-20): dedicated project, 30-day retention, minimal named access, metadata-only smoke first, content mode only after P3-C canaries. Destination/region/access setup and any hosted smoke are **separately gated permission steps; nothing has been configured or uploaded** |
| 13 | Provider API calls (`src/infra/llm/qwen_client.py`, `gemini_client.py`, `litellm_client.py`, `src/ingestion/indexing/embedding.py`, `src/evals/assessment/answer_eval.py`) | Generation sends system+user prompts containing the **current message, prior conversation history, and retrieved public-corpus context**; embeddings send query/chunk text; HyPE/enrichment send corpus text at index time; LLM-as-judge calls send query/answer/context (`LLMTestCase`) | Providers named in config (DashScope/Qwen default; Gemini, LiteLLM/OpenRouter, OpenCode Go routes per decisions D03/D17) | **Governed by each provider's terms, not by this repository.** No retention or deletion guarantee is claimed or verifiable here; local deletion does not reach provider copies | Inherent: this content leaves the machine on every chat/eval/index call. DeepEval's own product telemetry is force-disabled (`DEEPEVAL_TELEMETRY_OPT_OUT=1` before import, `src/evals/deepeval_models.py`); the SDK may still write its own local files (gitignored `.deepeval/`), which are not audited here |
| 14 | Weights & Biases (historical paths, `src/experiments/wandb_tracking.py`, `wandb_history.py`, `scripts/cleanup_wandb_runs.py`) | Opt-in per experiment (`tracking.wandb.enabled`): numeric aggregate metrics only (verbosity-tiered); manifest and user-authored experiment fields are not forwarded. Legacy **raw artifact export runs only with `log_artifacts: true`** and warns it is not content-policy approval | Hosted W&B project/entity named in experiment config; history reads via API with a 60 s in-process cache | Hosted W&B run/artifact retention is vendor-side — no guarantee claimed. `scripts/cleanup_wandb_runs.py` deletes runs via API (dry-run default). Local `wandb/` SDK dir is gitignored. D10 keeps W&B history until the Phase 4 consolidation | The vendor-operated hosted W&B service receives the logged aggregates; D06 retains existing history during transition |
| 15 | Secrets/config (`src/app/security.py`, `src/config/settings.py`, `.env*`) | Provider keys, session-signing secret, W&B/telemetry tokens as `SecretStr`; app API-key material (`ApiConfig.api_keys`/`api_keys_json`) is held as **plain strings, not `SecretStr`** (`src/config/settings.py`) — known gap flagged for a separate code-repair task; dotenvx-encrypted `.env` | Server-side; authed callers present `X-API-Key`; production startup requires keys and a ≥32-byte signing secret | Operator-managed rotation; nothing here deletes or exports them | Provider APIs receive keys as auth credentials on each call |

## What deletion and TTL do **not** do

Verified in code; stated to prevent false assurance:

- **`DELETE /history` is narrow.** It pops the *current cookie-bound session* from
  `data/chat_history.json` and rotates the cookie (`src/app/routes/history.py`) — but only
  on success: an active chat turn for the same session makes the delete fail with
  **409 `chat_session_busy`** (store turn guard), leaving the record and cookie untouched;
  retry after the turn ends and require success. It does
  not touch other sessions, `chat_history.json.corrupt.<epoch>` backups, provider copies
  of prompts already sent, console logs, evaluation artifacts (row 7), eval caches
  (row 9), rate-limit events (row 4), or any hosted W&B/Logfire copy.
- **TTL is lazy pruning, not scheduled erasure.** `_prune_expired_sessions` runs only
  inside history reads and writes. A session older than `CHAT_HISTORY_TTL_SECONDS`
  disappears at the *next* read/write — there is no background job, no boot-time sweep,
  and nothing runs while the server is down. `TTL <= 0` disables pruning entirely.
- **Cookie lifetime is not persisted deletion.** `CHAT_SESSION_COOKIE_MAX_AGE_SECONDS`
  (30 days) only stops the browser presenting the cookie; the server-side record lives
  until TTL pruning or `DELETE /history`. Presenting a valid cookie after its session was
  pruned simply receives empty history — pruning is keyed by the stored `updated_at`, not
  by cookie state.
- **No cascade into artifacts/caches/backups/hosted copies.** Chat history TTL/DELETE and
  evaluation re-runs never propagate to rows 7–14. Hashes recorded in artifacts are
  integrity/correlation bindings, not deletion handles: no code path deletes a provider,
  Logfire, or W&B copy because a local record was removed.
- **No automatic cleanup promises.** The repository ships no retention job, no garbage
  collector, and no backup rotation. Every durable store above is deleted only by an
  explicit operator action.

## Operator checklist (manual, permissioned; no step here runs automatically)

1. **Inventory** — enumerate durable stores before deciding anything:
   `ls data/` (chat history, `rate_limits.db`, `chroma/`, `evals/`, caches), search for
   `data/chat_history.json.corrupt.*` backups, list `data/evals/*/` run dirs and
   `data/evals/cache/` namespaces, and check host-level backups of the `data/` volume and
   Docker bind mount. Read-only inspection only; treat chat/artifact/caches files as
   content-bearing.
2. **Access review** — confirm who can read the host `data/` directory and console logs;
   confirm `/evaluation/*` callers hold `X-API-Key` **when key records are configured** —
   with none configured the middleware admits anonymous access (`src/app/middleware/auth.py:69-71`),
   so eval artifacts are then readable without a key (development mode is keyless by
   design, `src/app/security.py:217-222`); list named members of the Logfire project (once created — currently none)
   and of the W&B entity/project; verify that none of the residual env vars enumerated
   in `_RESIDUAL_OTLP_ENV_VARS` (`src/infra/telemetry.py:127-136` — the eight
   `OTEL_EXPORTER_OTLP` header/certificate/client-certificate/client-key variables;
   the code guard is a fail-closed presence check at `src/infra/telemetry.py:507-509`,
   not an environment cleanup) is present before ever enabling hosted export.
3. **Retention decision (D15, open)** — record explicit durations for chat history,
   artifacts, caches, corrupt-file backups, traces, and remote artifacts. Today's values
   are code defaults or lazy mechanics, not an approved policy: chat TTL/cookie 30 days,
   browser cookie 1 year, rate-limit events ≤120 s sliding, artifacts/caches/backups
   indefinite.
4. **Permissioned deletion** — stop the server first to avoid write races, then per
   target: chat history (delete sessions or the file; also delete `.corrupt.*` backups),
   rate-limit DB (delete rows or the file while stopped), eval artifacts/caches (delete
   run dirs / cache namespaces), vector index (delete `data/chroma/` only with a plan to
   re-ingest), W&B runs (`scripts/cleanup_wandb_runs.py`, dry-run default), Logfire
   (project-scoped deletion in the Logfire UI — no application code path exists), provider
   accounts (per-provider consoles; out of app scope), and local/host filesystem backups
   and Docker volumes (explicitly enumerated, or deletion is incomplete).
5. **Third-party copies** — remember that provider-side prompt/response copies, any
   future hosted Logfire spans, and existing W&B history each need their own
   vendor-specific deletion/retention action; nothing in this repository performs or
   promises it.

## Status of the hosted-export policy (approved ≠ configured)

Recorded owner policy (decisions.md, 2026-10-20): dedicated Logfire project, 30-day
retention, minimal named access, metadata-only smoke first; public/synthetic case-content
mode only after the P3-C canaries pass. The code implements the enforcement side
(`TelemetryConfig` validators, explicit OTLP exporter construction, a fail-closed
presence check that refuses to construct the hosted exporter while any variable in
`_RESIDUAL_OTLP_ENV_VARS` (`src/infra/telemetry.py:127-136`) is set — the environment
is never unset or sanitized (`src/infra/telemetry.py:507-509`), canary tests under
`tests/integration/telemetry/`), but the
destination, region, access list, retention value, and token are **not configured**, the
hosted smoke has **not** been run, and **no export has been performed**. Setup, region
selection, access grants, and the smoke test each remain separate permissioned steps.
