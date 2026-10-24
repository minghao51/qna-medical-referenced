# R2 data-sync handoff — off-machine durability delivered — 2026-10-24

**Status:** delivered and verified. The frozen D11 store, the raw corpus and the reviewed artifacts now mirror to a dedicated Cloudflare R2 bucket. No app/serving code touched, no data deleted, no secrets committed.

## Approvals used

Owner 2026-10-24: "is the current artifacts etc also sync to cloud fare etc" → "can we check on the `../egg-n-bacon-housing` cloudfare setup" → "can you help to create the token and bucekt too? yea option a it is" → "and also update the .env and .env.example" → "i have create the bucket, you can leverage the api key from the other project".

## What landed

- **Dependency (option a):** `boto3==1.43.118`, `botocore==1.43.118`, `jmespath==1.1.0`, `s3transfer==0.19.3`; lock delta +51 lines, no unrelated upgrades.
- **`scripts/manual/r2_sync.py`** (worker `glm-worker` + parent repairs): three sets — `corpus/` ↔ `data/chroma-d11`, `raw/` ↔ `data/raw`, `review/` ↔ `data/evals/review`; modes download (default) / `--upload` / `--verify` / `--only`; idempotent on a 100-byte size tolerance; atomic downloads (`.r2part` + `os.replace`); refuses with one stderr line when configuration is missing; credentials never printed. Parent repairs: parse args before settings so `--help` works without credentials; formatting.
- **`tests/unit/manual/test_r2_sync.py`** (worker `worker` = `opencode-go/deepseek-v4.1-flash`; 13 cases, fake boto3 injected via `sys.modules`): refusal without config, env/SecretStr settings + endpoint derivation and override, download and upload happy paths, 100-byte tolerance in both directions, verify counters, `--only` prefix isolation, missing-dir refusal, secret-never-printed, symlink skipping. Parent repair: `delenv(..., raising=False)` (the only gate failure of the slice).
- **`.env.example`** — commented R2 block with placeholders and the exclusion policy. **`.env`** — real values written blind (mode 600), values never displayed.
- **Gate inventory:** one line for the new test file (parent-owned).

## Verification

- Gate ×2 fresh bwrap processes: **2,056 passed / 5 warnings** both runs (2,043 → 2,056, +13 = the new tests).
- Statics: Ruff check clean, Ruff format 358 files, MyPy 164 `src` files, import-linter 4/4, docs consistency.
- Live R2 evidence: `--verify` before upload → 130 missing in R2; `--upload` → 130 transferred (6 corpus + 121 raw + 3 review) in ~25 s; `--verify` after → `ok=130, missing_locally=0, missing_in_r2=0, size_mismatch=0`.
- **Standalone check:** the same verify run with all `R2_*` variables stripped from the process environment passes, proving the repo's `.env` is sufficient.
- **Restore test (the "another setup" case):** pointed the module at an empty directory and ran the download path → 3/3 review artifacts restored with byte-identical SHA-256, no leftover `.r2part` files.

## Findings and limits

- **The borrowed token is account-wide, not bucket-scoped**, contrary to the source project's guide: it lists `egg-bacon-housing-data`, `equity-lake`, and `qna-medical-referenced-data`. It works, and the owner authorised reuse, but a leak would expose unrelated projects. Recommended follow-up (no code change): mint a token scoped to `qna-medical-referenced-data` only and swap two `.env` values.
- The tool resolves `.env` relative to the working directory, so it must be run from the repo root. Making the path absolute was deliberately rejected: it would break the test suite's isolation from the real `.env` and would let the tests read live credentials.
- Sync is one-way by default (download) and never deletes remote objects; `--upload` never prunes. No versioning or lifecycle rule is configured on the bucket — R2-side retention is therefore unbounded and unverified, which is adequate for public corpus data but is not a backup guarantee (no restore-from-history testing was performed).
- Credentials travel in a plaintext `.env` (mode 600) on this machine only; per decision 1b the workspace LLM endpoint stays out of the repo, and the same rule now applies to the R2 keys.

## Rollback

Delete the bucket contents/bucket in the Cloudflare dashboard; revert `scripts/manual/r2_sync.py`, its test, the inventory line, the `boto3` dependency (pyproject + lock), the `.env.example` block, and the decision record. Local data is untouched by any of this — the sync only reads local files and writes remote objects.

## Remaining menu (unchanged)

Hosted Logfire (destination/token/access), Docker/container smoke, reranker asset selection then gated download, live baselines (fresh run-specific approval; Stage B additionally needs a query-embedding permission), owner decisions D12–D16/D18. Optional follow-up from this slice: the bucket-scoped token swap.
