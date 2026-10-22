# Guard batch — GPT-6 Luna xhigh read-only review

**Status:** The two findings below were repaired in the owner-approved [2026-10-17 follow-up](20261017-review-repair-handoff.md). Separate Luna `xhigh` read-only re-review reported no actionable findings. Browser execution remains blocked; Phases 1–3 remain incomplete. The finding descriptions below record the pre-repair review, not current code.
**Owner approval:** After MiMo V2.6 Flash returned `model_coming_soon`, the owner explicitly authorized GPT-6 Luna `xhigh` instead.
**Reviewer:** Isolated OpenAI Codex subagent invoked with `--model openai-codex/gpt-6-luna --thinking xhigh`. Tools were limited to read/source inspection. No tests, builds, installs, application imports, credential inspection or application-provider calls were performed by the reviewer.
**Implementation authority:** [Guard-batch handoff](20261016-guard-batch-handoff.md). This review covers that bounded batch, not every inherited dirty-tree change or all migration phases.

## Findings

### Must fix — Selecting an incomplete run can crash the detail view

- `src/evals/artifact_service.py::load_run_payload()` projects invalid numeric measurements to `null`.
- `frontend/src/routes/eval/+page.svelte:275` still calls `data.summary.duration_s.toFixed(2)` without checking availability. The newly retained incomplete diagnostic runs can have a summary with a missing/null duration.
- `frontend/src/lib/types.ts:127–135` still declares the individual summary duration and threshold count as non-nullable. The unavailable threshold count also lacks explicit N/A formatting.
- The browser regression currently selects a mocked detail payload with a valid duration, so it does not exercise this failure path.

**Proposed bounded fix:** Coordinate nullable individual-summary types and their consumers; guard/format unavailable values as N/A. Extend the mocked selection regression with an actual incomplete/null-duration detail response. Preserve measured zeroes and individual diagnostic access.

### Warning — Numeric median measurements are not recognized

- `src/evals/artifact_service.py::_sanitize_artifact_value()` recognizes selected numeric fields/suffixes but not `chunk_length_median` or `_median`.
- `src/evals/checks/l3_chunking.py:70` emits `chunk_length_median` as a numerical measurement. A boolean persisted in that field survives the current projection instead of becoming unavailable.

**Proposed bounded fix:** Recognize this emitted numeric field (or the appropriate numeric schema), with regressions for invalid booleans and valid zero/finite values. Keep configuration/metadata and legitimate boolean findings intact; do not rewrite historical artifacts.

## Scope without actionable findings

The reviewer reported no actionable findings in the dedicated session signing/provider/single-worker changes or the isolated Logfire compatibility report. This is not security/privacy certification, approval of a dependency upgrade, or proof of live provider behavior.

Parent source inspection confirmed the unguarded duration formatting, non-nullable summary declaration and emitted median field. No application code/tests were changed during this review pass. Before recording documentation, the tracked diff was byte-identical to the captured pre-review diff.

## Evidence and remaining gates

- At the original read-only review, implementation evidence was **856 passed / 6 optional DeepEval skips** and did not cover these findings. The subsequent [repair handoff](20261017-review-repair-handoff.md) records **889 passed / 6 optional DeepEval skips**, added regressions and passing static/frontend checks. Neither reviewer ran tests.
- Browser execution remains blocked on the locked Chromium/runtime provisioning. The new null-detail regression needs execution once provisioning is approved; do not use a real backend/index/provider for it.
- Optional DeepEval compatibility, full Phase 1 lifecycle/preflight/baseline exits, Phase 2 identity/metrics/isolation/accounting, and application Phase 3 tracing remain incomplete.
- The Logfire 5.2.0/OTel/protobuf-major dependency change still needs separate review/approval before project-lock adoption. No dependency or export permission changes follow from switching coding reviewers.

**Follow-up:** The owner approved the two-finding repair slice; its code repairs and focused regressions are implemented and re-reviewed in the [repair handoff](20261017-review-repair-handoff.md). The mocked browser regressions still require approved runtime provisioning/execution. A P1-C3 worker/SDK cancellation and retry slice remains separately inspected and presented before implementation.
