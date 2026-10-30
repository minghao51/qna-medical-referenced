# Audit Follow-ups — 2026-10-30

**Context:** full setup audit (backend web layer, frontend↔backend contract,
configuration/deployment, ingestion/RAG, R2 sync) followed by a five-slice
remediation, committed as `d6d3455` (*Harden deployment contract, security, and
data integrity*) and pushed to `main`.

**Status:** closed items are recorded at the bottom. Everything in *Open items*
is deliberately deferred; none of it is a hidden regression from `d6d3455`.

Owner actions use the decision register (`docs/plans/migration/decisions.md`) as
the authority for anything that changes serving behavior or deployment posture.

---

## Open items

| ID | Priority | Item | Owner action | Acceptance |
|---|---|---|---|---|
| F-01 | High (governance) | **Ratify the serving-profile default change.** `config/settings.yaml`, `src/config/settings.py`, and `docker-compose.yml` now default to `baseline` instead of `baseline_cross_encoder`. | Append an approval entry to `docs/plans/migration/decisions.md` recording that the default image installs no optional dependency groups and has no reranker assets, so `baseline` is the correct served default and `baseline_cross_encoder` is opt-in. | A dated decision entry exists; `README.md` and `docs/data-sync-runbook.md` already state the deviation and the opt-in path. |
| F-02 | High (security) | **Role-based authorization and admin UI.** `/config`, `/evaluation*`, `/documents`, and `/experiments` authenticate but do not authorize; any valid key can read them. No admin UI exists. | Decide the public/admin split first (public chat only vs. protected operator views), then add route-level role checks and a server-side auth path for the UI. Do not ship a key in browser code or `VITE_*`. | Each protected route rejects a key without the required role; tests cover allow/deny per route; docs match. |
| F-03 | Medium | **Read-only serving boot.** Applying a runtime profile still writes additive metadata keys into the served collection at startup (`src/ingestion/indexing/store.py::_apply_index_metadata`); vectors and frozen provenance are untouched, but a boot mutates the artifact's metadata. Validation credit is also not invalidated when a caller mutates metadata after a successful check (no production caller today). | Decide whether serving must be strictly read-only (apply overlays in memory only) or whether additive writes are acceptable; if read-only, gate the write on a build/ingestion context. Bind credit to metadata state or reset it explicitly on mutation. | Booting a read-only mount succeeds without `collection.modify`; a metadata mutation after validation forces re-validation. |
| F-04 | Medium | **OpenAPI drift guard.** `docs/20260424-openapi-swagger.yaml` was manually corrected (evaluate-single request body, `findings` array, `ready`, nullable aggregates) but remains hand-maintained. | Generate the spec from FastAPI models, or add a contract test comparing `create_app().openapi()` shapes to the checked-in YAML for the documented endpoints. | CI fails when a route schema and the published contract diverge. |
| F-05 | Medium | **Frontend SSE parser hardening.** The chat client still parses only single-line `data:` JSON frames; no named events, `[DONE]`, multi-line accumulation, reconnect, or truncated-stream detection. The backend currently emits the narrow format, so this is resilience, not a live bug. | Introduce a small SSE parser with explicit terminal-state validation and a user-visible "incomplete response" error; add chunk-boundary and malformed-frame tests. | Frames split across chunks and malformed frames produce deterministic UI states; no silent partial answers. |
| F-06 | Medium | **Remaining API hardening from the audit.** No request-body size limit at the ASGI/proxy layer; evaluation `run_dir` accepts `.`/`..` and artifact paths are not root-confined; `/evaluation/l6/records` reads a whole file before applying `limit`; 429 bodies and `X-RateLimit-Reset` do not match the documented error contract. | Add a body-size gate, resolve/contain artifact paths under the evaluation root (reject symlinks), bound `limit` with `Query(ge=1, le=500)` and stop reading early, align error payload/headers. | Path-traversal and oversized-input tests fail closed; documented limits match runtime. |
| F-07 | Medium | **R2 integrity beyond size.** `--verify` now detects same-size drift by SHA-256, but `--upload`/download still skip on a 100-byte size tolerance, and there is no manifest. | For frozen-artifact syncs, prefer exact size + checksum equality (manifest) rather than tolerance; keep tolerance only for the raw corpus if it is intentional. | A byte-changed frozen artifact is never reported in sync; manifest verification is documented. |
| F-08 | Low (test hygiene) | **Split live vs offline coverage in `tests/unit/evals/test_eval_error_handling.py`.** The module-level `pytestmark = [slow, live_api]` is honest (every test drives real retrieval + DeepEval judges) but also excludes the two offline artifact-store tests in that file. | Extract the offline tests into a non-live file, or scope marks per test; document `RUN_LIVE_QWEN_TESTS=1` as the opt-in for live runs. | Offline tests run in the default gate; live tests remain opt-in. |
| F-09 | Low (ops) | **Legacy index migration.** `data/chroma` (pre-provenance) now fails closed at startup by design. Operators with old indexes need a repair path. | Point the runbook at `data/chroma-d11`, `python -m src.cli.ingest --force-rebuild`, or a metadata backfill (see `scripts/manual/backfill_d11_collection_metadata.py`) and state which is authoritative. | An operator following the runbook can serve or rebuild without guesswork. |
| F-10 | Medium (ops) | **Proxy trust and NAT.** Anonymous `/chat` limits are now per client IP. Behind `APP__API__TRUST_PROXY_HEADERS=true` the app trusts the leftmost `X-Forwarded-For`; NAT users share one bucket. | Require the trusted proxy to overwrite/strip forwarded headers and block direct backend access; decide whether edge limiting supplements the in-app per-IP limit. | Deployment guide and proxy config enforce header overwrite; documented NAT tradeoff accepted. |
| F-11 | Medium (deps) | **Unbounded upper constraints.** `chromadb>=0.4.0`, `openai>=1.0.0`, `litellm>=1.0.0`, `wandb>=0.23.0` have no upper bounds; the ChromaDB 1.x embedding-function behavior is already observable in tests. | Pin compatible ranges and add a lockfile refresh check. | Dependency upgrades are deliberate and CI-verified, not implicit. |

---

## Why a pytest run can appear to hang

Two independent effects, both addressed in `d6d3455`:

1. **Unmarked live-network tests.** `tests/unit/evals/test_eval_error_handling.py`
   drives real retrieval plus DeepEval judges; each test took 60–210 s
   (~18 min for the file). `tests/unit/infra/test_hyde.py` constructed a real
   provider client in 12 tests. Neither was marked `live_api`, so the default
   gate executed them.
2. **Orphan behind a pipe.** `timeout 2800 uv run pytest … | tail -5` kills
   `uv`, but the pytest child keeps running and holds the pipe open, so the
   shell waits far beyond the timeout.

Both files are now marked, and `tests/conftest.py` auto-skips `live_api` unless
`RUN_LIVE_QWEN_TESTS=1`. The offline gate completes in **~49 s** (2,284 passed).
See `docs/testing/backend-tests.md` for the exact commands.

---

## Closed in `d6d3455`

- Deployment: D11 path/collection default, `baseline` profile, no collection
  renaming by serving profiles, startup identity log, `config/sources.yaml`
  in the image.
- Security: CORS outermost (preflight/401/429 carry ACAO), IP-keyed anonymous
  limiting (rotating cookie bypass removed), lazy thread-safe rate-limit DB
  init (no import-time project-DB access).
- Data integrity: metadata overlay merge (provenance preserved) with
  authoritative `set_index_metadata` for migrations, complete required-key
  fail-closed readiness, credit bound to `(signature, store)` and invalidated
  on rebuild/experiment config, R2 path containment, `.r2part` cleanup,
  SHA-256 verify drift detection, sanitized key logging, body close on error.
- Web/contracts: SSE `Cache-Control`/`X-Accel-Buffering`, abortable chat
  stream with generation tokens, honest clear-history, OpenAPI shape fixes,
  `APP__` env-var documentation, refreshed stale codebase notes.
- Tests: 8 red tests fixed, rate limiting isolated to a tmp DB per test,
  regression coverage for CORS, IP limiting, metadata merge/replace,
  readiness fail-closed paths, and R2 containment/checksum/cleanup.
