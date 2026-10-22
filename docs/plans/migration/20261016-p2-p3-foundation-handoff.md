# P2/P3 — Offline role/completeness and existing-export foundation

**Status:** Bounded offline implementation; neither phase is complete. Phase 1 remains incomplete.
**Continuation:** The later approved [P2-B1 handoff](20261016-p2-b1-handoff.md) supersedes this slice's run/cache-reuse behavior with fresh attempts, bounded source provenance and atomic artifacts. The implementation/evidence below describes the earlier foundation, not full P2-B completion.
**Approval:** Owner requested “procede with phease 2 and 3” and OpenAI Codex GPT-6 Luna implementation subagents. The presented first slice covers independent judge-provider selection, explicit answer-suite activation, required measurement checks, winner eligibility, and existing W&B/UI hardening. Integrated comparison gates remain sequential; this does not approve live calls, uploads, installs/upgrades, data migrations, a provider/default switch, or Phase 4.
**Prior authoritative isolation/handoff:** [P1-C2](20261016-p1-c2-handoff.md). Preserve all earlier dirty/untracked work and disclosed database side effects.

## Continue from here

1. Read `AGENTS.md`, this handoff, then the overview/checklist/decisions and prior C2 handoff. **HEAD alone cannot reproduce this working tree.** Keep all tracked and untracked changes; do not reset, clean, stash away, or overwrite earlier work. Transfer the entire dirty tree if changing workspace.
2. User approval covers offline Phase 2/3 implementation, not automatic completion or live/dependency/export access. Preserve Phase 1's outstanding gates. Use explicit `--model openai-codex/gpt-6-luna --thinking xhigh` for requested subagents; existing agent definitions pin other models.
3. Reproduce the expanded isolated gate below, never bare pytest. The durable runner needs no temporary scout reports/session files.
4. Recommended next bounded slice: P2-B's versioned source/index/artifact identity and cache contract before further benchmark/tracing integration. Inspect the exact seam and present the bounded plan under `AGENTS.md`; retain the separate full Phase 1 exit and Logfire-dependency gates. Do not start a live pilot or claim the existing metrics/identities are trustworthy merely because this regression gate passes.

## Implemented boundaries

### Role selection and activation — partial P2-A

- `src/config/settings.py` adds `APP__LLM__JUDGE_PROVIDER`: `qwen`, `gemini`, or `litellm`. Omitted/`None` explicitly inherits the generation provider for legacy compatibility; generation defaults are unchanged. Existing provider-specific judge model/settings and credentials remain in use.
- `src/evals/deepeval_models.py` selects the independent judge provider, rejects unknown selections, and validates only its selected credential by supported nested setting name. LiteLLM judge calls receive an explicit key rather than mutating credential environment state.
- Answer evaluation is enabled only when explicitly requested, not by the presence of a DashScope key. Selected generator/judge credentials are checked independently; fake Gemini tasks do not need a DashScope generation key. This does not remove the real embedder/enrichment roles' DashScope requirements.
- The manifest configuration records selected generator/judge provider/model/settings without keys. These selections and the measurement marker affect the existing run signature. This is **not** the complete R05/R06 effective snapshot or identity contract.

### Measurement contract — partial P2-C

- New configuration/manifests/summaries carry `measurement_contract_version: 1`; this versions measurement semantics, not the outstanding full artifact/cache/index schema.
- Execution status (`completed` when finalization is reached), measurement (`complete`/`incomplete`), and quality gate (`passed`/`failed`/`incomplete`) are distinct. Legacy summary `status` is `ok` only for a completed measurement and passed gate; quality failures remain `failed` even in exploratory mode.
- Active thresholds are required by default. Missing, invalid, non-finite, or boolean answer scores cannot pass. A missing optional diagnostic must explicitly declare `required: false`. The declared boolean L5 dimension check retains its boolean behavior.
- Disabled answer evaluation is not applicable and its thresholds are excluded. An explicitly requested but disabled/skipped/errored/unscored suite is incomplete. Empty selected datasets cannot pass.
- Selected-case coverage is currently fixed at 100%, recorded in the summary. Answer summaries retain expected case counts, fully measured cases, failed cases, per-metric measured/error counts, and partial-case quality. Generation/metric-construction failures do not discard other cases; cancellation still propagates without writing successful caches.
- Failed/non-finite/boolean metric cache results are not reused as valid successes. Fresh assessment attempts receive separate answer cache directories beneath their own output directory. Complete run-cache reuse still exists and remains unsuitable as fresh benchmark timing until P2-B/E are implemented.
- Strict direct/config/parallel CLI runs return nonzero for incomplete measurements even with no numerical failures. Exploratory incomplete runs may return zero but retain `incomplete` artifacts/status; quality failures return nonzero.
- Addition winner selection requires the new completed/complete/passed contract and a finite primary score. Ablation selection validates the parent assessment and positive measured counts/finite candidate metrics before launching winner-only answer evaluation. No eligible candidate means an explicit error, not an invented baseline winner. This is not proof of cross-run comparability or promotion eligibility.
- Existing artifact filenames/readers remain usable; legacy artifacts are not rewritten or upgraded into the new measurement contract.

### Existing export/UI hardening — partial P3-B, not Logfire tracing

- W&B raw-artifact defaults are off in both normalization and execution. Invalid tracking modes do not silently select online export; booleans must be real booleans in normalized config.
- The existing W&B call boundary forwards only fixed-name structural scalar metadata and allowlisted finite aggregate metrics. Arbitrary experiment/manifests, freeform names/notes/tags, dynamic category/source-derived keys, SDK exception details and returned SDK run identifiers/URLs are omitted.
- Explicit legacy raw-artifact opt-in remains available with a warning. It is an **unsafe-content compatibility path**, not a certified public/synthetic-content mode or authorization to upload. Existing files that explicitly request it retain that behavior.
- Fake-SDK tests inspect explicit outgoing config/metrics and error returns/logs using synthetic canaries. They do not certify W&B's automatic console/system/code/environment capture or actual hosted behavior. Do not infer end-to-end privacy from these tests.
- Frontend confidence text/tooltips/help now call the score an uncalibrated retrieval/pipeline diagnostic, not a probability of medical correctness. The calculation and wire format are unchanged.
- Metric-name lookup no longer imports NumPy/SciPy eagerly. Statistical helpers lazily require their dependencies and fail actionably when unavailable. No statistical package was installed or inference performed.

## Verification

- Before-fix new completeness selection: **18 failed, 9 passed**. It reproduced missing-metric bypass, non-finite acceptance, implicit activation, false success, and case-loss failures.
- Final expanded isolated gate: **763 passed, 6 skipped, 0 deselected**. Six skips require unavailable optional DeepEval: one app-security case, three medical-metric cases and two synthetic-generator cases. This does not establish real optional DeepEval API compatibility.
- Ruff lint/format: **22 touched source/test files passed**. Source MyPy: **154 files passed**. Import-linter: **four contracts kept**, zero broken. Docs consistency and `git diff --check` passed.
- Seven existing warnings remain: two protobuf import deprecations, one Requests dependency-version warning, and two each for deprecated GET/DELETE history routes. No dependency changes were made to silence them.
- Read-only GPT-6 Luna `xhigh` integration review found boolean answer-score acceptance. The implementation now rejects boolean scores/means/cache entries, explicitly preserves the L5 boolean check, and adds regressions. The reviewer did not run tests; parent execution is the test evidence.
- Three disjoint GPT-6 Luna `xhigh` implementation subagents covered judge selection, W&B/UI hardening, and winner selection. Parent integrated/reviewed changes and ran all gates.
- Frontend dependencies are absent. No frontend install/build/type-check/browser validation is claimed; frontend changes are presentation-only and still need their normal provisioned check.

### Reproduce the expanded isolated gate

Run from the repository root. The C2 runner remains the authority for pre-import temporary history/rate-limit/Chroma storage, synthetic credentials and denied Python network/repository SQLite access. Extend its selection, not its isolation:

```bash
uv run --offline --no-sync python - <<'PY'
from pathlib import Path
handoff = Path('docs/plans/migration/20261016-p1-c2-handoff.md').read_text()
runner = handoff.split(
    "```bash\nuv run --offline --no-sync python - <<'PY'\n", 1
)[1].split('\nPY\n```', 1)[0]
exec(compile(
    runner.split('raise SystemExit(pytest.main([', 1)[0],
    '<C2-isolated-expanded-runner>', 'exec',
))
extra = ['tests/unit/evals/', 'tests/unit/experiments/']
targets = [
    target for target in targets
    if not any(target.startswith(directory) for directory in extra)
] + extra
raise SystemExit(pytest.main([
    '--no-cov', '-q', *targets,
    '-m', 'not live_api and not live_openrouter and not e2e_real_apis '
          'and not network and not deepeval',
]))
PY
```

The new focused selection is the five files `test_measurement_completeness.py`, `test_judge_roles.py`, `test_winner_eligibility.py`, `test_wandb_export_policy.py`, and `test_metric_dependency_boundary.py` in their existing unit subdirectories. Use the same isolation prefix before collection. CLI strict-mode regressions are in `tests/unit/cli/test_eval_pipeline_cli.py`.

## Remaining work / stop conditions

- Phase 1 SDK/request cleanup, retry coordination, non-commit worker ownership, setup/security and corrected baseline capture remain open. This slice does not remediate or conceal them.
- P2-A: full implementation/task selectors, presence-aware experiment precedence, actual resolved snapshot passed to execution, all retained role validation, owned run-level generator/judge reuse/closure, and bounded nested retries.
- P2-B: complete versioned schemas, source/dirty-content/index snapshots, complete semantic fingerprints, atomic caches and explicit fresh/replay semantics. Current complete-run reuse is not a verified benchmark; do not use it as new quality/performance evidence.
- P2-C: full eligible/excluded/subpopulation coverage policy, retrieval-case failure preservation, and remaining report/dashboard mappings. Existing proxy/high-confidence denominators are not repaired by the selected-case coverage check.
- P2-D/E: canonical frozen reviewed cases, independent qrels and correct metric formulas, actual emitted chunks, verified index reuse/read-only copies, subprocess attempt isolation, matched descriptive comparisons and controlled timing.
- P2-F: role usage, nullable costs, deduplicated UTC-month summaries/manual reconciliation. Preserve the USD 20 incremental monthly ceiling; existing Go subscription remains separate. No paid workload was launched.
- Phase 3: approved pinned Logfire/OTel dependency slice, disabled/local/export modes, correlated baseline spans, bounded lifecycle, policy at **every** automatic/manual export boundary, comprehensive canaries, access/retention controls, browser trace policy and optional explicitly approved hosted smoke. W&B fake-payload checks are not a replacement.
- Reviewed pilot evidence, real optional DeepEval compatibility, provider capability/billing access, frontend checks and hosted validation remain blocked/unverified as applicable. Do not treat optional skips or synthetic fixtures as measured medical quality.

## Identity and rollback

HEAD remains `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`; `uv.lock` SHA-256 remains `10a308c18f3078abcade42024541464d3623d730af532b5f777f9298a0f7f8f5`. All work is uncommitted, including earlier phases and this handoff/new tests. No credential inspection, application-provider calls, exports, downloads, dependency changes, stored-data migration or cleanup was performed. Execution used synthetic fixtures and temporary storage. Earlier P1-A1 default-directory side effects remain disclosed in the original handoffs and untouched.

Rollback only this slice's role/completeness/export/UI additions and associated tests/docs, preserving all prior edits/untracked files. Do not operationally restore missing-metric success or unrestricted export to make a benchmark pass. No stored-data rollback is needed or authorized.
