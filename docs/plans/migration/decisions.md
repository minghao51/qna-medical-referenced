# Decisions and open questions

**Status:** Owner responses D01–D10 recorded on 2026-10-15. Includes the owner's follow-up approving Go, Logfire/Pydantic Evals consolidation, and public/synthetic input/output export. Accepted choices and remaining technical checks are distinguished below. The owner subsequently approved P1-A1–P1-A4 plus the bounded P1-B configuration, P1-C1 streaming, and P1-C2 history/concurrency slices and requested async-first options. These offline slices are complete: [P1-A1](20261015-p1-a1-handoff.md), [P1-A2](20261015-p1-a2-handoff.md), [P1-A3](20261015-p1-a3-handoff.md), [P1-A4](20261015-p1-a4-handoff.md), [P1-B](20261015-p1-b-handoff.md), [P1-C1](20261015-p1-c1-handoff.md), [P1-C2](20261016-p1-c2-handoff.md) (2026-10-16). Async orchestration is canonical; retain only thin sync CLI entry wrappers and offload currently synchronous work. **2026-10-20 decisions:** review-authority policy, matched baseline tuple, Logfire/OTel adoption go, hosted-export setup policy, budget-admission posture, and the D11 embedding freeze are recorded in the section below.

## Phase 4 staged start — recorded 2026-10-21

Owner selected working Go-powered chat through Pydantic AI as the primary goal and accepted a staged Phase 4 plan with stop points. See the [fresh-session pickup brief](20261021-phase4-pickup-brief.md) for the full answers, scope and workflow.

- **D03/D17 upcoming generator:** MiMo V2.6 Flash through OpenCode Go replaces the earlier DeepSeek selection for the upcoming Phase 4 route/comparison. Exact model ID/endpoint/capabilities require verification; historical baseline snapshots remain unchanged. No serving-default switch or live use authorized.
- **P4-A authorization:** inspect and perform isolated dependency/provider compatibility work; registry access and isolated installs allowed. Present exact dependency changes/capability findings before applying project-lock changes or P4-B implementation. Stop on unrelated major upgrades.
- **Structured output:** schema-validated support required for internal tasks and user-facing generation. Unsupported route capabilities require an owner decision, not silent downgrade or model substitution.
- **Judge/promotion:** recommend an independent different-family judge after capability findings; exact ID/settings remain unpinned. Correctness, comparable quality, explicit latency/usage trade-offs and maintenance burden guide evaluation; no numeric default-promotion gate adopted.
- **Execution/privacy:** no live calls now; quota/spend/input permission required at the end. Local telemetry only; no hosted uploads, automatic provider/model fallback, patient data, default flip or legacy path removal. D18 no-fallback policy is accepted for this Phase 4 work; broader operational resilience variants remain separate. D16 paid/live CI remains open.

This narrowly supersedes earlier blanket Phase 4 exclusion for staged planning and P4-A only. It does not waive earlier integrated-comparison prerequisites, authorize every later slice, or mark any Phase 4 implementation complete. Dependency installations and capability tests have not started at this handoff.

## Consolidated remaining Phases 1–3 approval — recorded 2026-10-19

The owner requested completion of Phases 1–3, then said **“proceed” / “approve the plan”** and subsequently **“continue.”** This approves the consolidated lifecycle/preflight, identity/evidence/isolation/accounting, and controlled telemetry implementation plan; do not ask again for the same scope. Locked evaluation dependencies and Playwright's locked browser/runtime requirements may be provisioned. Exact Logfire **5.2.0**, OTel **1.45.1**, and protobuf **6.33.6** adoption is conditional on compatibility/privacy verification; stop if unrelated upgrades are needed. The current lock changes only this dependency family (including its added/removed transitive dependencies); existing provider SDK, Chroma, and DeepEval versions are unchanged.

This supersedes earlier installation restrictions only for that narrow work. Credential inspection, live generation/embedding/judge calls, hosted exports, corpus/model downloads, existing-data migration/deletion, provider/model/default switches, public deployment, and Phase 4 remain excluded. Human/runtime checks cannot be invented. The [current integration handoff](20261019-phases-1-3-integration-handoff.md) distinguishes delivered code, current verification, and remaining gates; **none of the three whole phases is declared complete**.

## Owner decisions — 2026-10-20 (second continuation)

Recorded after the [admission/manifest/spans handoff](20261020-admission-manifest-spans-handoff.md). Approver: repository owner, in-session ("D1 b) / D2 b) / recommendations for the rest"). Each entry settles policy and retains its evidence/verification conditions; none of them authorizes live calls, spend, hosted export execution, or default switches by itself.

- **Review authority (D07 extension) — named independent engineering reviewer.** Option (b) of the presented choices: a named independent engineering reviewer who is not the implementation author supplies review manifests through the fail-closed hash-attestation mechanism; the authority's name, scope and date are recorded here when first exercised. Content hashes authenticate supplied-content consistency only — never reviewer identity, medical qualification, or clinical endorsement (D01/D07 scope unchanged). `reviewed_evidence_eligible`, cohort and promotion eligibility remain false until the first manifest from the recorded authority verifies; numeric qrel diagnostics remain non-clinical.
- **Matched baseline tuple (D17 remainder) — generator: Go route `deepseek-v4.1-flash`; judge: one independent fixed judge from a different model family.** The exact judge model ID, prompts, temperature and token limits are pinned in the matched-run configuration snapshot before any live run. This selection does not authorize live calls, spend, or a serving-default switch; D03 account/route verification and D04 budget admission gates still apply to the eventual run.
- **Logfire/OTel adoption — proceed with the conditionally approved bounded slice.** Exact Logfire **5.2.0**, OTel **1.45.1**, protobuf **6.33.6** per the 2026-10-19 approval. Compatibility verification and P3-C content-canary tests remain the slice's stop/go gate; stop if unrelated upgrades are required. No application tracing or hosted export is enabled by this record alone.
- **Hosted export setup (D06/D15) — dedicated Logfire project, 30-day retention, minimal named access, metadata-only smoke first.** The approved public/synthetic case-content mode is exercised only after P3-C canaries pass. Actual destination/region/access configuration and any hosted smoke are still separate setup/permission steps; nothing has been configured or uploaded.
- **Budget-admission posture (D04 extension) — informational, fail-closed admission on recorded paid operations only.** Interactive chat serving stays ungated; no operational USD-20 hard-cap guarantee is claimed. In-flight/delayed/outside-repository charges and automatic provider overage remain disclosed limitations; a chat gate is reconsidered only after an actual cost incident.
- **Embedding/index freeze (D11) — option (a): freeze the current embedding model, 768-dimensional representation, corpus snapshot and index for initial comparisons.** Any reindex or embedding-provider change is a separately named variant/experiment with its own identity; cross-encoder/reranker assets remain unselected and not downloaded.

D15's policy direction is recorded above (destination setup pending). D12, D13, D14, D16 and D18 remain open. D17 is settled except for judge-ID pinning and capture evidence.

## How to record an answer

Reply using decision IDs, for example `D01: private lab; D02: public/synthetic only`. Update each record with the accepted choice, rationale, date, approver, and any conditions. Do not infer approval from silence or from provision of an API key.

## Owner decision summary — 2026-10-15

| ID | Recorded choice | State / remaining condition |
|---|---|---|
| D01 | A: private research lab | Accepted; no public or clinical product rollout |
| D02 | Public and synthetic data only | Accepted; no real/de-identified patient data; approved case input/output export under D10 |
| D03 | OpenCode Go; DeepSeek V4.1 Flash or MiMo V2.6 Flash | Selected; owner reports checking workload eligibility. Verify account access, request headers, capabilities, and usage reporting before live validation |
| D04 | USD 20/month incremental project spend; simple tracking/logging | Includes generation, judges, embeddings, enrichment, and metered telemetry. Existing Go subscription separate; included quota is not an extra cash charge |
| D05 | Adapter first, agentic behavior later | Accepted recommendation |
| D06 | Local tracing verification first, then Logfire | Public/synthetic case input/output export now explicitly approved under D10; destination/access/retention still need setup |
| D07 | Reference-heavy engineering evaluation, no clinical-suitability claims | Accepted; no clinician availability or independent judge model inferred |
| D08 | Test experimentally; prioritize reuse across experiments | Accepted objective; no numerical promotion gate or default flip approved |
| D09 | CLI/YAML first and isolated processes | Accepted recommendation |
| D10 | Pydantic Evals runner + primary Logfire UI; public/synthetic case inputs/outputs may be exported | Approved target and content permission; bounded migration/parity checks still required, no bulk deletion of history/index or unrelated changes |

Approver/source: repository owner, first-round interview and follow-up answers. Go workload eligibility is owner-reported, not independently authenticated/provider-tested by this review. Follow-up approves the consolidation direction and public/synthetic input/output export, not arbitrary paid runs, exposure of secrets/patient data, immediate uploads, destructive changes, or (at that point) the P1-A1 code slice. The subsequent “let's proceed, lets start” explicitly approves P1-A1; the next “proceed” approves P1-A2 concurrency/cancellation, followed by the async-first preference. “Proceed with next” approves P1-A3 off-loop retrieval/search/reranking and its necessary native-async HyDE correction. The subsequent “proceed” approves P1-A4 synthetic HTTP/SSE lifespan verification and app-owned startup-failure/cleanup fixes. After confirming handoff readiness, “continue with the tasks” / “proceed” approves the proposed P1-B effective-profile/ingestion-flag fixes and offline verification, including the necessary CLI retrieval-override follow-through. The next “proceed” approves the proposed offline P1-C streaming retries/cleanup work, begun as bounded P1-C1 (no prefix replay, owned public-stream cleanup, and failed-generation history discard). The subsequent “proceed” starts C2 inspection; the explicit “approve” accepts the concrete C2 plan: reject same-session overlapping turns/history clears, publish the completed pair atomically, hold admission until an admitted persistence worker settles, and propagate cancellation even though a complete pair may persist after admission. C2 is verified on 2026-10-16. Stronger request/SDK cleanup and retry-policy work remain separately bounded; neither C1 nor C2 completes P1-C/R03. These approve those bounded offline slices, not all migration phases or live runs.

## Offline Phase 2/3 implementation approval — 2026-10-16

The owner requested “procede with phease 2 and 3” using OpenAI Codex GPT-6 Luna subagents. The first presented bounded slice implements independent judge selection, explicit answer-suite activation, required-measurement/winner checks, and existing W&B/UI hardening; see the [handoff](20261016-p2-p3-foundation-handoff.md). This authorizes offline foundations, not waiver of Phase 1/integration exits or unresolved D11–D18 choices. Live calls, paid work, exports, dependencies, data migrations and default switches retain their separate gates. Neither Phase 2 nor Phase 3 is complete.

## P2-B1 approval — 2026-10-16

The owner said “approve” to the concrete fresh-attempt/identity-cache foundation plan after inherited-gate reproduction: version artifact records, separate execution IDs from fingerprints, capture bounded non-secret source/lock/content provenance, fail closed on unverified identity, publish artifact/cache files atomically, fix duplicate artifact-store creation and add offline regressions. See the [B1 handoff](20261016-p2-b1-handoff.md). Actual consistent index/effective semantic identity and replay remain unimplemented; disabling unverified reuse is not benchmark or promotion evidence. This approval retains all prior phase/live/dependency/export/data/budget/default-switch gates. Phases 1–3 remain incomplete.

## Phase 1/2 guard batch and package approval — 2026-10-16

The owner requested that the docs stay updated, approved installing the frozen-lock frontend dependencies and checking/installing packages for the Logfire compatibility spike, and selected **D17: corrected `baseline` for now**. The presented next batch covers dedicated session signing, unknown-provider/single-worker guards, and history/API/UI non-comparability handling. GPT-6 Luna `xhigh` subagents remain requested. Package-registry access and isolated compatibility installations are now approved; exact supported Logfire pins and any project-lock change must be recorded/reviewed before application tracing is adopted. No broad provider SDK upgrade is inferred.

D17 settles the comparison profile, not a generation-provider/model, independent judge, prompt/temperature/token tuple, a default harness/provider switch, or a live baseline run. Existing runtime profile defaults are not silently changed by the documentation decision. `baseline_cross_encoder` and its model assets are not selected or downloaded. Live provider/embedding calls, hosted export, real-corpus/model downloads, stored-data migration/cleanup, public deployment, and Phase 4 remain excluded. All three phases remain incomplete until their remaining evidence gates are satisfied.

**Historical documentation-only pause:** The owner then requested documentation only and continuation in another thread. The original subagents were stopped without implementation/installations; the [resume handoff](20261016-phases-1-3-resume-handoff.md) preserves that historical boundary.

**Resumption:** The owner subsequently requested implementation of Phases 1–3, explicitly resuming this approved bounded batch with OpenAI Codex GPT-6 Luna `xhigh` implementation subagents and OpenCode Go MiMo V2.6 Flash review. Dedicated signing/provider/single-worker and history/API/UI guards are now implemented; see the [guard-batch handoff](20261016-guard-batch-handoff.md). The frozen frontend install and type/build checks passed, with project locks unchanged. Browser execution is blocked on absent runtime assets/libraries. The requested MiMo model returned `model_coming_soon`; the owner subsequently explicitly approved OpenAI Codex GPT-6 Luna `xhigh` instead. That read-only [replacement review](20261016-guard-batch-review.md) identified two reader/UI issues. On 2026-10-17 the owner said “approve the repair slice”; both code findings and focused regressions are implemented in the [repair handoff](20261017-review-repair-handoff.md), with **889 passed / 6 optional DeepEval skips** and no actionable Luna re-review findings. Browser execution remains blocked; this approval does not provision browsers or upgrade dependencies. Switching coding reviewers does not select an application generator/judge or authorize package/live/export work. The compatibility spike does not authorize application tracing/lock adoption. No further live/export/default/Phase 4 permissions are inferred; Phases 1–3 remain incomplete.

## P1-C3a approval and open review finding — 2026-10-17

After “continue” authorized inspection, the owner explicitly said **“approve”** to the concrete SDK-boundary slice: transient-only nonstream retries without nested attempts/raw SDK logs; owned public stream cleanup through repeated cancellation before session ownership releases; focused isolated regressions and Luna `xhigh` review. The proposal disclosed that nonreturning cleanup may keep a session busy, and excluded broader worker ownership, SDK upgrades, browser provisioning, live calls and defaults changes.

The [C3a handoff](20261017-p1-c3a-handoff.md) records **1,282 passed / 6 optional DeepEval skips**, ten fresh 391-case runs and static checks. Luna review found one remaining default-Gemini-aiohttp connection retry that ignores `attempts=1`; parent reproduced it on both async nonstream methods and streaming. At that checkpoint C3a was not fully cleared. At that review checkpoint, explicit selection/ownership of the SDK's public HTTPX async transport was proposed but **not yet approved/applied**; no private SDK patch or dependency change is inferred. Broader C3b work follows only after inspection/presentation/approval. All phase/live/export/asset/data/default gates remain.

## Gemini HTTPX review-fix approval — 2026-10-17

The owner subsequently said **“proceed with the fix”** to the concrete public-HTTPX Gemini transport/lifecycle proposal. This explicitly approves that SDK async transport choice, owned cleanup and constructor/lifecycle regressions, **not an SDK upgrade, provider/model/profile switch or broader worker work**. The [fix handoff](20261017-gemini-httpx-fix-handoff.md) records 37 added cases, 10/10 fresh processes, **1,319 passed / 6 optional DeepEval skips**, static checks and no actionable scoped Luna re-review findings. The generation adapter's original finding is resolved; native SDK-default aiohttp behavior, direct judge SDK routes and physical per-stream release are not thereby certified. All other phase/live/export/asset/data/dependency/browser/default permissions remain unchanged.

## First-round interview

These questions are intentionally opinionated. The goal is to prevent building an elaborate framework benchmark that does not answer your actual question.

### D01 — What are we optimizing, and who uses the system?

**Question:** Is the primary deliverable (A) your private harness/model research lab, (B) a public educational demo with a private lab, or (C) a production medical-facing application? Rank learning/developer experience, answer quality, latency, cost, and reliability.

**Recommendation:** A first. Use maintainability/debuggability plus non-regressing answer quality as the initial migration objectives; do not require a framework to improve medical correctness just because it is newer.

**Why it matters:** Determines auth, deployment, safety review, concurrency, UI work, and promotion criteria. C requires a substantially larger governance and operational scope than this migration.

**Blocks:** Phase 1 deployment policy; Phases 3/5 rollout. Offline defect repair can be proposed independently.

**Decision:** Accepted 2026-10-15: A, private research lab. Prioritize reusable experimentation, developer experience, and debugging without clinical product claims. Do not build public-demo auth/deployment features in the initial migration.

### D02 — What data may enter models, local artifacts, and hosted telemetry?

**Question:** Public documents and fabricated questions only, de-identified real cases, or identifiable patient data? Are there residency, retention, institutional, or vendor restrictions? Is any currently retained data sensitive?

**Recommendation:** Public corpus plus synthetic conversations only. No patient uploads during migration; metadata-only external telemetry; no raw content exports by default. Do not equate de-identification with zero privacy risk.

**Why it matters:** Queries, embeddings, judge prompts, tool inputs, history, artifacts, and exception payloads are all data flows—not just the final answer. Existing approved co-pilot aspirations do not authorize using real patient data now.

**Blocks:** All live calls if the dataset classification is unknown; all hosted export. Offline work uses isolated synthetic fixtures.

**Decision:** Accepted 2026-10-15: public and synthetic data only. Real and de-identified patient cases are out of scope. D06 retains local verification first; D10's follow-up explicitly permits public/synthetic case inputs/outputs in Logfire. Secrets, credentials, real patient data, and unrelated artifacts remain excluded.

### D03 — Which providers and routes should we validate first?

**Question:** Which accounts do you actually want the app to use: DashScope, direct Google/OpenAI/Anthropic, OpenRouter, a LiteLLM gateway, or local inference? Which exact model IDs and endpoint regions are allowed? Do you require native SDKs, gateway convenience, or both?

**Recommendation:** Two generation candidates initially: preserve one existing supported route as the baseline and add one target route. Keep DashScope embeddings unchanged. Choose exact model IDs only after account/model-access checks. Avoid a full provider-by-harness Cartesian product.

**Tradeoff:** A gateway is convenient, but routing/fallback can change the actual backend. Native and gateway routes to the same named model are distinct experimental conditions.

**Blocks:** Live validation and provider-specific dependencies in Phase 4. Fake-model implementation does not require all accounts.

**Decision:** Selected 2026-10-15, reaffirmed in owner follow-up: OpenCode Go with `deepseek-v4.1-flash` or `mimo-v2.6-flash`. Owner states they checked workload eligibility; record that confirmation without requiring the same choice again. First model, account access, request-header behavior, structured/streaming capabilities, and usage reporting remain technical validation tasks. No credential value was supplied or inspected.

**Eligibility finding:** The [official Go documentation](https://opencode.ai/docs/go/) inspected on 2026-10-15 lists both IDs, but says Go is designed for OpenCode/other coding agents and that clients should send typical coding-agent traffic. The owner subsequently confirmed checking this workload's eligibility and selected Go; the planning eligibility question is therefore closed on that owner-reported basis, not replaced by an independently verified provider guarantee. Implement the documented honest client `User-Agent` and stable per-conversation `x-opencode-session` header, not impersonation or fake coding/tool traffic. Stop on an actual account/provider rejection; do not silently switch routes.

The documented Go Chat Completions base URL is `https://opencode.ai/inference/go/v1`; the documented separate Console pay-as-you-go base URL is `https://opencode.ai/inference/v1`. They are different experimental/billing routes. [Console models](https://opencode.ai/docs/zen/) list DeepSeek's paid ID and MiMo variants including a `-free` ID; verify the exact selected ID and data policy rather than silently substituting one.

### D04 — What spend and execution limits are acceptable?

**Question:** What are the maximum USD per smoke run, full benchmark, and month? What wall-clock limit and provider concurrency are acceptable? Must the runner stop at a strict cost ceiling, or are preflight estimates plus provider-side limits acceptable?

**Initial recommendation, refined by the owner:** Start with a tiny approved smoke set and manually launched broader runs. Keep generator/judge/embedding usage distinguishable. The accepted policy below uses one monthly ceiling and simple accounting, not a new billing service or mandatory per-run dollar caps.

**Tradeoff:** Reasoning models, judge fan-out, nested SDK/framework retries, and tool loops multiply cost. Unknown prices must be reported as unknown, not zero.

**Blocks:** Live runs still need verified account access, bounded request/token/time settings, and useful usage reporting or explicitly disclosed limitations. Incremental budget scope is now settled; exact Go billing reconciliation is not implemented.

**Decision:** Accepted 2026-10-15: USD 20/month ceiling with simple tracking/logging; no separate per-run dollar maximum requested. Track actual charges separately from token-priced usage estimates and included subscription quota consumption. Proposed minimal implementation adds compact per-run cost summaries to existing manifests/logs, a monthly aggregate, and manual subscription/console adjustments; no billing database or request-event ledger. Pause new paid runs at the recorded ceiling, while explicitly acknowledging unknown/in-flight/outside-repo charges. No hard billing guarantee or automatic top-up/overage is authorized.

**Scope clarification accepted in follow-up:** USD 20 covers all incremental project charges, including generation, judges, embeddings, enrichment/expansion, and metered telemetry. Existing fixed Go subscription fees are tracked separately, not counted again against the incremental ceiling; any new paid subscription/tier needs separate approval. Included Go token/quota consumption is not itself an extra cash charge. Keep Console **Use balance** spillover/auto-top-up off unless separately approved.

**Go tracking limitation:** No app integration or supported programmatic account-level usage/billing endpoint has been verified. Plan to record reported tokens and nullable quota-value estimates per run, explicitly incomplete when usage/prices are missing. Exact remaining Go quota, paid-balance deductions, and invoices require Console/manual reconciliation unless an official API is verified. Tell the owner when only estimates are available; never label quota-value estimates as exact cash spend.

### D05 — Is replacing generation enough, or is tool-driven behavior the goal?

**Question:** Do you primarily want to compare provider/framework ergonomics under the same RAG flow, or do you want a model that chooses retrieval, asks clarifying questions, and makes multiple tool calls? Which actual questions require the latter?

**Recommendation:** First compare the existing implementation with a Pydantic AI generation adapter under matched prompts/context/model settings. Make a tool-driven harness a separate Phase 5 experiment. Start with one read-only corpus retrieval tool, not four speculative medical tools.

**Tradeoff:** Native message history, query rewriting, structured answers, and agent loops change system behavior. They cannot all be introduced in the supposedly equivalent baseline comparison.

**Blocks:** Phase 5 design; does not block baseline repair.

**Decision:** Accepted 2026-10-15: follow the adapter-first recommendation. Preserve matched RAG behavior for the framework comparison; tool-driven behavior is a separately gated later experiment.

### D06 — Where should traces and experiment history live?

**Question:** Do you want hosted Logfire from the beginning, local-only telemetry first, or another OTel destination? Is W&B history actively used? May we keep W&B for aggregates but disable raw artifact uploads? Who may access these systems?

**Recommendation:** Local validation first; hosted Logfire metadata-only after explicit permission. Retain W&B historical readers and optional aggregate logging until parity is established. Keep local JSON/JSONL artifacts as the durable, vendor-independent record.

**Tradeoff:** Rich content makes debugging easier but creates a separate sensitive data store. Logfire traces are not a substitute for a versioned corpus, dataset, or run manifest.

**Blocks:** Hosted Phase 3 rollout; removal of W&B.

**Decision:** Accepted 2026-10-15: local verification first, then hosted Logfire. The follow-up explicitly expands the initial metadata-only permission to allow public/synthetic case inputs/outputs under D10. Retain disabled/local/metadata-only modes and existing history during transition; no second long-term W&B/custom-dashboard stack. Destination/access/retention still need configuration before export.

### D07 — Who judges quality, and what is the medical claim?

**Question:** Who can review evidence labels, acceptable answers, and safety cases? Are we validating an engineering demo or claiming medical suitability? Which provider/model should judge, independently of the generator?

**Recommendation:** Use reviewed source evidence plus deterministic checks, a fixed independently selected judge across candidates, and human adjudication of disagreements. Seed from the existing fixtures, but do not treat automatically bootstrapped labels as human-reviewed truth. Without qualified clinical review, label results engineering evidence only.

**Tradeoff:** A separate judge model reduces some self-preference concerns but does not establish clinical truth. A judge from a different family is useful where affordable, not a guarantee of neutrality.

**Blocks:** Credible benchmark/promotional claims; exact live judge selection. Evaluation infrastructure can use fixtures before review is complete.

**Decision:** Accepted 2026-10-15: reference-heavy, evidence-grounded engineering evaluations with no clinical-suitability claims. Evaluate whether cited passages actually support claims, not citation count alone. Clinician availability was not confirmed; do not mark cases clinically reviewed or invent expert adjudication. Independent judge model and label-review arrangements remain open.

### D08 — What is enough evidence to switch the default?

**Question:** Must Pydantic AI win quality, or is equivalent quality with better developer experience sufficient? What are acceptable quality regression margins, critical safety failures, p95 latency, time to first token, and cost per answered case? Is default promotion even required for this research repo?

**Recommendation:** Keep multiple implementations available. Require zero known critical safety regressions in the reviewed suite, complete required measurements, predeclared quality margins, and acceptable cost/latency. No automatic promotion based only on a point-estimate winner or non-significant difference.

**Tradeoff:** Not finding a statistically significant difference does not prove equivalence. Small datasets may support only provisional decisions.

**Blocks:** Phase 5 promotion/default switch. Numerical margins remain open until metric calibration.

**Decision:** Accepted objective 2026-10-15: make the repository more reusable for experiments and test practical outcomes. No numerical gate or default switch is approved yet; expose capability/configuration-driven variants without building a universal plugin platform. An exploratory comparison is useful without declaring a winner.

### D09 — CLI first, or interactive experiment selection now?

**Question:** Is YAML/CLI sufficient initially, or must you switch harnesses/providers in the browser? Will chat and evaluations run concurrently? Is local process isolation acceptable?

**Recommendation:** CLI/YAML first, a fresh subprocess per variant, separate writable run/cache paths, and a fixed read-only index for generation comparisons. The existing UI remains a browser for results. No web-exposed arbitrary model/endpoint/key selector.

**Tradeoff:** Subprocess isolation avoids much of the existing global-state coupling but needs startup overhead and careful index-write isolation. It is smaller than a general run scheduler.

**Blocks:** Phase 2 runner shape; Phase 4 interactive UI scope.

**Decision:** Accepted 2026-10-15: CLI/YAML first, fresh subprocesses and isolated writable run state; no interactive arbitrary provider/key/endpoint selector. Existing UI can remain temporary/read-only; building new evaluation-dashboard features is not a goal.

### D10 — How much compatibility do you need?

**Question:** Must current SSE clients, experiment YAMLs, local artifacts, W&B history, and direct client imports remain usable? Are short deprecation windows acceptable? May the metric semantics be versioned rather than preserving incorrect formulas?

**Recommendation:** Preserve the chat wire contract and read access to historical artifacts. Version new experiment/result semantics, provide explicit legacy translation where needed, and invalidate incompatible caches. Do not promise numerical comparability across metric versions.

**Tradeoff:** Keeping every internal import forever slows migration. Public CLI/API/artifact compatibility matters more than unadvertised internals.

**Blocks:** Phase 2 schema changes and Phase 4 cutover/removal.

**Decision:** Approved in follow-up to the 2026-10-15 interview: consolidate evaluation/tracking into Pydantic Evals + Logfire and allow public/synthetic case input/output exports. Preserve the chat contract, local reproducibility records, and archived history; no destructive bulk cleanup is authorized.

**Approved target:** Pydantic Evals is the evaluation runner, Logfire is the primary experiment/trace UI, versioned datasets/prompts/configuration stay in the repository or controlled local storage, and small local run manifests/reports/cost summaries support reproducibility/offline recovery. Freeze rather than expand custom evaluation dashboards; remove W&B/legacy artifact-service paths in a bounded Phase 4 consolidation slice after replacement evidence is demonstrated. Do not maintain two full evaluation stacks indefinitely.

**Export boundary:** Allowlisted public/synthetic evaluation inputs/outputs and associated approved case/report fields may be exported to Logfire after local policy tests pass and the destination is configured. This is not permission to upload unrelated history, whole indexes, secrets, cookies/auth headers, or real patient data. Pydantic Evals' [Logfire integration](https://ai.pydantic.dev/evals/how-to/logfire-integration/) sends per-case content, so test this approved-content mode as well as metadata-only mode.

**Implementation still needed:** Select the destination/access/retention policy, verify pinned dependency controls, and present the bounded consolidation/deprecation slice before removing old writers/dashboard/API paths. Optional hosted dataset storage has distinct API-key scopes and snapshot/version requirements; no immediate upload or dataset management service is implied.

## Decisions that can wait until their phase

| ID | Decision | Recommendation | Needed before |
|---|---|---|---|
| D11 | Embedding-provider migration and corpus expansion | **Accepted 2026-10-20: freeze current model, 768-dimensional representation, corpus snapshot, and index for initial comparisons** (see the 2026-10-20 section); reindex/embedding changes are separately named experiments | Any embedding/index experiment |
| D12 | Relationship to the approved medical co-pilot plan | Explicitly defer vision, differential generation, dosing, drug interactions, and autonomous web access from this migration; keep educational scope pending owner confirmation | Phase 5 tools or product-scope claims |
| D13 | Native message history and structured answer format | Preserve flattened-history behavior in the adapter comparison; introduce native history/structured claims as separately named variants | Phase 5 behavior changes |
| D14 | Deployment/authentication approach | Private lab first. If public demo is selected, use a trusted server-side auth/proxy design separating anonymous chat from private admin/evals; never ship a privileged browser key | Internet exposure |
| D15 | Retention, access, and deletion | Explicit durations and access policy for chat, raw local artifacts, corrupt-file backups, caches, traces, and remote artifacts; synthetic-only until chosen | Any sensitive-data handling or persistent hosted export |
| D16 | Live CI cadence and dependency extras | Offline PR gate; evaluation/provider extras compatibility job; manually dispatched paid smoke with budgets; scheduled live runs only after approval | Phase 4 live CI |
| D17 | Baseline profile and generation settings | Owner selected corrected **`baseline`** on 2026-10-16; generation/judge models and prompt/temperature/token limits still require a matched-run snapshot. Cross-encoder assets are not selected | Baseline benchmark capture |
| D18 | Provider/gateway fallbacks | Disable automatic route/model fallback during comparison; permit only explicitly named operational experiments with actual backend recorded | Live comparisons and resilience variants |

### Session decisions (2026-10-21, P4-C)

- **Judge role wired, generation untouched.** Owner decision "wire now": `judge_provider: pydantic-ai` is accepted end-to-end offline (credential `APP__LLM__PYDANTIC_AI_API_KEY`, `judge_model_{light,heavy}_pydantic_ai`, HTTPS `/v1` endpoint validation, honest `max_completion_tokens`/attempt accounting). `provider: pydantic-ai` for **generation** stays fail-closed in preflight/`effective_roles` until P4-D decides on route widening. Wiring this judge does not select it: default judge remains the generator provider (`qwen`).
- **Same-route judge is a recorded limitation, not parity evidence.** Default `pydantic-ai` judge and generator share the OpenCode Go route/model family, so matched runs cannot claim independent-judge scoring; D17 judge pinning stays open and P4-D must pin an independent judge before any quality comparison.
- **CLI selectors deliberately not flipped.** A selectable `pydantic_evals` harness needs materialized corpus/index content (D11 open), so P4-C ships a programmatic runner only. Flipping `--harness`/`--generation-implementation` without materialized inputs would create a selectable path that cannot run honestly.
- **Runner fan-out is bounded by default** (`deepeval_query_concurrency`) instead of the framework's unlimited per-case concurrency; adversarial case fan-out would multiply paid calls, so the runner — not the caller — owns the bound.
- **Session role pairing is temporary:** worker `deepseek/deepseek-flash`, reviewer `zai/glm-5.3-flash` for this run only; the standing GLM → Luna xhigh pairing is unchanged.

D11 is accepted as above. D12–D16 and D18 remain open. D17's profile choice and generator are accepted (`baseline`, Go `deepseek-v4.1-flash`); its remaining judge-ID pinning, matched settings snapshot, and capture evidence are not inferred. Recommendations in the other rows are not silently adopted.

## Pickup session decision (2026-10-24) — pydantic-ai generation preflight stays fail-closed

Owner reviewed the pickup-brief leftover item "decide whether `provider="pydantic-ai"` generation preflight/`effective_roles` is widened (currently fail-closed)" and selected **keep fail-closed**. Rationale: Stage A's accepted-incomplete live smoke ended at the baseline structured-output rejection with the adapter's structured modes unreached, so a widened preflight would advertise a generation path whose structured capability is not established; no capability availability is asserted by this record. Preflight/`effective_roles` behavior is unchanged; `judge_provider: pydantic-ai` is unaffected and remains opt-in offline. Recorded with the [offline leftovers handoff](20261024-offline-leftovers-handoff.md).

## Uncertainties to resolve experimentally, not by preference

1. Can the selected dependency versions coexist with the current Python 3.12 lockfile and provider SDKs?
2. Does the exact provider/model/region support streaming and the selected structured-output mode?
3. Can the existing prompt/message representation be reproduced without hidden instruction duplication?
4. Are usage, reasoning tokens, cached tokens, routing details, and price information available on each route?
5. Which existing fixtures remain valid against the frozen source snapshot?
6. Does a tool-driven harness help contextual follow-ups enough to justify extra latency and failure modes?
7. Does Logfire or an underlying instrumentation library capture forbidden content through attributes, exceptions, validation errors, or evaluation reports despite message capture being disabled?
8. Are observed improvements repeatable across cases, repeated runs, and route availability?

Each experiment needs a stated hypothesis, controlled variables, budget, expected artifacts, and a decision it can actually inform.

## Stop/go rules

- No keys required to answer these questions or write tests.
- Unknown data classification means no live requests or external export.
- A supplied key does not approve a spend budget or public deployment.
- Unresolved promotion criteria mean the new implementation remains opt-in.
- An unresolved later-phase decision does not block a separately approved offline baseline fix.
