# Review authority + D17 judge pin handoff — pickup stages 2 and 3 delivered — 2026-10-24

**Status:** both leftover stages delivered and gated. Stage 2 exercised the fail-closed hash-attestation tool for the first time with a recorded authority; stage 3 pinned the independent judge as configuration only. **No live provider call, no spend, no dependency change, no default switch.**

## Approvals used

Owner 2026-10-24, in-session: "lets go with D2 and D3, for the judge, we can leverage opencode deepseek v4.1 flash or longcat"; then "we ca nuse more tokens, i am more worry of cutoff, invalid structures" (judge output budget) and, in answer to the two scoping questions: "1. the standing reviwer / 2. option B".

Standing pairing preserved: worker `glm-worker` (`zai/glm-5.3-flash`), reviewer/authority `luna-reviewer` (`openai-codex/gpt-6-luna:xhigh`). Parent owned the snapshot, corpus export run, attestation run, integration, gates and docs.

## Stage 2 — review authority recorded and exercised (D07-ext)

**Authority:** `openai-codex/gpt-6-luna:xhigh` — the named independent engineering reviewer, not the implementation author. Name, scope and first-exercise date are recorded in [decisions](../migration/decisions.md).

**Why this is the first real exercise:** the T6 tool existed with 27 tests but no manifest had ever been verified, so `reviewed_evidence_eligible`, cohort and promotion eligibility were unreachable.

**Option B chosen** (bind the real frozen corpus, not a toy one):

1. `scripts/manual/export_review_corpus.py` (NEW, worker `glm-worker` + parent repairs) — read-only export of the manifest corpus payload from `data/chroma-d11` (`medical_docs`): `{"sources": {id: {"content"}}, "documents": {id: {"source_id", "content"}}}`. Deterministic (`sort_keys`, documents ordered by `(page, chunk_index, id)`, atomic write, refusal on empty/malformed/missing-`source` records). Result: **2,473 documents / 60 sources / 1.41 MB**, byte-identical across two runs (`62d4e1b3024cb52cd364dfaccc71eac78d473c5a5e6389bc84b082da603a7cba`).
2. Reviewed dataset authored **by the authority** (`luna-reviewer`, reply transcribed byte-for-byte by the parent because that agent is read-only by design): 8 cases — 7 answerable with 8 bound qrels passages across 8 distinct sources, 1 unanswerable with an empty passage list. `data/evals/review/dataset.json` (`f1849cce…`).
3. Attestation run: `python -m src.evals.assessment.review_manifest_tool` with `--reviewer-id openai-codex/gpt-6-luna:xhigh`, `--manifest-id d11-review-manifest-v1`, `--index-snapshot-fingerprint a0dc5d29…` → exit 0, printed `manifest_hash_verified_not_identity_authenticated`, wrote `data/evals/review/manifest.json` (1.30 MB, `7e19b572…`), byte-identical on re-run. First failing attempt was the correct fail-closed refusal of an empty fingerprint (a `python`-vs-`uv run` shell slip), not a tool defect.
4. Independent re-verification (parent): `_read_review_manifest` → `_review_context_parts` → `_review_manifest_authority_status_from_parts` returns the hash-verified status; per-case `_reviewed_evidence_qrels` binds all 8 passages; frozen binding is 60 sources / 2,473 documents; manifest `dataset_sha256 05a329ae…`, `corpus_sha256 18f4733d…`, `attestations.content_sha256 801716eb…`.

**Deliberate design decision (recorded):** the corpus binding is exported from the Chroma store, **not** from the gold parquet, because sampled record contents differ between the two past character 100 — the binding must match what retrieval actually returns or evidence provenance would silently fail. `frozen_sources` content is therefore the ordered concatenation of the frozen chunk texts per source: sufficient and exact for quote binding, documented as a derivation rather than original document bytes.

**Unchanged guarantees:** attestations authenticate supplied-content consistency only; no identity, qualification or clinical-endorsement claim; authoring flips no eligibility flag, and eligibility is re-derived at execution from the manifest.

## Stage 3 — D17 independent judge pinned

**Finding presented before the pin:** the owner's first candidate, `deepseek-v4.1-flash`, is the **recorded matched generator** (decisions.md 2026-10-20 tuple, reconfirmed 2026-10-21), so it cannot judge its own comparison. The second candidate qualifies on family.

**Pin (config only, zero code change — every field already existed):**

| Field | Value |
|---|---|
| judge provider | `pydantic-ai` |
| judge model (light = heavy) | `longcat-2.0` (Meituan LongCat family vs DeepSeek generator) |
| endpoint | `https://opencode.ai/inference/go/openai/v1` (`pydantic_ai_base_url`) |
| credential | `APP__LLM__PYDANTIC_AI_API_KEY` (existing Go key; not inspected) |
| prompts | unchanged — verbatim DeepEval metric prompts (`METRIC_SPECS`), raw-prompt passthrough |
| temperature | 0.0 (`judge_temperature`) |
| output cap | **16,384** via run overlay `APP__LLM__JUDGE_MAX_TOKENS=16384` (committed default 1024 unchanged) |
| prices | $0.30 in / $1.20 out per 1M (public catalog; cached price unpublished) |

The raised cap is the owner's cutoff/invalid-structure mitigation: the model is a reasoning family, so a 1,024-token ceiling risks truncating a verdict mid-structure. Worst case ≈ $0.02 per judge call; realistic usage is far below the cap.

**Frozen snapshot:** [D17 matched-run configuration](../migration/20261024-d17-matched-run-configuration.json) — generator `deepseek-v4.1-flash`, judge `longcat-2.0`, retrieval carried unchanged from the 2026-10-19 baseline snapshot, D11 identity pointers, review binding, prices, budget class, and an explicit limitations list.

**Recorded caveats (do not overclaim):** family independence is satisfied but the **route is shared** (both calls traverse OpenCode Go), so any comparison must report that confound; Go's acceptance of `max_completion_tokens` and the judge's real quality/latency/usage are unverified until a separately approved live check; availability rests on the public catalog listing only; the generator's structured-output capability remains unestablished (Stage A boundary), adapter generation stays opt-in and preflight stays fail-closed.

## Files changed

- `scripts/manual/export_review_corpus.py` (new; parent repairs: refusal-message wording, summary-line wrapping).
- `tests/unit/manual/test_export_review_corpus.py` (new, worker `glm-worker`; 12 tests — read-only behaviour, exact payload shape, `\n\n` ordering joins, insertion-order/str-vs-int determinism, nested output dir creation, default collection name, and 7 refusal classes each asserting exit 1 + single-line stderr + no artifact).
- `scripts/verify_phase123_offline.py` — one inventory line for the new test file (parent-owned).
- `docs/plans/migration/decisions.md` — two session records (authority exercise, D17 pin).
- `docs/plans/migration/20261024-d17-matched-run-configuration.json` (new snapshot).
- `docs/plans/migration/20261021-remaining-work-pickup-brief.md`, `docs/plans/migration/README.md`, this handoff.
- Local, gitignored artifacts: `data/evals/review/{corpus,dataset,manifest}.json`.

No `src/` change; `uv.lock` untouched (`7d63f1ce…`); no `.env` inspection.

## Verification

- Isolated gate `bash scripts/verify_phase123_offline.sh` ×2 fresh processes: **2,043 passed / 5 warnings** both runs (`gate-1.log`, `gate-2.log` in the session snapshot dir; progression 2,031 → 2,043, +12 exactly the new manual-script tests, 0 skipped, 0 deselected).
- Statics: Ruff check clean; Ruff format 356 files; MyPy 164 `src` files; import-linter **4/4 contracts kept**; docs consistency passed.
- Artifact determinism: corpus export and manifest authoring each re-run byte-identical.
- Snapshot before changes: `/tmp/qna-stage23-20261024/` (HEAD `eb7c733`, clean `status -uall`, lock digest, empty untracked list).

## Review chain

- `glm-worker` wrote the export script (static-check only, no execution); parent repaired two cosmetic issues and ran the export.
- `luna-reviewer` (as the named authority) authored the reviewed dataset; its first reply correctly declined to write files because that agent is pinned read-only, so the dataset was re-requested as inline JSON and transcribed without edits.
- Parent performed the independent manifest re-verification and all gate/static runs.
- No adversarial code review was commissioned for the export script: its contract is covered by the 12 hermetic tests, its output was verified against the real collection, and it touches no production path. That omission is recorded, not hidden.

## Rollback

Delete the two new files and the one inventory line; revert the four doc edits. Local artifacts under `data/evals/review/` are regenerable (`export_review_corpus.py` + the authority's dataset + the tool). `data/chroma-d11` was read only; the legacy `data/chroma` store was never touched.

## Remaining menu (unchanged)

Hosted Logfire (destination/token/access), Docker/container smoke, reranker asset selection then gated download, live baselines (fresh run-specific approval; Stage B additionally needs a query-embedding permission), and owner decisions D12–D16/D18. Stage C additionally still needs the structured-output boundary resolved and a live verification of the pinned judge.
