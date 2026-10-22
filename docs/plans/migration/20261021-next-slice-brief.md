# Next slice brief — Logfire/OTel adoption, P3-C canaries, and expansion tasks — 2026-10-20

**Purpose: pickup point for a fresh agent thread.** This brief records the prepared next slice after the [admission/manifest/spans handoff](20261020-admission-manifest-spans-handoff.md), the owner's 2026-10-20 decisions, the owner-directed orchestration change, and the expanded task list. No code was changed while writing this brief; only `decisions.md`, this file, and the README/phases pointers moved.

## Owner decisions already recorded (2026-10-20, second continuation)

See the dated section in the [decision register](decisions.md). In force: named independent engineering reviewer for review authority (D07-ext); matched baseline tuple generator Go `deepseek-v4.1-flash` with an independent fixed judge from a different family, exact judge ID still to be pinned in the matched-run snapshot (D17 remainder); **proceed with the conditionally approved Logfire 5.2.0 / OTel 1.45.1 / protobuf 6.33.6 adoption slice**; hosted-export policy (dedicated project, 30-day retention, minimal access, metadata-only first, content mode only after canaries); budget posture informational/fail-closed with chat ungated; D11 embedding/index freeze.

## Starting state (verify, don't trust)

- HEAD `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`; whole tree carries large pre-existing uncommitted Phase 1–3 work — never reset/stash/clean.
- Isolated gate baseline: **1,673 passed / five warnings, zero skips/deselections**, repeated in a fresh process (`/tmp/qna-eval-admission-spans-K4T7WQ/gate-final*.log`). Statics: Ruff 330 files, MyPy 159, four import contracts, docs consistency.
- Telemetry state: owned manual spans only (request/run/case/retrieval/expansion/**embedding**/search/reranking/generation/retry incl. **stream retry transitions**/error/cancellation/evaluation); modes disabled/local/explicit-OTLP; `TelemetrySpan.finish()` supports outcomes success/error/cancelled/**retry**. Automatic SDK capture remains off.
- Budget: `paid_operation_budget_status` generalized, benchmark wrapper byte-compatible, offline diagnostics report per recorded mode.
- Review manifests: optional fail-closed hash attestations; statuses `unavailable` / `manifest_asserted_not_authenticated` / `manifest_hash_verified_not_identity_authenticated`; all eligibility guards unconditionally false.
- Reproduce the gate only via `bash scripts/verify_phase123_offline.sh` (bubblewrap; no bare pytest). New test files must be appended to its explicit inventory.

## Orchestration for this slice (owner-directed change)

- **Implementation workers: `glm-worker`** (`zai/glm-5.3-flash`, user-scope agent file `~/.pi/agent/agents/glm-worker.md`, write tools).
- **Slice reviewer: `luna-reviewer`** (`openai-codex/gpt-6-luna:xhigh`, read-only, user-scope agent file `~/.pi/agent/agents/luna-reviewer.md`).
- Parent (the new thread) owns: integration, isolated gates, statics, docs/plans, `scripts/verify_phase123_offline.py` inventory, `uv.lock`/`pyproject.toml` unless it grants T1's narrow lock ownership, and any file not assigned below. Keep the established pattern: disjoint exclusive ownership per task, subagents never run tests/imports/network, static ruff/mypy on owned files only, task briefs + reports in a fresh `/tmp` snapshot, GLM→Luna review of the slice-attributable diff, preservation check at the end (copy `/tmp/qna-eval-admission-spans-K4T7WQ/preservation.py` pattern: before-patch/status/untracked-hashes/locks, allowed-set comparison).
- Budget/privacy invariants carry over verbatim: no live calls, no hosted export execution, no credential inspection, no defaults change, eligibility guards stay false, no hard-cap claims, automatic body/exception capture stays disabled.

## Task list

### Core (approved: decisions of 2026-10-20 + presented plan)

- **T1 — Lock change (approved family only).** Add `logfire==5.2.0` with OTel `1.45.1` / protobuf `6.33.6`; provider SDK/Chroma/DeepEval versions unchanged. The lock diff must contain only this dependency family — abort and report if unrelated upgrades appear. Exclusive ownership: `pyproject.toml`, `uv.lock` (offline resolution from the already-provisioned compatibility environment; no network installs beyond what the 2026-10-19 package approval already granted).
- **T2 — Logfire as explicit-export destination behind existing config.** Keep the owned manual span model; wire Logfire into the existing `explicit` telemetry mode; verify against the pinned versions that automatic body/exception capture stays **disabled** and that lifecycle/flush timeouts are bounded (the two spike blockers). Startup without a token unchanged; local mode unchanged. Parent likely keeps `src/infra/telemetry.py` and grants narrow edits, mirroring the retry-outcome precedent.
- **T3 — P3-C offline canaries.** Synthetic secret/cookie/patient-like-ID/prompt/context canaries through spans, logs, and report/artifact paths including error and validation paths; assert absence in metadata-only mode and presence only in the approved public/synthetic-content mode. Hosted smoke stays excluded (destination setup is a separate permissioned step per the recorded policy).

### Expansion tasks (owner requested a larger slice; confirm each in the next thread's bounded plan before execution)

- **T4 — Review-polish batch** (from the 2026-10-20 GLM review's noted-not-changed list): refine non-transient embedding error codes (`INTERNAL`/`VALIDATION`, parent-only marking), deduplicate `_usage_budget_status`, compute `_review_context_parts` once per evaluation, and add the blind-spot tests (429/5xx status-code transient stream classification, empty-input embedding span, explicit outer-span usage-absence assertion, manifest edges: extra attestation keys, boolean `schema_version`, record superset/subset, missing/whitespace `query_id`).
- **T5 — D11 frozen-identity snapshot.** Extend the configuration-snapshot pattern (`20261019-baseline-configuration.json`) with the frozen embedding model, 768-dim representation, corpus and index identity, recorded as the comparison-time identity per the D11 decision. Offline reads of existing local metadata only.
- **T6 — Attested-manifest authoring helper.** Offline CLI/tool for the named review authority to construct a schema-v1 review manifest **with** attestations from a review dataset plus frozen corpus (canonical hashes, same helpers as verification). No eligibility flip, no identity claims; the authority is recorded in `decisions.md` only when actually first exercised.
- **T7 — P3-B boundary documentation.** Retention, access, deletion, and third-party processing boundaries for chat, local artifacts, traces, caches, and hosted destinations; explicit "no automatic PHI scrubbing" language; align with the recorded hosted-export policy.

### Suggested ownership map (disjoint; adjust in the bounded plan)

| Task | Exclusive files |
|---|---|
| T1 | `pyproject.toml`, `uv.lock`, lock-diff report |
| T2 | narrow grants in `src/infra/telemetry.py`, `src/config/settings.py` (telemetry section) |
| T3 | new `tests/integration/telemetry/test_content_canaries.py` (or split unit/integration), fixture files |
| T4 | `src/ingestion/indexing/embedding.py`, `src/cli/eval_pipeline.py`, `src/evals/assessment/retrieval_eval.py` (bounded), the four prior slice test files |
| T5 | new snapshot JSON under `docs/plans/migration/`, snapshot-builder script if needed |
| T6 | new `src/evals/assessment/review_manifest_tool.py` (or CLI module) + new test file |
| T7 | `docs/` boundary documents |

Conflicts to watch: T2/T4 both may want telemetry-adjacent code (keep T4 off `telemetry.py`); T4/T6 both touch `retrieval_eval.py` (T6 must only import its helpers, not edit them; if an export is needed, parent grants the one-line change).

## Exit accounting (do not overclaim)

Unchanged open exits after this slice will still include: identity-authenticated review authority (until the named reviewer's first manifest), judge-ID pinning and matched-run capture (D17 remainder), full budget admission (chat/in-flight/overage), hosted destination setup + hosted smoke, Docker/container smoke, reranker assets, live baselines, and Phase 4. The core tasks close the P3-A dependency item and the P3-C offline-canary item only.
