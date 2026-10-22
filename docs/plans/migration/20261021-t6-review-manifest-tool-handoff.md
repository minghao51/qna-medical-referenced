# T6 attested-manifest authoring tool handoff — 2026-10-21

**Purpose: closing record for the confirmed task T6** of the [next-slice brief](20261021-next-slice-brief.md), following the [T5 handoff](20261021-t5-d11-snapshot-handoff.md). Parent + one `glm-worker` (one repair round) + `luna-reviewer` (review → repairs → **closed**). T7 remains unconfirmed.

## What landed

- **`src/evals/assessment/review_manifest_tool.py`** — offline schema-v1 review-manifest authoring tool for the D07-ext named review authority. Single source of truth by **import, not reimplementation**: canonical hashes, qrels binding, attestations, schema validation, manifest reading, and authority status all route through the real verification helpers in `retrieval_eval.py`/`orchestrator.py` (both strictly import-only, per the brief; no export grants were needed). Fail-closed authoring: unbound evidence passages refuse naming the case (never silently certifying empty qrels), duplicate case IDs / corpus hash mismatches / malformed declared evidence (present-but-non-list, including unanswerable cases — intentionally stricter than the verifier) / invalid source-hash claims (explicit `null` included) / empty IDs / oversize / symlinked / duplicate-key inputs all refuse with fixed one-line reasons and write nothing. Output can never alias an input (resolved-path + dev/ino guard, covering hard links and symlinks); the write is atomic and deterministic (sorted canonical JSON, no timestamps/env capture), and the post-write check requires parsed read-back **and** byte-digest equality — mismatch deletes the artifact and exits non-zero. No identity claims: attestations authenticate content consistency only; authoring flips no eligibility flag (D07-ext framing in the module docstring; the authority name/scope/date is recorded in `decisions.md` by the owner when first exercised).
- **`tests/unit/evals/test_review_manifest_tool.py`** — 27 tests: end-to-end author → `_read_review_manifest` → schema → `_review_context_parts` → authority status `manifest_hash_verified_not_identity_authenticated`; byte determinism; closed key set; alias preservation (direct, hard-link, symlink); read-back tamper deletions (different manifest / wrong digest); pre-write self-check no-output; unbindable/duplicate/malformed refusals; unanswerable determinism; fingerprint pass-through; no-identity shape contract.
- One inventory line in `scripts/verify_phase123_offline.py` (parent-owned).

## Review chain

Initial review: **approve-with-repairs** (P2 output-aliasing an input; P2 post-write check blind to a valid-but-different manifest — `manifest_id` mutable undetected; P2 present-but-non-list `evidence_passages` silently taking the empty-qrels path; P3 explicit-null source-hash claim accepted). Repair round closed all four plus both test blind spots; closure verdict: **T6 CLOSED**. The two non-blocking edge-coverage gaps the closure noted (unanswerable + non-list combo, symlinked output alias) were closed parent-owned with two further tests, green under execution. All verdicts verbatim in `/tmp/qna-eval-t6-manifest-Xq3KvA/review.md`.

## Verification (snapshot `/tmp/qna-eval-t6-manifest-Xq3KvA/`)

- Gate via `scripts/verify_phase123_offline.sh` only: **1,787 passed / 5 warnings ×2 fresh processes** (`gate-final*.log`; progression 1,760 → 1,776 → 1,785 → 1,787; no intermediate failures — both worker rounds passed the parent gate first try).
- Statics green: Ruff/format 336 files, MyPy 160 src files, 4 import contracts, docs consistency.
- Preservation OK (touched files exactly: tool, tests, one inventory line, docs pointers; locks identical).

## Residuals & exits (do not overclaim)

- **No authority has exercised the tool.** Authoring a manifest is not review: eligibility (`reviewed_evidence_eligible`, cohort, promotion) stays false until the first manifest **from the authority recorded in `decisions.md`** verifies at execution time, and that recording is an owner action at first exercise. Content hashes authenticate supplied-content consistency only — never reviewer identity, qualification, or clinical endorsement (D01/D07 unchanged).
- The tool does not classify or scrub content; the frozen sources it embeds must be permitted public/synthetic inputs under D02.
- Inherited and unchanged: T4's unthreaded orchestrator `_review_context_parts` calls (this tool does not touch the orchestrator), review authority exercise, D17 judge pinning, budget admission, hosted setup/smoke, Docker smoke, reranker assets, live baselines, Phase 4, and **T7**.

## Next thread pickup

Confirm T7 (P3-B boundary documentation) per the [brief](20261021-next-slice-brief.md) — docs-only slice (retention/access/deletion/third-party boundaries for chat, local artifacts, traces, caches, hosted destinations; explicit "no automatic PHI scrubbing"; aligned with the recorded hosted-export policy). Starting state: HEAD `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`, dirty tree untouched, gate 1,787 ×2, statics as above.
