# Phases 1–3 — Historical pause and resumed continuation

**Status:** The owner resumed the approved bounded batch in the next thread. **Phases 1–3 remain incomplete.**
**Current implementation authority:** [Approved Gemini HTTPX fix](20261017-gemini-httpx-fix-handoff.md): the generation-adapter transport finding is repaired, with 1,319 passed / 6 optional DeepEval skips and no actionable scoped Luna re-review findings. It follows [C3a](20261017-p1-c3a-handoff.md), the [reader/UI repair](20261017-review-repair-handoff.md) and [guard batch](20261016-guard-batch-handoff.md). Broader workers/direct judge SDK compatibility remain open. Browser execution remains blocked; Logfire research is not tracing/adoption.
**Historical record:** The remainder below records the documentation-only pause and its approved next scope as captured before resumption. Its “not implemented yet” descriptions are historical, not the latest delivery status. Preserve the [P2-B1](20261016-p2-b1-handoff.md), [P2/P3 foundation](20261016-p2-p3-foundation-handoff.md) and [P1-C2](20261016-p1-c2-handoff.md) evidence and dirty tree.

## Resume in another thread

1. Read `AGENTS.md`, this file, the [decision register](decisions.md), [overview](README.md), [phase checklist](phases.md), [implementation specification](implementation-spec.md), [environment/authorization guide](environment-and-credentials.md), and the preceding handoffs.
2. **Preserve the entire dirty/untracked tree.** HEAD alone does not reproduce the work. Continue in this working tree or transfer all tracked and untracked work together. Do not reset, clean, stash away, overwrite prior work, reindex existing data or remove previously disclosed side effects.
3. Confirm the owner is resuming execution. The bounded batch below was presented and approved; the last instruction pauses it here rather than authorizing immediate background execution. Inspect relevant current files before edits and present any scope extension for approval under `AGENTS.md`.
4. Use explicit `--model openai-codex/gpt-6-luna --thinking xhigh` for requested subagents. Existing agent definitions/fallback chains select other models; do not rely on defaults. Parallel implementation ownership must be disjoint, with parent integration, isolated tests and read-only review.
5. Reproduce the isolated gate below before changing code. Keep real provider calls, hosted export, corpus/model downloads, data migrations, public deployment/default-harness switches and Phase 4 separately gated.

Suggested next-thread request:

> Read AGENTS.md and docs/plans/migration/20261016-phases-1-3-resume-handoff.md. Resume the approved bounded security/provider/worker and history/API/UI batch, preserving all dirty/untracked work. Use OpenAI Codex GPT-6 Luna at xhigh for subagents. D17 selects baseline for comparison; package permissions and remaining exclusions are recorded in the decision register. Phases 1–3 remain incomplete.

## Owner decisions and permissions now recorded

- **D17: corrected `baseline` for now.** `baseline_cross_encoder` and its reranker assets are not selected. This settles the comparison-profile choice, not exact generation/judge models, prompt/request limits, a frozen benchmark configuration, live execution, or a provider/harness default switch.
- The built-in named `baseline` profile is loaded by `src/rag/production_profile.py` from the `baseline` variant in `experiments/v1/comprehensive_ablation.yaml`. Do **not** assume the separate file `experiments/v1/baseline.yaml` is an identical resolved condition merely because its name matches. Freeze/record the actual effective settings before comparison.
- Runtime provider/profile defaults were **not changed** by this documentation update. Existing configured `baseline_cross_encoder` behavior is not proof that D17 has been applied to an execution. Apply the selected comparison condition explicitly when that bounded implementation is resumed.
- Owner approved **frozen-lock frontend dependency installation** for validation and **package checking/installing for the bounded Logfire compatibility spike**, including necessary package-registry access. No installation was performed here. Resolve exact versions/APIs in isolation, document the proposed pin/transitive effects, and review any project-lock change before adopting tracing. No broad SDK upgrade or Phase 4 package migration is inferred.
- Those permissions do not authorize real generation/judging/query embeddings, hosted Logfire/W&B export, real corpus/reindex work, NLTK/reranker/model-asset downloads, data cleanup/migration or automatic paid runs. Existing USD 20/month incremental project ceiling and separate Go subscription policy remain unchanged.
- D07 review/judge arrangements, D08 promotion margins, D15 hosted destination/access/retention, the remaining D17 matched generation settings and other open decisions remain open. Never turn synthetic labels into reviewed gold or coding-agent OAuth into application credentials.

## What happened in this continuation

- Three read-only GPT-6 Luna `xhigh` scouts inspected remaining Phase 1, 2 and 3 gates. Their actionable findings are incorporated below; no temporary scout/session report is required to resume.
- Latest prior parent verification in this thread reproduced the current isolated gate: **819 passed, 6 skipped, 0 deselected**, with the seven inherited warnings. All six skips require unavailable optional DeepEval; this is not optional API-compatibility evidence. No backend/frontend test rerun or new-feature acceptance is claimed for this final documentation-only step.
- Updated `decisions.md`, `README.md`, `phases.md` and `environment-and-credentials.md` to record the selected baseline, package permissions and bounded batch. This handoff and index pointers complete the documentation-only continuation.
- Three implementation/spike subagents were then launched but **stopped immediately when the owner requested documentation only**. They had no child processes at the stop check; all three exited. **No new implementation files or package environments were created.** Do not claim their proposed work was delivered or reviewed.
- Verified the tracked working-tree diff was byte-identical to the captured pre-batch diff before documentation index updates. Frontend `node_modules` remained absent; no compatibility-spike environment was created. Both lockfile digests remained unchanged. Existing dirty/untracked work remains present.

## Approved bounded batch at the pause — subsequently resumed

### A. Phase 1: session signing, provider selection and worker topology

Inspect `src/config/settings.py`, `src/app/session.py`, `src/app/security.py`, `src/infra/llm/__init__.py`, `src/cli/serve_production.py`, `.env.example` (template only), and related tests.

- Current `_get_signing_key()` uses the first plaintext API key or predictable environment name; JSON-only caller auth does not provide a dedicated signing secret. Add a dedicated secret setting, require a sufficiently long nonblank configured secret outside development, and never derive HMAC keys from caller API keys/environment names. A process-random development fallback may remain, with explicit restart/cookie consequences. Do not delete/migrate historical messages or retain insecure cookie acceptance for compatibility.
- Test missing/short/blank and valid synthetic secrets for plaintext and JSON caller-key configurations, tampering/legacy signatures, API-key independence and value-free errors. Record the supported new setting name only when implemented.
- `LLMConfig.provider` is an unrestricted string and `get_client()` silently falls back to Qwen. Reject unknown values both in validated configuration and at the client factory edge, retaining existing supported provider/default selections.
- Production CLI accepts arbitrary `--workers`; file history locking/admission remains process-local. Reject unsupported worker counts before starting Uvicorn; retain the documented single-worker topology. Do not change bind defaults or implement cross-process history storage in this slice.
- Add focused tests, extending existing production fixtures with synthetic settings rather than bypassing security validation. Preserve all prior streaming/session/history assertions.

These fixes do not finish P1-D setup/preflight/container parity, P1-C request/SDK cleanup/retries, or baseline capture.

### B. Phase 2: history/API/UI comparability repair

Inspect `src/evals/artifact_service.py`, the history endpoint in `src/app/routes/evaluation.py`, `frontend/src/lib/types.ts`, `frontend/src/lib/components/TrendingTab.svelte`, related evaluation helpers/tests.

- Current projected records are explicitly `comparable: false`, yet `aggregate_history_summary()` averages quality/latency/duration and the UI plots all runs. This is the disclosed B1 review finding, **still unfixed**.
- Until a verified comparison cohort exists, return unavailable (`null`) aggregates, not zeroes; retain run/source counts and individually readable diagnostic records. Do not grant comparison eligibility from an arbitrary persisted boolean or merely from equal source/config hashes.
- Coordinate nullable TypeScript/API fields, clear non-comparability notices, N/A formatting and removal/suppression of invalid historical trend comparisons. Preserve individual selection/filtering and legacy read access; do not rewrite historical artifacts or build a new dashboard/cohort framework.
- Missing/non-finite/boolean metric values must not masquerade as measured zeroes or break JSON responses. Add backend and mocked-browser regressions, including legacy/unsupported/incomplete/failed records, empty history, preserved counts and unchanged artifact bytes.
- Frontend package installation is approved from `frontend/bun.lock`; run type/build checks after provisioning. Browser tests must use synthetic/mocked API traffic, not a real application backend/index/provider. Existing browser cache presence was noted but **not validated**; do not claim browser checks or download assets implicitly.

This repairs the history presentation boundary, not full P2-C measurement coverage or cross-run comparability.

### C. Phase 3: package/API compatibility spike, not tracing adoption

Inspect `pyproject.toml`, `uv.lock`, logging/lifespan/request-ID boundaries, export guardrails and official pinned SDK documentation.

- No Logfire or direct application OTel dependency is declared. The lock contains transitive OTel API/SDK/OTLP **1.27.0** and semantic conventions **0.48b0**, not an application tracing contract.
- Use isolated scratch environments/copies for exact Logfire pin/API resolution; do not mutate the project's environment or lock while merely probing candidates. Include declared optional evaluation-group constraints so a DeepEval/Chroma conflict is not hidden. Do not install Pydantic AI/Evals or perform blanket SDK upgrades as this spike.
- Package-registry access is approved; runtime SDK probes must deny network and use no real hosted token. Establish actual supported disabled/no-send, console-off, local/in-memory exporter, correlation, exception/content-control and bounded shutdown APIs. Consult current official docs/package metadata rather than assuming examples apply to an arbitrary latest version.
- Record exact versions, dependency effects, commands/results and remaining blockers in a durable report before any application tracing slice. No candidate was resolved or installed in this thread.
- Actual local tracing/configuration, correlated request/retrieval/generation/retry/cancellation/run/case spans, comprehensive canaries and lifecycle/exporter-failure tests remain pending. Do not build a fake homegrown tracing framework just to mark the phase complete.

Existing request logs can contain auth/rate-limit identifiers, and the optional browser `PipelineTrace` includes query/expanded terms/document contents/context previews. Do not forward either wholesale. Existing W&B allowlists/raw-artifact opt-in warnings remain in force. Fake payload tests do not certify automatic SDK capture or hosted storage; D15 destination/access/retention and any hosted smoke remain separately gated.

## Later required slices and completion boundaries

After the bounded batch, inspect and propose the next concrete slice rather than treating the following list as approval for arbitrary rewrites:

- **P1-C3:** admitted non-commit history/search/rerank workers must settle before cancellation releases session ownership; test repeated asyncio/AnyIO cancellation without inventing thread termination or hard drain deadlines. Coordinate nonstream SDK/wrapper retries, permanent/transient errors and neutral logs. Native Gemini inner transport release remains unverified; public SDK behavior/compatible upgrade must be established, not privately patched or asserted from fake close hooks.
- **P1-D/exit:** value-free no-network preflight, role/extras/local-asset checks, local/container config parity and supported private-lab setup docs; selected corrected baseline snapshot and full offline/lifespan/static evidence. Do not infer live quality or provider access from wiring tests.
- **P2-A/B:** one effective snapshot passed to execution and manifests, complete role/prompt/rubric/dataset/corpus/output/source/lock identity, actual aligned Chroma readback and build spec, supported frozen snapshot/copy/write-exclusion semantics. Readback hashes or matching before/after reads alone are not a consistent snapshot under concurrent writers. Remote verification must fail explicitly if unsupported. Keep semantic reuse/promotion disabled until actually verified; use direct temporary synthetic stores in tests, not production getters.
- **P2-C/D:** preserve retrieval-case failures and selected/eligible/excluded/subpopulation denominators; version metric formulas against independent qrels/evidence, with hand-calculated tests for irrelevant same-source text, duplicates, missing judgments and unanswerable cases. Frozen reviewed pilot/calibration remains reviewed or explicitly blocked, never invented.
- **P2-E/F:** fresh subprocess variants with isolated writable outputs/history/caches/indexes and verified frozen inputs, actual emitted L3 chunks, controlled descriptive timing boundaries; role usage, nullable prices/cash versus included Go quota, deduplicated UTC-month summaries/manual reconciliation. No new billing database or automatic paid campaign.
- **P3/exit:** after compatible dependency approval/adoption and prerequisite identities/lifecycle, implement disabled/local/explicit-export behavior, all-boundary allowlists/canaries and bounded lifecycle. Public/synthetic evaluation-case export permission is not blanket interactive-chat/history/index export. No phase completion or hosted-privacy claim from synthetic fixtures alone.

## Durable verification and identity

Use the exact [B1 isolated reproduction guidance](20261016-p2-b1-handoff.md#durable-isolated-reproduction), which points to the [foundation expanded runner](20261016-p2-p3-foundation-handoff.md#reproduce-the-expanded-isolated-gate) and the C2 pre-import storage/network isolation. No `/tmp/qna-*` scout reports, process IDs, session files or local prompts are needed. The current selection yields the inherited **819 passed / 6 skipped** evidence, not tests for the unimplemented next batch.

After implementation, extend that isolated selection with the actual new session/provider/CLI tests and existing `tests/unit/app/test_evaluation_routes.py`; the full `tests/unit/evals/` selection already covers new history-comparability tests placed there. Do not run bare pytest or merely drop failing optional tests to claim completion. Frontend checks require the newly approved installation and must be reported separately from Python checks.

- Project HEAD: `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`.
- `uv.lock` SHA-256: `10a308c18f3078abcade42024541464d3623d730af532b5f777f9298a0f7f8f5`.
- `frontend/bun.lock` SHA-256: `c524e8e748022723e3eb257ebbf7420ae734d22990ee53415ed882941ce82eaa`.
- All implementation/handoff work remains uncommitted, including untracked tests/docs. No project commit, package installation, live application call, hosted export, dependency-lock change, provider/profile-default switch, real-data migration or stored-data cleanup was performed in this documentation continuation.

Documentation verification passed: `bash scripts/check_docs_consistency.sh`, `git diff --check`, and local link/anchor/code-fence/whitespace checks across all seven updated documentation files. All non-documentation tracked diffs remained unchanged; all pre-existing dirty/untracked status paths remained present, with only documentation paths added. Both lockfile digests remained unchanged. These are documentation/preservation checks only; they do not complete any migration phase.
