# Offline leftovers handoff — pickup-brief stage 8 delivered — 2026-10-24

**Status:** slice completed and gated; review chain recorded below. Test-only + documentation; **no behavior changes anywhere**. Supersedes nothing; closes pickup-brief leftover stage 8 ([brief](20261021-remaining-work-pickup-brief.md)).

## Scope and approvals

- Owner approval (2026-10-24, in-session): "Approved A, keep fail-closed, B approve, B1" — this slice is **A** with A1 resolved as *keep fail-closed*. **B (D11 materialization)** was approved in principle (B1 slice shape) and is **not part of this slice**; B2 (corpus source) remains an open owner input.
- Session roles per standing pairing: worker `glm-worker` (`zai/glm-5.3-flash`), reviewer `luna-reviewer` (`openai-codex/gpt-6-luna:xhigh`); parent owned snapshot, gates, repairs, and docs.

## Requirements satisfied and deliberate behavior changes

- **R05/R12 adjacent, test-only:** settings-bound acceptance for the pydantic-ai adapter bounds (`src/config/settings.py:71–73`) and task-layer override pass-through (`temperature`, `timeout_seconds`) are now covered by tests. No production code changed — zero source diffs.
- **Decision recorded (A1):** `provider="pydantic-ai"` **generation** preflight/`effective_roles` stays fail-closed ([decisions](decisions.md), 2026-10-24 section). Rationale: Stage A's accepted-incomplete smoke ended at the baseline structured-output rejection; no widening is honest while that boundary stands. `judge_provider: pydantic-ai` is unaffected.
- No default flips, no CLI changes, no live calls, no exports, no data/dependency changes, no downloads.

## Files changed

- `tests/unit/config/test_settings.py` — +2 tests (exact-bounds acceptance via `APP__` env; out-of-bounds rejection). Parent repair during integration: hoisted function-level imports to module top (style only).
- `tests/unit/infra/test_pydantic_ai_client.py` — +`BlockedAfterUsageChunk` fake transport, +2 tests: stream-cancellation usage settlement; repeated sync-call lifecycle/owned-resource reuse.
- `tests/unit/evals/test_pydantic_evals_tasks.py` — +`_RecordingModelSettingsAgent` stub, +1 parametrized test (below-bounds `0.0/0.5` and upper-bounds `2.0/600.0`) asserting overrides reach the adapter call seam (`client._temperature`/`_timeout`, owned `httpx.Timeout`, `ModelSettings` at the agent call).
- Docs: [phases](phases.md) (P4-C note + leftovers paragraph), [decisions](decisions.md) (A1 record), [pickup brief](20261021-remaining-work-pickup-brief.md) (stage 8 marked delivered), this handoff.

## Tests/commands/results

- Worker additions: 6 collected tests (5 test functions; the task-layer test is parametrized ×2).
- Isolated gate `bash scripts/verify_phase123_offline.sh` ×2 fresh bwrap processes: **1,969 passed / 5 warnings** both runs, pre- and post-repair (progression 1,963 → 1,969; +6 exactly the new tests; 0 skipped, 0 deselected).
- Statics: Ruff check clean; Ruff format **346 files** already formatted; MyPy **164 `src` files** clean; import-linter **4/4 contracts kept**; docs consistency re-run after this handoff (see gate log note in the session record).
- Dependency locks untouched: `uv.lock` SHA-256 `7d63f1ce0a02249c2efe7c2ef3de1c37c3eb1d770d278a7ad5845865eb8d6499` (identical to the owner-approved P4-B pin digest).
- Snapshot before changes: `/tmp/qna-pickup-a-20261024/snapshot.txt` (HEAD `4629216`, clean `status -uall`, lock digest, no untracked sources).

## Intended `--harness` selector shape (docs-only record, NOT wired)

Recorded per the approved slice item "record the intended `--harness` selector shape without wiring it before D11". This is the **intended shape only**; wiring requires materialized D11 corpus/index content plus its own bounded approval:

- The evaluation CLI gains `--harness {legacy,pydantic_evals}` (default `legacy`) and surfaces `--generation-implementation {existing,pydantic_ai}` (default `existing`), composing with the existing experiment YAML/CLI precedence (explicit flag > experiment override > profile > settings).
- Both selectors **fail closed** with an explicit actionable error (frozen corpus/index not materialized — D11 unresolved) whenever D11 content is absent; no silent fallback to `legacy`, no partial runs.
- `legacy` behavior, artifacts, and reports are byte-unchanged; `pydantic_evals` selection uses the P4-C programmatic runner path (`build_dataset` → `run_dataset` → `project_report`/`write_report`) with the same frozen inputs and normalized result contract.
- Selector identity enters run manifests (R06) so legacy/evals results are never merged or compared blindly.

## Review chain

- Worker report preserved verbatim in the session record; worker confirmed: only the three owned files touched; only read/grep commands plus read-only `ruff check`/`format --check` on owned files; no tests/imports/network; no product-code findings.
- Luna review (`openai-codex/gpt-6-luna:xhigh`, read-only, 2026-10-24): contract verification PASS on all four seams (settings bounds; `record_response`-on-completion settlement in `pydantic_ai_client.py:314–343` + `usage.py:178–192`; persistent-agent sync reuse; task→`generate_answer_case`→`a_generate` override pass-through); scope/privacy PASS (exactly 3 test files + 4 docs); **one P2, one P3, verdict REPAIRS REQUIRED**.
  - **P2 (repaired by parent):** cancellation test used a 50 ms sleep instead of proof that the usage chunk was consumed before cancellation. Repair: `BlockedAfterUsageChunk` now sets `usage_chunk_consumed` when the consumer requests the item *after* the usage chunk (async-generator resume semantics = deterministic proof), and the test awaits that event instead of sleeping.
  - **P3 (repaired by parent):** comment wrongly claimed each `run_sync` spins its own event loop (the locked dependency's `run_until_complete` reuses the current open loop). Comment corrected; loop-affinity coverage explicitly declared out of scope.
  - Reviewer blind spots recorded: sync-reuse is proven through `MockTransport`, not real connection-pool/loop-affinity behavior; the reviewed gate execution itself was not independently re-run by the reviewer (parent gate logs above are the evidence).
- Post-repair gates: **1,969 passed / 5 warnings ×2** fresh processes; Ruff check/format clean (346 files). Repairs touch only `tests/unit/infra/test_pydantic_ai_client.py` (parent-owned repair, no re-review requested for comment + deterministic-wait test mechanics; no product code involved).

## Rollback

Revert the three test files (purely additive) and the four doc files. Nothing runtime-visible exists to roll back; no cache/schema/artifact effects; no data touched.

## Remaining blockers / next slice

- **Stage 1 (D11 materialization)** — approved in principle (B1); waiting on owner B2 corpus-source decision (canonical sources exist in `config/sources.yaml`: 58 public web pages + 13 public PDFs + the missing local `LabQAR/reference_ranges.csv`; the machine currently holds zero corpus bytes and all Chroma collections are empty) and B3 identity confirmation; embedding spend estimate follows corpus fetch, before any paid run.
- Remaining pickup-brief stages 2–7 and 9 unchanged; P4-E remains dormant.
