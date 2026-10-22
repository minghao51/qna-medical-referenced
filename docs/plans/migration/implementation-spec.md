# Implementation specification

**Status:** Proposed implementation requirements, updated for owner responses on 2026-10-15; see [decisions](decisions.md) for accepted choices and unresolved conditions. No code slice is approved by this document alone.
**Baseline:** `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`.
**Execution plan:** [phases](phases.md). **Credentials:** [environment guide](environment-and-credentials.md).
**Verified progress:** [P1-A1](20261015-p1-a1-handoff.md) async readiness; [P1-A2](20261015-p1-a2-handoff.md) off-loop serialized initialization/cooperative cancellation; [P1-A3](20261015-p1-a3-handoff.md) off-loop retrieval/native-async HyDE; [P1-A4](20261015-p1-a4-handoff.md) synthetic HTTP/SSE lifespan and app-owned cleanup; [P1-B](20261015-p1-b-handoff.md) effective retrieval options, next-build ingestion flags, diagnostics, and explicit CLI retrieval overrides; [P1-C1](20261015-p1-c1-handoff.md) stream-only bounded transient retry, public-stream ownership, and failed-generation history discard; [P1-C2](20261016-p1-c2-handoff.md) same-instance session admission, atomic completed-turn writes, and cancellation-safe ownership of admitted commit workers; [P1-C3a](20261017-p1-c3a-handoff.md) nonstream wrapper retry policy and cancellation-safe returned public-stream cleanup, with its generation-adapter transport finding resolved by the approved [Gemini HTTPX constructor/lifecycle fix](20261017-gemini-httpx-fix-handoff.md). P1-C/R03 remain incomplete. Other gates remain pending; the baseline-finding table remains historical to the inspected revision.

**P2/P3 offline follow-through:** The owner-approved [foundation handoff](20261016-p2-p3-foundation-handoff.md) records independent judge selection, explicit answer-suite activation, partial measurement/winner guards, and existing W&B/UI hardening. Full R05–R11/R15 and all phase exits remain pending; no Logfire tracing or new metric-formula certification is implied.

**Current integration (2026-10-19):** The remaining Phases 1–3 plan and narrow dependency/browser provisioning are approved. See the [current handoff](20261019-phases-1-3-integration-handoff.md) for implementation, verification and explicitly open exits; historical implementation-status notes below do not certify whole-phase completion.

## 1. Goals, non-goals, and invariants

### Goals

1. Repair the existing served RAG path and prove that requested features actually execute.
2. Make harness/provider experiments reproducible, interpretable, and bounded in cost.
3. Add end-to-end observability without making content export a prerequisite.
4. Compare the existing generation implementation with a Pydantic AI adapter under matched conditions.
5. Evaluate both implementations with shared Pydantic Evals tasks while preserving useful metric definitions and historical results; use the approved primary Logfire experiment UI rather than maintaining duplicate evaluation/dashboard stacks (D10), with bounded implementation/cutover approval.
6. Explore tool-driven behavior only after the control implementation and measurements are trustworthy.
7. Keep simple monthly usage/cost accounting against the owner's USD 20 ceiling; do not build a billing platform or claim hard spending enforcement.

### Non-goals

No vector database migration, replacement of Hamilton, package-wide DI framework, generalized plugin registry, durable multi-agent workflow engine, new public experiment-launch API, or default embedding change. Vision uploads, differential diagnosis, medication/dosing tools, and unrestricted web search are not included without D12 approval. This is not a clinical validation or certification program.

### Invariants

- `AGENTS.md` and the existing import-linter architecture remain binding.
- Server-owned dependencies are built/closed at the composition root; tests can substitute them explicitly.
- A transport/framework change and a behavior change are separately named experimental conditions.
- New behavior remains opt-in until its acceptance gate is approved and passed.
- Deterministic tests must work without real credentials or remote model access.
- Private research scope; public/synthetic data only. Reference-heavy engineering measurements do not establish clinical suitability; qualified medical review is not assumed.
- No secret values enter source, manifests, hashes, logs, frontend bundles, or review output.
- Historical artifacts are not rewritten to look as if they used new formulas, prompts, or schemas.

## 2. Verified baseline problems and ownership

Line references describe the inspected revision; implementers must re-check them before editing.

| Finding | Current evidence | Requirement / phase |
|---|---|---|
| Async retrieval invokes a sync-only initializer | `src/rag/runtime.py:314–323,456–474`; `src/rag/index.py:105–116` | R01 / 1 |
| Production profile retrieval options are not propagated | `src/rag/production_profile.py:53–62`; `src/rag/index.py:164–179` | R02 / 1 |
| Ingestion feature overrides disappear in factory normalization | `src/ingestion/indexing/factory.py:20–32`; `src/ingestion/pipeline.py:59–72` | R02 / 1 |
| Streams restart after partial emission | `src/infra/llm/qwen_client.py:126–166`; equivalent LiteLLM/Gemini paths | R03 / 1 |
| Model/cache and index identities are incomplete | `src/evals/assessment/answer_eval.py:64–81`; `src/evals/checks/l5_index.py:128–132`; `src/evals/assessment/reporting.py:29–35` | R06 / 2 |
| Missing answer metrics can bypass thresholds | `src/evals/assessment/answer_eval.py:428–430`; `src/evals/assessment/thresholds.py:78–80` | R07 / 2 |
| Source-match proxies and generated labels weaken relevance measurement | `src/evals/assessment/retrieval_eval.py:63–143,237`; `src/evals/dataset_builder.py:460–507` | R08 / 2 |
| L3 regenerates generic chunks; index reuse ignores settings beyond strategy | `src/evals/checks/l3_chunking.py:23–29`; `src/experiments/feature_addition_runner.py:251–255` | R09 / 2 |
| State is process-global; run/cache writes are not inherently run-isolated | `src/config/context.py:110`; `src/ingestion/indexing/factory.py:14–76`; `src/evals/assessment/answer_eval.py:107–115` | R10 / 2 |
| Container/config/auth and session-secret behavior need alignment | `Dockerfile:28–31`; `docker-compose.yml`; `src/app/session.py:20–25` | R04 / 1; R11 / 3 |

The test suite's mocked coverage does not negate these findings. Regression tests must cover the missed call boundaries, not merely assert that individual helper mocks were invoked.

## 3. Target seams and configuration contract

### R00 — Minimal architecture changes

Reuse `src/infra/llm/interfaces.py`, `src/app/factory.py`, `src/app/dependencies.py`, `src/usecases/chat.py`, and the existing retrieval/configuration models. A thin provider implementation belongs under `src/infra/llm/`; real orchestration belongs at the use-case boundary. Do not make lower layers import app or CLI code, or loosen import-linter rules merely to place a new integration conveniently.

Use existing dataclasses/Pydantic models and explicit parameters. New small fields/models are allowed when required by a specific contract; a generic harness framework or service locator is not.

### R05 — Separate implementation from provider and role

The following are logical configuration requirements, **not implemented setting names or CLI flags**:

| Axis | Required effective identity |
|---|---|
| Generation implementation | Existing clients or Pydantic AI adapter |
| Chat harness | Deterministic RAG; later tool-driven variant |
| Generator | Provider/route, exact model, sanitized endpoint/region, request settings |
| Judge | Independently selected provider/route/model/settings and rubric |
| Embedder | Provider/model, dimensions, task/normalization settings, endpoint/region |
| Retrieval | Effective profile/options, reranker model/revision, index fingerprint |
| Telemetry | Disabled/local/approved export, content policy, destination |
| Budget/accounting | USD 20/month, approved charge scope, provider quota versus cash, pricing provenance |

Implementation MUST:

- Validate unknown implementations/providers and unsupported combinations instead of silently selecting Qwen.
- D03 selects OpenCode Go models `deepseek-v4.1-flash` / `mimo-v2.6-flash`; owner reports checking workload eligibility. Verify actual account/model access and capabilities, not the eligibility choice again. Set an honest application `User-Agent` and an opaque stable `x-opencode-session` per conversation; keep it stable across turns/retries, isolate unrelated cases/variants/judge conversations, and never reuse raw cookies, credentials, patient IDs, or another client's identity. Use request-scoped headers without mutating shared client state; test sync/async/streaming/structured paths offline. Keep Go and Console pay-as-you-go/direct-provider routes distinct; no silent fallback or model substitution.
- Resolve effective settings once at the run/composition boundary, including profile overrides, and pass the same snapshot to execution, manifests, and diagnostics.
- Define complete non-secret precedence: explicitly provided CLI flags > explicit experiment/variant overrides > selected runtime profile > resolved application settings. Within application settings: explicit `Settings` initialization > process environment (including dotenvx-injected values) > an explicitly configured dotenv source, if one is later added > `config/settings.yaml` > Python field defaults. Currently no project `env_file` is configured. Thus explicit run/profile values intentionally override environment-derived application defaults; use an explicit run override to supersede a selected profile. Loader-generated defaults are not explicit overrides; track presence so they do not mask profiles. Test these conflict cases, including explicit `false`.
- Resolve secret values independently through supported settings/secret injection, never through experiment/profile YAML. Keep the actual nested `APP__` behavior and do not revive undocumented flat aliases accidentally.
- Preserve explicit `false`, `0`, and empty/disabled options where meaningful. An `or` fallback must not silently re-enable a feature a run disabled. Reject invalid values explicitly.
- Permit a generator and judge to use different providers. A Gemini-only generation/judge task must not be gated on a DashScope generation key; an embedding request still legitimately requires its own configured credentials.
- Make generation temperature, token limits, timeouts, and supported reasoning settings explicit. Unsupported settings produce a clear validation error or a documented omission recorded in the run—not silent equivalence.
- Keep provider-specific settings small and allowlisted. Do not expose arbitrary endpoints or secret-bearing request dictionaries to browser callers.
- Preserve old configuration through a documented translation/deprecation path decided under D10. Emit resolved non-secret settings for inspection.

## 4. Runtime and transport requirements

### R01 — Correct async path and lifecycle

- Non-empty `POST /chat` must reach retrieval/generation without calling a sync-only initializer in an active event loop.
- Async orchestration is canonical for serving; startup initializes the selected index, and request readiness uses the async path or an explicit already-ready dependency. Keep thin sync CLI wrappers without nested event loops, not a second orchestration implementation.
- Run initialization's blocking lock/store/build work off-loop as one serialized unit. Cancellation observed before its post-lock admission checkpoint skips work; after admission, cancellation stops only caller waiting, not the synchronous build. Keep the lock until admitted work completes/fails. Do not promise that a `Task.cancel()` request alone revokes a worker that passes admission before cancellation is delivered.
- Blocking store access, query expansion, HyPE lookup, embedding/search/reranking operations used on the web path must be moved off the event loop or use a truly async implementation. Merely renaming a function `async` is insufficient. Native async HyDE must await the existing client async method on its owning loop, not call the sync method or move an async SDK to a worker.
- Preserve sequential expanded-query search and existing ranking/source/trace semantics when offloading. Serialize shared lazy reranker lookup/loading/prediction. Caller cancellation must propagate without starting downstream orchestration, while acknowledging that an already-started synchronous stage/batch can finish; no thread termination, hard resource cap, or charge reversal is promised.
- Reuse clients within their owning app/run and close owned sync/async SDK clients and streams on shutdown/cancellation. Do not close externally injected clients accidentally. App cleanup must cover partial startup and exceptional lifespan exit, drain its owned initializer/cleanup tasks before reset, and avoid replacing primary failures or exposing SDK exception details through ordinary cleanup errors. These app-owned task guarantees do not imply termination/draining of every request worker or physical database shutdown.
- Test real async retrieval boundaries with an isolated fake store/embedder. The initializer guard itself must not be mocked away in the regression test.

### R02 — Requested configuration equals executed configuration

- Apply retrieval profile settings, including top-k and reranking, to the actual chat/use-case retrieval call; remove unconditional route-level values that override the resolved profile unintentionally.
- Pass HyPE/enrichment feature flags explicitly into `IngestionRunConfig`; do not smuggle them through a vector-store normalizer that drops unknown fields. Use the existing runtime overlay as the handoff from typed ingestion configuration; zero sampling means no generation. Selecting flags must not silently rebuild/enrich an already-populated store, and next-build configuration is not evidence of materialized index features.
- Assert enabled enrichment really invokes the configured work and disabled enrichment does not. The correct client role must be selected; enrichment currently directly imports the Qwen factory in `src/ingestion/nodes/enrich.py`.
- Keep the existing embedder initially; document any remaining provider-bound roles explicitly rather than promising a project-wide provider switch.
- Trace/config endpoints report actual provider/model and effective options, not always `settings.llm.model_name` when Gemini/LiteLLM is executing. Distinguish a successfully applied profile from the configured/requested profile; use the injected client's model when available. Keep generation and retained index-time Qwen roles distinguishable. Preserve explicit option presence at the CLI retrieval boundary and keep mode aliases/top-k coherent with executed options.
- Activating a corrected profile may change rankings. Capture and explain this deliberate bug-fix delta; do not require parity with previously broken behavior.

### R03 — Stable streaming, cancellation, and history

- Preserve incremental `content` events and the terminal `done`, sources, pipeline, sanitized error, and request-ID fields used by the frontend.
- Emit at most one terminal event on a connected stream. Client cancellation need not and generally cannot receive a terminal event; it must stop further generation/side effects as far as the SDK allows.
- Retry classified transient failures only within explicit attempt/time limits. Coordinate SDK, client, and framework retries so total attempts are bounded.
- Scope upstream attempt time budgets to active producer work, not time yielded to the consumer; never leave a task timeout active across a generator yield. Such a budget does not imply a hard request/process deadline or a bounded SDK-close duration.
- Once any content is emitted, do not invisibly restart generation or switch providers. Report the interrupted attempt as incomplete; any future resume/replacement protocol needs separate frontend approval.
- Explicitly close/cancel upstream streams in cleanup. Cancellation must not be swallowed or retried.
- Persist completed assistant turns as completed. Partial/error/cancelled text must not be reused as an ordinary successful turn: either discard it or mark/filter it explicitly; choose the smallest compatible implementation. Approved C2 semantics discard failed generation and publish a complete generated user/assistant pair in one atomic file replacement. After a cancellation checkpoint, submitting the owned off-loop persistence task is commit admission; a queued/started admitted job may still publish the complete pair on cancellation. Drain it before releasing same-session admission and propagate cancellation, even if the job fails. Server completion does not prove terminal delivery; no rollback of an already-published turn, hard drain deadline, or power-loss durability is implied.
- Preserve session isolation and test concurrent turns. Reject or serialize overlapping turns for one session rather than silently interleaving history; do not expand to a new conversation database unless required by D09/D14. C2 rejects same-instance turns/history clears for an active session before history/retrieval/generation work, releases the guard before terminal yields, and allows unrelated sessions. Busy chat uses a sanitized `chat_session_busy` SSE terminal (HTTP headers already sent); busy clear returns 409 without rotating the cookie. Custom history stores must support the existing protocol's `turn` and atomic `save_turn` capabilities; do not silently fall back to two individual writes. Low-level `save_message` and independent instances are not whole-turn serialization APIs; multiworker shared-file use remains unsupported.

### R04 — Configuration and dependency availability

- Include authoritative non-secret configuration files in images; align local and container provider/profile selection.
- Publish a non-secret preflight that reports effective roles, missing credential names, optional extras, index readiness, and capability mismatches without making paid requests.
- If cross-encoder reranking is selected, install/test its extra and verify model asset availability explicitly. Serving startup must not unexpectedly download large assets or rebuild a corpus during a benchmark.
- Separate deployment modes explicitly; never use a production entrypoint name as proof that production settings are active.
- Declare the supported worker/storage topology. With the current process-local history lock, do not advertise safe shared-file multiworker writes; restrict to one worker or separately implement/test process-safe persistence before enabling that topology.
- Keep `.env.example`, setup/runbooks, and config docs consistent with implemented nested settings.

## 5. Reproducibility, caching, and artifacts

### R06 — Versioned experiment identity

Extend existing artifacts/manifests rather than creating a competing experiment-tracking database. Under approved D10 consolidation, a small local manifest is retained even when Logfire is the primary UI; R15 adds cost summaries to existing records, not another tracking database. Persist these non-secret facts:

- Result/metric/schema versions, code revision, working-tree state, dependency-lock digest, and runtime versions. Dirty-source runs require a source-content digest for reuse; otherwise disable semantic cache/run reuse and promotion for those runs.
- Requested AND effective configuration; generation implementation and harness identities.
- Provider/route/model/settings, sanitized endpoint/region, prompt/message template hash, tool/schema version, and history representation hash.
- Judge provider/model/settings, rubric/evaluator version, and expected-answer/evidence identity.
- Corpus snapshot and parsed-source digests; actual index fingerprint; embedding model/dimensions/settings; chunker and reranker configuration/revision.
- Dataset bytes/case IDs, split, label provenance/review state, normalized task inputs, sampling seed, repetitions, and execution order.
- Cache policy, reuse provenance, failures/skips, timings, usage, and nullable cost with pricing-source/date if known.

Identity rules:

1. Distinguish a unique execution/attempt ID from a content-derived experiment fingerprint. Repetitions may share a fingerprint but must not collapse into one reused execution.
2. Labels, display names, artifact locations, and `force_rerun` are execution concerns, not substitutes for semantic identity.
3. Build a deterministic fingerprint from canonical collection content/IDs/metadata plus the index build specification. Do not hash a Chroma directory with a file-only helper or use volatile DB/WAL timestamps as the sole content identity. Freeze/read a consistent snapshot; verify any stored manifest against the actual collection.
4. Generation identity includes actual prompt/messages/context, implementation, model/route/settings, and output schema. Judge identity includes actual output, expected evidence/answer, judge/rubric/settings, and metric implementation.
5. Retrieval caches need query, effective retrieval/expansion settings, expansion-model identity where applicable, and index identity. Judge changes should not force expensive re-embedding; generation changes should not invalidate an otherwise unchanged index.
6. No credential value or hash of a secret is stored. Use a non-secret credential/account profile identifier only if it changes routing semantics. Sanitize endpoint URLs and exception text before persistence/export.
7. Bump incompatible cache/result versions. Old data remains readable and marked legacy; it cannot satisfy new required measurements automatically.

Cache and artifact behavior:

- Use per-run writable caches and atomic replacement for local JSON files. Shared cross-process read/write caches are deferred unless locking/transaction tests are implemented.
- An explicit reusable read-only cache snapshot may be copied into a run, with origin and identity validation recorded.
- Do not persist transient failures as successful reusable metric values. Record failures for diagnosis separately.
- Benchmark mode executes fresh attempts; cached-answer replay is a distinct functional/replay mode, never a latency sample for live generation.
- During transition, keep existing local JSON/JSONL artifact filenames readable by current consumers. Under an approved D10 cutover, archive legacy artifacts unchanged and retain a small versioned local manifest/report/export; indefinite legacy dashboard/API maintenance is not presumed.

### R07 — Measurement completeness and gating

Model three facts separately in the artifact contract: execution outcome, measurement completeness, and quality-gate result. Names may fit existing schemas, but semantics must be explicit.

- A required metric that is missing, skipped, invalid/non-finite, errored, or computed on insufficient eligible cases cannot pass.
- An explicitly disabled answer-evaluation suite is `not_applicable`, not a measured pass; retrieval-only runs can pass their own declared retrieval requirements.
- An enabled suite lacking its provider/dependency/credentials is incomplete/error with an actionable message, not silently disabled.
- Collect per-case failures instead of losing all completed work when one task raises. Summaries show expected/measured/failed/skipped denominators and coverage per metric.
- Report quality on measured cases AND failure/completion rates across all eligible cases; failed variants cannot win by dropping hard cases.
- A strict gate returns a nonzero CLI exit for incomplete requirements or failed quality. Exploratory mode may return artifacts without blocking development, but its quality status must remain incomplete/failed as appropriate.
- Keep legacy `status` behavior compatible only where it cannot turn incomplete new results into `ok`; document the mapping for API readers.

## 6. Dataset and scoring contract

### R08 — Reviewed evidence and honest metrics

The initial foundation is a fixed-index exploratory pilot with frozen cases and independently checked evidence judgments. Stable IDs plus frozen evidence quotes are sufficient for that pilot. Cross-chunk span mapping and broad clinical annotation are conditional extensions for chunking/safety/promotion studies, not prerequisites for exercising a generation adapter. Unreviewed wiring fixtures remain explicitly unreviewed and cannot establish quality superiority.

Use existing fixtures as candidate seeds, not automatically verified gold. Each versioned scored benchmark case must identify:

- Stable case ID, query or conversation turns, category/risk tags, answerability, split, and source family.
- Frozen source revision/hash and evidence passages; optional reviewed expected answer/required facts, forbidden claims, and acceptable uncertainty behavior.
- Label origin (`human_reviewed`, synthetic, heuristic), review status, and relevance grades. Missing review must not be upgraded to human/high confidence by keyword overlap.
- For source-span labels: offsets in the frozen canonical text with an explicit normalization/offset convention, plus passage text/hash. Map these spans to each chunking variant rather than treating one chunker's IDs as universal truth.

Scoring requirements:

- Keep source-family hit metrics separately labeled as proxies; matching a document title alone does not establish answer-bearing evidence relevance.
- Define a versioned primary retrieval unit (recommended: reviewed evidence passage) and avoid counting repeated chunks covering one passage as independent recall successes.
- Compute standard nDCG using the independently judged relevance set and documented gains/discounts, not only relevance found in the returned list. Proposed gains are `2^grade - 1` with logarithmic discount; ratify with hand-calculated tests before calibration.
- Recall denominators and retrieved numerators must use the same judged unit. Where judgments are incomplete, label the metric as judged-set recall, not whole-corpus recall.
- Precision@k uses a documented denominator of k, including missing result slots. If a returned-only precision proxy is retained, name it differently.
- Report evidence hit/coverage and duplicate/source diversity independently. Exact chunk hit is diagnostic only within a fixed chunking version.
- Unanswerable/no-relevant-evidence cases use abstention/unsupported-claim checks; mark ranking metrics not applicable rather than manufacturing an ideal relevance set.
- Preserve fixture `dataset_split` assignments unless deliberately rebuilding the benchmark. Detect duplicates/near-duplicates and report source-family overlap; distinguish same-corpus holdout from source-family generalization. Freeze test cases before tuning and record any unavoidable overlap.
- Synthetic data generation is an explicit separate operation. Benchmark evaluation must not silently add new synthetic questions or bootstrap changing labels per variant.

Pilot size and final promotion thresholds are decisions D07/D08, not guaranteed statistical power. A small reviewed pilot can validate wiring without establishing clinical safety or equivalence.

### R09 — Evaluate executed artifacts and control index reuse

- L3 assesses actual emitted chunks/configuration for the selected run, including HTML/PDF/reference coverage where applicable; do not recreate a generic PDF-only approximation.
- Reuse an index only when every index-affecting input matches its verified fingerprint. Chunk size/overlap, extractor/normalization, enrichment, embedder, dimensions, source snapshot, and metadata affecting ranking all matter—not only strategy names.
- Read-only generation comparisons share an identical frozen index. Index-changing experiments build isolated collections/storage, never overwrite the served baseline.
- Reports distinguish deliberate bug-fix changes from harness changes. Rerun affected HyPE/enrichment/profile studies; retain old reports as legacy evidence.

### R10 — Run isolation and honest performance measurement

- Start with a fresh subprocess per variant. Each receives a resolved non-secret config and secret access through approved environment injection, not CLI arguments.
- Give every attempt separate outputs, history, mutable caches, and any writable index. Process isolation alone does not protect a shared on-disk Chroma directory or history file. If the embedded backend cannot enforce safe read-only sharing, use verified per-process snapshot copies rather than assuming a read-only API exists.
- Do not run in-process evaluations against the same mutable singleton state as serving chat. Avoid a broad global-state refactor until a concrete use case requires it.
- Measure cold start/model loading separately from warm steady-state retrieval/generation. Seed any intended warm cache explicitly; a cache-disabled run does not populate an application cache.
- Record time to first token, retrieval, reranking, generation, total elapsed time, and judge overhead separately. Include sample count, hardware, concurrency, repetitions, order, cache state, and backend route.
- Exploratory fixed-index pilots may report descriptive matched per-case results, sample counts, and recorded execution order without claiming statistical significance or equivalence. Before inferential/promotion claims, use repeated runs and paired uncertainty estimates; cluster resampling by conversation/source grouping where independence assumptions require it and document the method.
- Show raw distributions/per-case data. Do not infer equivalence from an insignificant difference or select a winner from incomparable datasets.

### R15 — Simple monthly budget and usage accounting

- Use the accepted USD 20/month incremental-project ceiling with no mandatory per-run dollar maximum: generation, judges, embeddings, expansion/enrichment, and metered telemetry share it. Existing fixed Go subscription fees are separate; a new paid subscription/tier needs separate approval.
- Add a compact cost summary to existing per-run manifests/logs: UTC month, run ID, reported usage by role, nullable cash estimate/actual charge, pricing source/date, and unknowns. Summarize these records by month, counting each run once. No new billing database, request-event ledger, invoice integration, or dashboard.
- Keep informational existing subscription fees, included-quota token-value consumption, and metered incremental cash charges separate. Use a small manual charge/adjustment record for Console reconciliation; do not double-count prepaid top-ups and consumed usage. Go account-level quota/billing API access has not been verified: use reported tokens/nullable quota estimates where available and explicitly require Console/manual reconciliation for exact balance/invoices. Notify the owner if usage is absent or only estimated.
- Include available usage from generation, judges, embeddings, expansion/enrichment, and retries; failures/cancellations can cost money. If SDK totals omit attempts or final usage, mark the summary incomplete rather than inventing precision. Do not sum both SDK and enclosing framework totals for the same call. Add event-level bookkeeping only if a concrete need is separately approved.
- Show known totals, estimates, and unknowns; missing usage/prices are never zero. Do not start new paid runs when the recorded monthly ceiling is reached. Confirm automatic top-ups/overage are off (including Go Console **Use balance**); local logs cannot guarantee a hard cap on in-flight, delayed, or outside-repo spending.
- Live runs still need explicit finite case/request/token/time/concurrency settings and approval. Test monthly aggregation, duplicate run summaries, quota/cash separation, and incomplete/unknown usage offline; no billing-service test suite.

## 7. Observability, privacy, and deployment

### R11 — Content-safe traces and storage

- Instrument request/use-case, retrieval/expansion, embedding/search, reranking, generation, retry/cancellation, and evaluation spans. Correlate request, run, case, and attempt identifiers without logging raw session cookies or patient identifiers.
- Record actual model/route and provider-reported usage. Missing usage/prices are null/unknown; separate measured from estimated cost.
- Instrument the baseline as well as Pydantic AI so traces compare equivalent stages. Avoid duplicate nested SDK/framework spans inflating usage totals.
- Default general-purpose prompt/completion/tool capture off; preserve disabled/local/metadata-only modes. D10 explicitly permits allowlisted public/synthetic case inputs/outputs and approved associated report fields in the chosen Logfire project. Enable this only for classified/approved runs, not blanket SDK/HTTP body capture or unrelated chat history/document uploads. Secrets, real patient data, cookies/auth headers, and unsanitized validation/exception payloads remain forbidden.
- Apply the selected mode's allowlist at every export boundary, including automatic Pydantic Evals report export and FastAPI instrumentation. Model-message settings alone do not control eval reports. Verify version-specific controls: metadata-only mode suppresses case content; approved-public/synthetic mode exports only allowed fields after local verification and destination setup.
- Use a local in-memory exporter to test both modes: content fixtures must stay absent in metadata-only mode and appear as expected only in approved-content mode. Synthetic canaries representing forbidden secrets/identifiers must be absent from serialized spans/logs/reports in both modes, including error paths. Inspect a synthetic-only hosted smoke before broader export.
- Local/disabled telemetry requires no hosted account; exporter failure must not fail user requests. Explicitly flush/close on shutdown within a bounded timeout.
- Do not expand W&B or custom eval-dashboard functionality. New raw W&B artifact export defaults off; preserve history during transition. The approved D10 consolidation target makes Logfire the primary UI and retires redundant writes/paths in a separately approved Phase 4 slice; no deletion is inferred.
- Protect local sensitive artifacts too: implement/document approved access, retention, deletion, backups, and remote lifecycle policies before processing such data. Replacing local JSON storage is not automatically required for a synthetic-only private lab.

Deployment hard gate:

- Require a dedicated unpredictable session-signing secret outside development, including when auth uses JSON records; define rotation/invalidation behavior.
- If public deployment is selected, separate public chat from authenticated private config/evals/documents/experiment views. Keep privileged credentials server-side; do not put a master API key into frontend settings.
- Verify environment selection, cookies, CORS, auth boundaries, and readiness in a lifespan/container smoke test. No public rollout while D01/D14/D15 remain unresolved.
- Clearly label existing frontend confidence as an uncalibrated retrieval diagnostic; do not display a fabricated probability of medical correctness.

## 8. Pydantic migration and behavioral exploration

### R12 — Pydantic AI generation adapter

- Implement the existing sync, async, streaming, and structured-generation contract with typed return behavior. Tighten streaming typing minimally if needed; do not expand the protocol into an agent scheduler.
- Match prompt text, instruction placement, history flattening, retrieval context, provider route/model, temperature, token limits, and output mode for the baseline comparison. Record any unavoidable representation mismatch as a confound.
- Build and reuse owned agents/models/HTTP clients per app/run; do not construct a new provider per token or per judge metric unintentionally.
- Configure exact endpoint region and explicit secrets through existing settings resolution. Provider-native and gateway routes are different conditions; disable automatic fallback for comparisons.
- Use the supported Pydantic AI test/function models and a deny-live-request guard for offline tests. Also guard non-Pydantic SDK paths; its guard alone does not protect the existing clients.
- Verify provider capability profiles with contract tests plus a small approved live smoke. JSON-object mode, JSON-schema enforcement, and tool-based structured output are not interchangeable labels.
- Structured output validates the requested Pydantic model; unsupported schema modes fail explicitly. Bound schema-validation retries and account for their usage.
- The existing generation implementation remains selectable without a Pydantic credential or Logfire token. New integration dependencies follow the supported-mode decision and are locked/tested before default activation.

### R13 — Pydantic Evals tasks for both implementations

- Wrap existing plain-Python baseline tasks and the new adapter using identical frozen inputs and normalized result fields. Use the ordinary task API; do not require Pydantic AI to evaluate the baseline.
- Preserve ingestion checks and repaired domain retrieval metrics. Adopt Pydantic Evals as runner/reporting infrastructure, not as an automatic replacement for medical judgment.
- Keep useful DeepEval evaluators through thin task/evaluator integration during calibration; retire duplicate orchestration/reporting after an approved D10 cutover. A metric dependency may remain without maintaining a parallel evaluation platform. Avoid two divergent definitions of each metric.
- Run judges on the same saved outputs when comparing evaluator versions; run generation separately when comparing systems. Tag evaluator versions and never merge equal-named but differently defined scores blindly.
- Add real harness replay for multi-turn cases, including actual assistant turns and isolated history. Evaluate turn-level grounding and contextual behavior as well as final conversation outcomes.
- Approved D10 target: Pydantic Evals execution + Logfire primary experiment UI, with versioned datasets/prompts/configuration and small local manifest/report/cost records for offline reproducibility and export recovery. Pydantic Evals datasets can be local/versionable or hosted in Logfire; hosted storage is a separate destination/content/access decision with dataset-scoped API keys, not merely a trace-export token. The documented dataset-management SDK is experimental; pin/test versions and retain a frozen dataset snapshot/hash for every run. Legacy reports remain readable during migration and archived thereafter only if cutover is approved. Hosted views remain subject to R11 and are not required for offline execution.
- Set required evaluator coverage explicitly and use R07's completeness rules irrespective of the runner's default success semantics.

### R14 — Optional tool-driven harness

Phase 5 needs a separate approved change plan. Initial recommendation is one read-only corpus retrieval tool with validated arguments/results and explicit citation IDs. No shell, arbitrary filesystem, autonomous downloads, unrestricted URLs, dosing, or diagnostic tool is authorized by this spec.

- Use the chat-use-case boundary for orchestration; keep the generation adapter thin.
- Add native history, query rewriting, clarification, structured answers, or citation validation as separately named variants so effects can be attributed.
- Bound turns/tool calls, total requests, tokens, time, retries, and cost. Validate tool inputs; handle empty evidence, tool errors, prompt injection, and loop exhaustion explicitly.
- Assess claim-to-evidence support, fabricated citations, uncertainty, unsafe requests, and malicious retrieved text—not merely whether a retrieval span exists.
- A deterministic control always performs retrieval as designed; an agent may legitimately clarify or abstain without retrieval. Define trace/trajectory expectations per scenario rather than forcing a tool call on every question.
- Emit only permitted user-facing text and tool activity summaries, not private model chain-of-thought.
- Promotion requires D08's predeclared gate, reviewed cases, complete measurements, and explicit approval. No switch is required merely to finish an exploration.

## 9. Rollout and compatibility

- Keep the existing SSE/API fields stable through Phases 1–4. Any new internal completion fields must be translated to the current wire shape.
- Version manifest/metric/cache semantics explicitly and test loading legacy/new artifacts during transition. D10 may approve archival rather than indefinite live dashboard/API compatibility; do not remove paths or discard history before that bounded cutover. Legacy runs never become valid new-benchmark evidence merely by being imported.
- Preserve existing client implementations until offline contracts and approved live checks pass for selected routes. Deprecation/removal is a separate decision under D10.
- Correctness/security repairs are not optional rollout flags that can be disabled to reproduce an unsafe production path. A historical revision can be used only in an isolated, clearly labeled diagnostic environment.
- Roll back a new adapter/telemetry exporter by selecting the corrected baseline or disabling export. Do not roll back cache integrity fixes, secret handling, or missing-metric enforcement to make a benchmark green.
- Never delete/rebuild the user's current index or history as a migration side effect. New index experiments use new storage paths and verified provenance.

## 10. Completion evidence

Every implementation slice records changed files, requirement IDs, test commands/results, known limitations, decisions used, and rollback instructions. Reports distinguish mocked integration correctness from actual provider support and engineering safety tests from clinical validation.

Required overall evidence includes: real async call-path regression coverage; effective-config assertions; interrupted-stream/cancellation tests; identity/cache invalidation tests; hand-calculated retrieval metrics; missing/failed metric gate tests; run/index isolation tests; content-canary export tests; old/new artifact compatibility; and matched-model baseline/adapter comparison results.

## 11. External references

Consult current documentation and pin compatible versions before implementing; examples here do not guarantee a future/latest API signature.

- [Pydantic AI models/providers](https://ai.pydantic.dev/models/overview/)
- [DashScope and compatible APIs](https://pydantic.dev/docs/ai/models/compatible-apis/)
- [Pydantic AI testing](https://ai.pydantic.dev/testing/)
- [OpenCode Go: endpoints, usage limits, and coding-agent-use condition](https://opencode.ai/docs/go/)
- [OpenCode Console models: separate pay-as-you-go application endpoints](https://opencode.ai/docs/zen/)
- [Pydantic Evals](https://ai.pydantic.dev/evals/)
- [Pydantic Evals / Logfire report integration and content export](https://ai.pydantic.dev/evals/how-to/logfire-integration/)
- [Pydantic Evals local dataset management](https://ai.pydantic.dev/evals/how-to/dataset-management/)
- [Local versus Logfire-hosted evaluation datasets](https://pydantic.dev/docs/logfire/evaluate/evals-in-code/)
- [Experimental hosted dataset SDK and API-key scopes](https://pydantic.dev/docs/logfire/evaluate/datasets-sdk/)
- [Span-based evaluation](https://ai.pydantic.dev/evals/evaluators/span-based/)
- [Logfire sensitive-data scrubbing and AI content exclusions](https://pydantic.dev/docs/logfire/instrument/python/scrubbing/)
