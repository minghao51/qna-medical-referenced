# P4-D approvals pack — proposal only

Prepared after P4-C. **Owner approved preparing this document, not execution.** No live calls, spend, credential inspection, embeddings, downloads, hosted export, dependency changes, selector wiring, or default switches are authorized.

Sources: [pickup brief](20261021-remaining-work-pickup-brief.md), [decisions](decisions.md), [P4-D phase](phases.md#p4-d-matched-live-parity-and-ci), R05/R12–R15 in the [spec](implementation-spec.md), and [P4-C handoff](20261021-phase4c-evaluation-tasks-handoff.md).

## Stage A continuation

Owner selected Stage A using **at most $1 included Go quota value and $0 incremental cash**, with no spillover/top-up, and said “proceed.” This narrows the original A cash proposal below. The [Stage A execution addendum](20261021-phase4d-stage-a-execution-addendum.md) records the proposed wire/token bounds, code blockers and required account confirmations. No live call has run; B/C are not approved.

## Proposed bounded stages

Each stage needs its own execution permission after its blockers are resolved. Accepting a later stage's planning envelope does not unblock it.

| Stage | Proposed inputs and work | Proposed incremental cash allocation | Proposed Go quota-value allocation |
|---|---|---|---|
| A: protocol smoke | 2 fixed public/synthetic prompts plus 1 fixed small schema; 9 logical operations: text, stream, cancellation for each implementation; existing JSON-object structured output; adapter tool and native-json-schema structured output | $1 maximum admission allocation | $1 |
| B: real-RAG smoke | 1 fixed public/synthetic case, 2 generation operations | $1 maximum admission allocation | $1 |
| C: matched pilot | 10 fixed public/synthetic cases × 2 implementations = 20 generation operations; 6 required evaluator slots per output = 120 metric evaluations, **not 120 judge requests** | $8 maximum admission allocation | $5 |

These are proposed stop/admission allocations, **not price estimates or enforceable billing caps**. Combined cash allocation is $10, only if the standing $20/month incremental ceiling has at least $10 remaining. Other monthly project operations count toward the same ceiling. Go subscription fees are separate; quota-value consumption is not cash and must not be double-counted. Owner must confirm remaining cash and quota before each stage. No new subscription/tier is authorized. Spillover/pay-as-you-go and auto-top-up must be off before the first request, not verified by making that request.

Proposed stage stop clocks: A 30 minutes, B 30 minutes, C 2 hours. An interrupted/incomplete pilot is not parity evidence. Sequential generation; case concurrency at most 2 for C. The current P4-C evaluator processes metrics sequentially within each case; the separate metric-concurrency setting does not make this runner execute three metrics concurrently. Timeout/retry worst cases can exceed two hours: stop and report incompleteness rather than extend automatically.

## Exact wire/token budgets — required before execution

The logical counts above are exact proposed workload counts, not verified wire ceilings. **No stage is executable until a run-specific addendum supplies numeric caps and shows how they will be enforced.** This document does not implement enforcement.

The addendum must pin:

- Exact input/case/schema/prompt hashes and sizes; total input-token and output-token caps per role and stage, including retries and structured repair calls.
- Maximum provider requests/attempts per role and stage, separately counting transport retries, structured-validation retries, metric-internal model calls, and outer metric retries.
- Current route-specific prices or quota accounting, conservative per-role estimates, remaining monthly budget, and admission/reservation strategy. Unknown prices/usage are unknown, never zero. No combined cost estimate is possible while the independent judge is unpinned.
- Existing retry configuration: `retry.max_retries=3` means **three total client attempts**, not four. Outer metric attempts may be two; judge-client retries multiply these, and a metric may issue multiple model calls. An adapter judge adding no *second wrapper retry layer* does not mean its client has no retries.
- Explicit structured-validation retry limit and its wire impact. Do not derive a wire ceiling from logical operations alone.

## Matched route and settings

Proposed generator for both implementations: `mimo-v2.6-flash`, OpenCode Go `https://opencode.ai/inference/go/openai/v1`. Existing implementation versus opt-in `PydanticAIClient` is the experimental variable; no fallback/substitution.

Proposed shared generation values: temperature **0.7**, maximum output **2048** tokens, timeout **30 seconds**, three total transport attempts where supported. These reflect existing-client request values rather than pretending it accepts the previously suggested 0.0/512 overrides. Verify resolved wire settings before acceptance of the execution addendum. Cancellation legs stop after a nonempty delta and must not retry after content.

Unresolved run wiring must be presented for approval: existing generation uses `qwen_base_url`, also shared with embedding/qwen judge paths. Pin per-role endpoint and credential-source mapping without exposing values; prevent an embedding or judge from accidentally using the generator route. Honest User-Agent and stable opaque conversation-session header policy must be verified for both implementations; existing-client header support is not assumed. Any needed code/header/config adaptation is a separately approved bounded slice, not permission granted here.

Record unavoidable confounds: `max_completion_tokens` mapping; existing JSON-object versus adapter tool/native-json-schema shapes; structured-validation retries; stream buffering and timing; instruction placement. Same-family judge overlap is not acceptable for stage C; an independent different-family judge is mandatory. Route/schema/stream acceptance is live-only evidence. Equal stochastic text is not required.

## Stage prerequisites

**A — protocol only:** no retrieval, corpus, judge, or embeddings. Requires the execution addendum, approved synthetic inputs, account/route confirmation, safe run wiring and exact budgets. It is not blocked by D11, but is not currently executable.

**B — real RAG:** blocked on D11 corpus/index materialization with provenance and explicit query-embedding permission. Freeze the existing embedding representation and corrected `baseline` retrieval profile; no reranker/download or reindex permission. Current twin tasks retrieve separately for each implementation: budget **two retrievals** for this case, not one. Pin retrieval options and record context hashes; differing contexts invalidate a matched-context claim. A retrieve-once/reuse-context runner would require separate implementation approval. Determine the actual embedding/expansion wire fan-out before approving its numeric cap.

**C — scored pilot:** all B prerequisites plus:

1. Owner pins an independent, different-family judge: exact model ID, endpoint/route, credential source, prompts, temperature, token limits, retry settings, metric fan-out and prices. **PENDING; no availability is asserted. Without this pin C stays blocked.** Same-family scoring is not an approved substitute under the latest D17 decision.
2. Named independent review authority recorded and exercised through a verified hash-attestation manifest. No verified manifest is currently recorded; reviewed/cohort/promotion eligibility remains false. This is engineering evaluation, not clinical validation.
3. Frozen matched configuration: exact generator/judge tuples, prompts and versions, corpus/index identity, case hashes, retrieval settings, dependency-lock digest, git revision and effective role accounting.
4. Budget for **20 separate retrievals** through the current twin-task seam, not ten. Verify actual query-embedding/expansion calls; preserve per-case context hashes and report any divergence. Do not claim shared frozen context unless a separately approved path actually supplies it.

Measure quality, R07 completion/denominators, TTFT, total latency, per-role usage/cost estimates and maintenance trade-offs. Missing required measurements preclude parity/winner claims. Preserve failed/skipped/timed-out denominators.

## Stop and privacy rules

- Stop on route/account rejection; unsupported capabilities return to the owner, never downgrade or substitute.
- Stop before exceeding approved request/token/time/budget allocations where controllable; disclose in-flight/delayed/outside-repository charges. Interactive chat remains ungated: no hard monthly billing-cap claim.
- Stop on enabled spillover/top-up, unexpected charges, unavailable pricing/usage needed for admission, forbidden content, or a changed matched condition.
- Local metadata-only telemetry. Store sanitized request-shape/settings evidence, **not verbatim wire envelopes**: never authorization values, secrets, raw session IDs or stable session-header values. Hash/label approved prompts and contexts; no raw body export inferred. No `.env` inspection or secrets in agent tasks/reports.
- Generation preflight/`effective_roles` stays fail-closed for `pydantic-ai`; CLI harness selectors remain unwired and blocked on D11. No bypass is authorized. A programmatic run path and any necessary changes need explicit approval.
- Hosted Logfire setup/export, Docker smoke, asset downloads, live CI (D16), P4-E cutover and offline test leftovers remain separate work.

## Owner response template

Accept/amend/decline independently; silence or supplying a key is not approval.

```text
Planning envelopes:
A: 9 logical operations; $1 cash / $1 Go quota value; 30 min: ___
B: 1 case / 2 generation operations; $1 cash / $1 quota; 30 min: ___
C: 10 cases / 20 generation operations / 120 metric evaluations;
   $8 cash / $5 quota; 2 h incomplete-run stop: ___
Monthly cash remaining and Go quota remaining: ___
Generator model/route and proposed shared 0.7 / 2048 / 30s settings: ___
Independent judge exact ID/route/settings/prompts: ___ (blank => C blocked)
Public/synthetic input/case inventory: ___
D11 materialization and query-embedding permission: ___ (pending => B/C blocked)
Named review authority and verified manifest: ___ (pending => C blocked)
Execution addendum with numeric wire/input/output caps, per-role pricing,
  safe route/header/credential wiring, retry accounting: PENDING
Separate implementation permission if needed: NOT GRANTED / bounded scope ___
Separate run permission for a fully unblocked stage: NOT YET / stage ___
```

No whole phase is declared complete. Preparing or accepting this planning pack does not supply the missing execution evidence or permissions.
