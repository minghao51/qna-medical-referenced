# T5 D11 frozen-identity snapshot handoff — 2026-10-21

**Purpose: closing record for the confirmed expansion task T5** of the [next-slice brief](20261021-next-slice-brief.md), following the [T4 handoff](20261021-t4-review-polish-handoff.md). Parent + one `glm-worker` (two repair rounds) + `luna-reviewer` (review → repairs → **closed**). T6–T7 remain unconfirmed.

## What landed

- **`scripts/manual/build_d11_frozen_identity.py`** — offline D11 identity builder. Embedding identity from `effective_roles` (verified: `text-embedding-v4`, 768 dims matching D11, provider qwen); corpus identity via `content_directory_provenance` verbatim; index identity by freezing the configured collection from a private copy of `data/chroma` under a **source sqlite `BEGIN EXCLUSIVE` maintenance boundary** (chroma's writers coordinate through sqlite) plus a before/after file-signature net, through the real `freeze_index_snapshot` seam. Fail-closed everywhere: missing/locked/corrupt sqlite → `chroma_source_lock_unavailable`; unstable source → `chroma_source_unstable`; forged success-shaped captures → `index_capture_invalid` (verified branch mirrors upstream `_validate_build_spec`: 64-hex digests, positive counts/dimensions, non-empty model/collection, finite numeric semantic/keyword/boost weights, required hex source provenance); missing/incomplete embedder role → explicit unverified blocks. Documented residual: filesystem-level writers bypassing sqlite coordination are out of model (signature check remains a secondary detector).
- **`tests/unit/evals/test_d11_identity_builder.py`** — 19 tests incl. the two-connection sqlite exclusion proof, pre-locked-source and mid-copy-mutation fail-closed paths, forged-capture rejections, honest missing-role serialization, content-free output assertions, real local tmp chroma stores.
- **`docs/plans/migration/20261021-d11-frozen-embedding-index-identity.json`** — emitted artifact (parent-run builder). Honest current state: embedding identity **verified**; corpus **unverified** (`source_tree_empty` — `data/raw` contains 0 files); index **unverified** (`Index snapshot is empty or exceeds the supported document count` — the `medical_docs` collection holds 0 documents; other local collections are test artifacts). No content, no live/clinical claims, reranker `not_selected_not_downloaded`, deterministic (byte-identical across regenerations).

## Review chain

Initial review: approve-with-repairs (three P2s). Repair round 1: quiescence signature, forged-capture validation, honest role blocks — first gate run exposed three test failures, parent-repaired (post-gate shape reasons, a broken recursive-`copytree` monkeypatch rewritten to mutate between signature captures, a leftover duplicate line in `main()`); closure round 1: M3 closed, M1/M2 open with precise gaps. Repair round 2: sqlite exclusive-lock copy boundary + strict upstream-mirroring validation; parent added the reviewer's non-blocking pre-locked-source test and a fast lock timeout. **Second closure verdict: T5 CLOSED** (all verdicts verbatim in `/tmp/qna-eval-d11-snapshot-Lm1Nam/review.md`).

## Verification (snapshot `/tmp/qna-eval-d11-snapshot-Lm1Nam/`)

- Gate via `scripts/verify_phase123_offline.sh` only: **1,760 passed / 5 warnings ×2 fresh processes** (`gate-final7*.log`; progression 1,741 → 1,753 → 1,756 → 1,759 → 1,760; two intermediate 3-failure runs honestly logged).
- Statics green: Ruff 334 files, MyPy 159 src, 4 import contracts, docs consistency.
- Emitted JSON byte-identical across regenerations after each repair round (verified by diff).
- Preservation OK (touched files exactly: builder, tests, emitted JSON, one inventory line; locks identical; `data/` never written).

## Residuals & exits (do not overclaim)

- **The frozen identity is configuration-level only right now**: this machine has no materialized corpus (`data/raw` empty) and an empty `medical_docs` index. A verified corpus/index identity requires an ingestion run (with source provenance metadata satisfying `_validate_build_spec`) and re-running the builder. This is a **new documented exit**: "corpus/index materialization + provenance-carrying ingestion before a verified frozen identity".
- Documented model boundary: sqlite-coordinated writers excluded during copy; raw filesystem writers out of model (secondary signature detection only).
- T5 does NOT close: review authority, D17 judge pinning, budget admission, hosted setup/smoke, Docker smoke, reranker assets, live baselines, Phase 4, and **T6–T7**.

## Next thread pickup

Confirm T6 (attested-manifest authoring helper) and/or T7 (P3-B boundary docs) per the [brief](20261021-next-slice-brief.md); note T6's constraint: it may only **import** `retrieval_eval.py` helpers (no edits) and inherits the documented orchestrator review-context residual. Starting state: HEAD `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`, dirty tree untouched, gate 1,760 ×2, statics as above.
