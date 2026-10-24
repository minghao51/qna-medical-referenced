# D11 materialization handoff — corpus/index identity VERIFIED — 2026-10-24

**Status:** pickup-brief stage 1 (the keystone) **delivered and closed**. The D11 frozen identity is no longer "honestly unverified/empty": corpus, embedding, and index identity blocks are all `verified` with `freeze_guarantee: true`. Luna review chain: REPAIRS REQUIRED (6×P2, 2×P3) → all repaired → **VERDICT: CLOSED**.

## Approvals used

- Owner 2026-10-24: "B approve, B1" (slice shape); "yes for all" (B2-fetch of `config/sources.yaml`, spend go for embedding, B3 identity confirmation); "3a" (repair stale URLs before freeze); "1b" (workspace endpoint lives in `.env`, not committed config); "fetch" (LabQAR); "a" (URL-guard surgical fix).

## What changed (two commits + this closure)

- `5096f9a` — corpus source repair: 29 dead URLs (ACE restructure, isomer PDF UUIDs, HealthHub content-API retirement) remapped to live successors or removed with reasons; verified fetch 48 md + 10 PDF → 2,135 gold chunks; `docs/data/sources.md` updated.
- This commit — B1 seams + materialization closure (files listed below).

## Operational materialization (record)

- Corpus fetch: `data/raw/` (public SG MoH/ACE/HealthHub/NICE pages + PDFs; download manifest with per-URL status; 62 downloaded, 0 current failures).
- LabQAR (CC BY 4.0, figshare DOI 10.6084/m9.figshare.29391863): `Set_1.json`/`Set_2.json` cached under `data/raw/LabQAR/`; deterministic converter → `reference_ranges.csv` (471 rows, 79 skipped one-sided bounds; byte-identical across runs).
- Embedding (paid, owner go): DashScope-compatible embeddings, model `text-embedding-v4`, 768 dims, batch 10, into **new** storage `data/chroma-d11` (existing `data/chroma` untouched, still empty). Two passes: 2,007 inserted (128 dup skipped) + 466 reference vectors → **2,473 embeddings**; 466 inserted on pass 2 (5 dup skipped). Estimated cost ≈ $0.006 at $0.07/1M tokens (well under the USD 20/month ceiling; exact usage in local run records).
- Identity: `scripts/manual/build_d11_frozen_identity.py --chroma-dir data/chroma-d11` → **corpus verified (121 files, `27b130d9…`), embedding verified (workspace MaaS endpoint), index verified (`medical_docs`, 2,473 docs, fingerprint `a0dc5d29…`, `freeze_guarantee: true`)**. Emitted JSON updated in this commit; byte-deterministic.

## Code seams (worker `glm-worker` rounds ×3 + parent repairs; Luna-reviewed)

- `_safe_qwen_endpoint` allowlist (`src/evals/deepeval_models.py`): workspace-scoped `*.maas.aliyuncs.com` hosts accepted beside the two legacy DashScope hosts; error message byte-identical (an existing test regex pins it).
- `download_web.main()` (`src/ingestion/steps/download_web.py`): exported `DOWNLOAD_GROUPS` (moh was silently omitted — pre-existing gap, now fixed and fetched).
- `scripts/manual/build_labqar_reference_csv.py` (NEW): deterministic, fail-closed converter (atomic write; fallback to Set_1 only for missing bounds; present-but-invalid/non-finite bounds rejected).
- `_reject_credentials` (`src/evals/index_snapshot.py`): **owner-approved surgical fix** — the urlsplit userinfo/query/fragment check now applies only to scheme-anchored URL strings (prefix + embedded span scan); fixes a false positive where prose quoting a URL + a later sentence `?` blocked index certification. Key-name rules and real-URL behavior unchanged.
- `build_collection_build_metadata` + attach (`src/ingestion/indexing/store.py`): all 22 required build-metadata keys from live typed config at collection creation; returns `None` (no metadata) when the raw corpus is unavailable — gate-integration repair so isolated stores don't fail (builder still fails closed on metadata-less stores).
- `scripts/manual/backfill_d11_collection_metadata.py` (NEW): idempotent, offline backfill (`collection.modify`, merge-preserving extra keys, digest always corpus-derived — override removed per review); applied once to `data/chroma-d11`.
- Builder cross-check (`scripts/manual/build_d11_frozen_identity.py`): verified index identity whose source digest mismatches the independently computed corpus digest downgrades to `index_source_provenance_mismatch`.
- Gate inventory (`scripts/verify_phase123_offline.py`): the five new test files added to the explicit list (they were silently not collected before — found via Luna's "green gate inconsistent" observation).

## Verification

- Isolated gate ×2 fresh bwrap processes: **2,031 passed / 5 warnings** (progression 1,969 → 2,031; +30 evals tests immediately, +20 more after the inventory fix; +2 closure round). Statics: Ruff check/format 354 files, MyPy 164 src, 4/4 import contracts, docs consistency.
- Review chain: worker ×3 → parent gate repairs (None-on-no-corpus, format, docstring merge) → Luna REPAIRS REQUIRED (6×P2/2×P3) → worker repairs → Luna **CLOSED** (no actionable findings; blind spots recorded in the review, all non-blocking).

## Residuals (do not overclaim)

- Build metadata reflects the **global effective configuration** at store init; stores constructed with non-default per-instance/runtime-overlay values would persist metadata that does not describe their build (Luna P2-5; certification is builder-validated against collection metadata, so such stores are internally consistent but only meaningful for default builds — recorded boundary, no code change).
- `src/evals/assessment/orchestrator.py` keeps its own evaluation-config credential guard (separate copy; unchanged by design).
- `settings.py` default `qwen_base_url` remains the legacy US host; the live endpoint comes from `.env` (`APP__LLM__QWEN_BASE_URL`) per owner decision 1b — the frozen identity records the workspace endpoint.
- LabQAR CSV rows with one-sided reference bounds (79) are skipped, recorded in converter output.
- The moh homepage and all corpus files live under gitignored `data/`; the identity JSON is the durable provenance record.

## What this unblocks (per the pickup brief)

- Stage B (real-RAG smoke) prerequisites: D11 ✔ — query-embedding permission still separate.
- Selectable `pydantic_evals` CLI `--harness` wiring (P4-C deferred checkbox) — can now be planned honestly.
- Phase-2 evaluation identity/replay work.

Still blocked/open: review-authority exercise (stage 2), D17 independent judge pinning (stage 3), hosted Logfire (stage 4), Docker smoke (stage 5), reranker assets (stage 6), live baselines (stage 7), owner decisions D12–D16/D18.

## Rollback

Revert this commit (code + docs + identity JSON). `data/chroma-d11/` and `data/raw/` are gitignored caches — delete only with owner approval (existing-data rule). The legacy `data/chroma` store was never touched.
