# T4 review-polish handoff — 2026-10-21

**Purpose: closing record for the confirmed expansion task T4** of the [next-slice brief](20261021-next-slice-brief.md), following the [Logfire/P3-C handoff](20261021-logfire-canaries-handoff.md). Parent + two `glm-worker` tasks (A: embedding; B: pipeline/eval/tests) + `luna-reviewer` (review → repair → **closed**). T5–T7 remain unconfirmed.

## What landed

- **Embedding error-code refinement** (`src/ingestion/indexing/embedding.py`): result-count parse failure → `INTERNAL`; outer wrapper span classified **by origin** — local invariant failures carry a module-private marker (`_LOCAL_FAILURE_ATTR`, best-effort with safe `UPSTREAM` fallback) set at the three local raise sites (parse failure, dimension mismatch, incomplete results); re-raised transient exhaustion → `RETRY_EXHAUSTED`; provider-origin exceptions (including `ValueError`/`RuntimeError` from the provider) → `UPSTREAM`, consistent with their attempt spans. Per-attempt span codes and shapes unchanged. `VALIDATION` still reserved (no input-side failure path exists).
- **Budget-status dedup** (`src/cli/eval_pipeline.py`): the `--usage-summary` elif branch now calls the existing `_usage_budget_status` helper; output byte-identical (documented deviation: the summary file is read twice — helper + operation admission; offline immutable-input assumption).
- **Single review-context computation** (`src/evals/assessment/retrieval_eval.py`): base parts computed once per evaluation and threaded through `_review_manifest_hash_verification_failed` (new `base_parts` param) and `_review_manifest_authority_status_from_parts`; public `review_manifest_authority_status` unchanged as a thin wrapper. Attestation verification ≤1× per evaluation, base hashing 1× (was 3×).
- **Blind-spot tests**: empty-input embedding span (no provider call) and outer-span usage-absence (`test_embedding_spans.py`); manifest edges — extra attestation keys, boolean `schema_version` (attestation-level and manifest-level), record superset/subset, missing/whitespace `query_id` (`test_review_manifest_authentication.py`); 429/503 retry-then-exhaust and 400 no-retry stream classification via `SyntheticStatusError` (`test_stream_retry_telemetry.py`); wrapper guards + call-count pin; **one `summary.json` canary** (`test_content_canaries.py`) closing the last blind spot from the Logfire-slice review chain.

## Review chain

Initial review: **approve-with-repairs** — one P2 (outer classifier typed provider-origin `ValueError`/`RuntimeError` as `INTERNAL`) + blind spots. Repair landed the origin-marker design; three new tests then failed in the parent gate on wrong span-shape expectations (outer wrapper spans carry a generated `attempt_id` by established design) — parent corrected the expectations only, no classification/privacy assertion weakened. Closure check: **all four items CLOSED, final verdict CLOSED** (verbatim in `/tmp/qna-eval-review-polish-p0bETV/review.md`).

## Verification (snapshot `/tmp/qna-eval-review-polish-p0bETV/`)

- Gate via `scripts/verify_phase123_offline.sh` only: **1,741 passed / 5 warnings ×2 fresh processes** (`gate-final3*.log`; progression 1,717 → 1,736 → 1,738+3 failed → 1,741; the intermediate failure and its honest record are in `gate-final2.log`).
- Statics: Ruff 332 files, MyPy 159 src, 4 import contracts, docs consistency — green.
- Preservation: allowed-set comparison clean (touched files exactly: 3 tracked src + 4 test files; `test_budget_admission.py` byte-identical as expected); locks identical.
- Attributable diffs: `attr-*.diff` (src files vs reconstructed slice-start via HEAD + before-patch stanzas; canaries vs prior snapshot copy). Known evidence gap (disclosed to and accepted by the reviewer): no before-images for three of the changed test files.

## Residuals (documented, not repaired — for future bounded plans)

- Orchestrator's own `_review_context_parts` calls (`_record_dataset_identity`, `_validate_review_context_for_dataset`) remain un-threaded — **T6 residual** (that task imports these helpers).
- Verifier-level manifest `schema_version: true` passes via `True == 1` — unreachable behind the orchestrator's bool rejection; defensive-depth candidate.
- Dead `RuntimeError("Unexpected error in embedding retry logic")` (`embedding.py` ~:251) unmarked → would classify `UPSTREAM` if ever fired (unreachable with `max_retries >= 1`).
- Budget summary concurrent-replacement between the two reads — out of model (offline immutable input).
- Provider-origin `RuntimeError` and marker-set failure not directly exercised by tests (covered by inspection per closure verdict).

## Exit accounting (do not overclaim)

T4 closes the review-polish batch only. Still open, unchanged: identity-authenticated review authority, D17 judge pinning + matched-run capture, full budget admission, hosted destination setup + hosted smoke (fail-closed OTLP env gate already implemented), Docker/container smoke, reranker assets, live baselines, Phase 4, and expansion tasks **T5–T7**.

## Next thread pickup

Confirm T5 (D11 frozen embedding/index identity snapshot) and/or T6/T7 per the [brief](20261021-next-slice-brief.md); each still needs inspect → bounded plan → approval. Starting state to verify: HEAD `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`, dirty tree untouched, gate 1,741 ×2 (`/tmp/qna-eval-review-polish-p0bETV/gate-final3*.log`), statics as above.
