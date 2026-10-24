# Data Sync and Portability Runbook

Operational guide for moving this project's data between machines and keeping an
off-machine copy in **Cloudflare R2**. Companion documents: `local-workflows.md`
(the app/pipeline runbook), `configuration.md` (settings reference), and
`data-processing-boundaries.md` (content, access, retention and deletion limits).

Use this runbook when you need to:

- keep an off-machine copy of the corpus, the frozen vector index, and the
  reviewed evaluation artifacts
- move the project to another setup (new laptop, server, CI box) without paying
  to re-embed the corpus
- verify that a restored copy is the *same* frozen identity as the original

## What syncs, and what never syncs

Three sync sets, each with its own R2 prefix:

| R2 prefix | Local directory | Size (approx) | Contents |
| --- | --- | --- | --- |
| `corpus/` | `data/chroma-d11` | 25 MB | Frozen D11 Chroma store (`medical_docs`, 2,473 embeddings) |
| `raw/` | `data/raw` | 31 MB | Fetched public corpus + LabQAR reference class + download manifests |
| `review/` | `data/evals/review` | 3 MB | Reviewed dataset, exported corpus binding, verified review manifest |

**Never synced:** `data/evals/cache`, `data/evals/<run>` artifacts, `rate_limits.db`,
the chat-history store, logs, and `.env`. They are simply not members of any sync
set, so the tool never enumerates or writes them. Chat history and rate-limit
state are machine-local by design.

Everything above is public material (Singapore MoH/ACE/HealthHub/NICE pages and
CC BY 4.0 reference ranges). No patient data, prompts, sessions, or credentials
are involved.

## Prerequisites

1. **Client dependency.** `boto3` is a normal project dependency:
   `uv sync --frozen` is enough.
2. **Bucket.** A private R2 bucket dedicated to this project
   (`qna-medical-referenced-data`). Do not share a bucket with another project.
3. **Credentials.** An R2 API token with **Object Read & Write** scoped *to that
   bucket*. Create it in the Cloudflare dashboard: R2 → Manage R2 API Tokens →
   Create API token.
4. **Configuration** in `.env` (gitignored, mode `600`, never committed):

   ```dotenv
   R2_ACCOUNT_ID=...
   R2_ACCESS_KEY_ID=...
   R2_SECRET_ACCESS_KEY=...
   R2_BUCKET=qna-medical-referenced-data
   R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
   ```

   `R2_ENDPOINT` is optional; when empty it is derived from `R2_ACCOUNT_ID`.
   `.env.example` carries the same block commented out.

> **Run from the repository root.** The tool resolves `.env` relative to the
> working directory. Absolute-path resolution was deliberately rejected because
> it would let the hermetic test suite read live credentials.

> **Least privilege.** These keys can read/write objects in the configured
> bucket. A token that also lists unrelated buckets is broader than necessary —
> prefer a bucket-scoped token and treat the `.env` file as a secret.

## Daily commands

```bash
# Compare local vs R2 without transferring anything (safe, read-only)
uv run python scripts/manual/r2_sync.py --verify

# Push local changes (new corpus files, refreshed artifacts)
uv run python scripts/manual/r2_sync.py --upload

# Restore / refresh local from R2
uv run python scripts/manual/r2_sync.py

# One set only
uv run python scripts/manual/r2_sync.py --only review --upload
```

Behaviour worth knowing:

- **Idempotent.** A file is skipped when the remote size differs from the local
  size by at most 100 bytes. Re-running either direction is safe.
- **Download is atomic.** Each file lands as `<name>.r2part` and is then
  `os.replace`d into position, so an interrupted run never leaves a truncated
  file in place.
- **Additive only.** Neither direction deletes objects. `--upload` does not
  prune, and download does not remove local files missing from R2.
- **Fail-closed.** Missing configuration prints one line to stderr and exits 1
  without building a client. Credentials are never printed, logged, or included
  in error output.

### Expected output

First run against an empty bucket:

```text
corpus: 6 transferred, 0 up-to-date, 0 remote-missing
raw: 121 transferred, 0 up-to-date, 0 remote-missing
review: 3 transferred, 0 up-to-date, 0 remote-missing
```

Steady state (`--verify`):

```text
corpus: ok=6, missing_locally=0, missing_in_r2=0, size_mismatch=0
raw: ok=121, missing_locally=0, missing_in_r2=0, size_mismatch=0
review: ok=3, missing_locally=0, missing_in_r2=0, size_mismatch=0
VERIFY OK: ok=130, missing_locally=0, missing_in_r2=0, size_mismatch=0
```

Counters mean: `missing_in_r2` = local work not yet backed up; `missing_locally`
= remote objects not present here (relevant before a restore); `size_mismatch` =
same key, different size — investigate before trusting either side.

## Move to another setup

Follow this order; steps 5–6 are what prove the move worked.

1. **Clone and install:**

   ```bash
   git clone <repo-url> && cd qna-medical-referenced
   uv sync --frozen          # lock pins chromadb 1.5.5 — the store format depends on it
   ```

   `git clone` carries **no** data: `data/` is gitignored.

2. **Recreate `.env`** with the model/embedding credentials *and* the five `R2_*`
   values (mode `600`). Secrets travel out-of-band — never through git, chat, or
   a shared drive.

3. **Confirm the empty state, then download:**

   ```bash
   uv run python scripts/manual/r2_sync.py --verify   # expect ok=0, missing_locally=130
   uv run python scripts/manual/r2_sync.py            # restore corpus/ raw/ review/
   uv run python scripts/manual/r2_sync.py --verify   # expect ok=130, all deltas zero
   ```

4. **Point the app at the restored store.** The committed default
   (`storage.chroma_persist_directory`) is `data/chroma`, which stays empty. Set:

   ```bash
   APP__STORAGE__CHROMA_PERSIST_DIRECTORY=data/chroma-d11
   ```

5. **Verify the frozen identity** — the fingerprints must match the committed
   record (`docs/plans/migration/20261021-d11-frozen-embedding-index-identity.json`):

   ```bash
   uv run python scripts/manual/build_d11_frozen_identity.py \
     --chroma-dir data/chroma-d11 --corpus-dir data/raw \
     --output /tmp/identity-check.json
   ```

   Expect index fingerprint `a0dc5d29…`, corpus digest `27b130d9…`, `2,473`
   documents, `freeze_guarantee: true`. **One field is expected to differ:** the
   embedding *endpoint*, because it comes from `.env`, not from the data.

6. **Verify the reviewed artifacts:**

   ```bash
   uv run python scripts/manual/export_review_corpus.py \
     --chroma-dir data/chroma-d11 --output /tmp/corpus-check.json
   sha256sum /tmp/corpus-check.json    # expect 62d4e1b3…
   ```

   Do not regenerate `data/evals/review/dataset.json` — it is the review
   authority's work product; restore it from R2 and keep it byte-identical.
   The manifest re-verifies against it:

   ```bash
   uv run python -m src.evals.assessment.review_manifest_tool --help
   ```

   (Authoring a *new* manifest requires the dataset, corpus binding, reviewer id
   and index fingerprint — see the review-authority handoff under `plans/migration/`.)

## Troubleshooting

| Symptom | Cause / action |
| --- | --- |
| `Refusing to run: missing required R2 configuration: R2_ACCESS_KEY_ID` | `.env` incomplete, or you ran the tool outside the repo root |
| `... does not exist: data/chroma-d11` | Fresh clone before the first download; run the download first |
| `SignatureDoesNotMatch` | Wrong secret for the access key id, or credentials from a different account |
| `AccessDenied` / `NoSuchBucket` | Token not scoped to the configured bucket, or `R2_BUCKET` typo |
| `size_mismatch` in verify | Same key with different bytes — inspect before uploading or downloading |
| Downloads silently skip everything | Expected when sizes differ by ≤ 100 bytes; a genuine change of a few bytes is below the tolerance |

## Security and retention limits

- Credentials live only in `.env` (mode `600`, gitignored). The tool prints
  bucket/prefix names and counters — never keys, never the endpoint's account id.
- Prefer a **bucket-scoped** token. A shared account-wide token can reach every
  bucket in the account and is a wider blast radius than this project needs.
- **No versioning or lifecycle rule is configured** on the bucket. This runbook
  provides durability of the current state, **not** point-in-time recovery: an
  overwritten or deleted object has no history to restore, and `--upload` cannot
  recover a locally damaged file. Treat it as a mirror, not a backup system.
- Nothing here authorizes hosted evaluation exports. Logfire and W&B keep their
  own gate under `data-processing-boundaries.md`; syncing corpus data to this
  bucket does not extend those permissions.
