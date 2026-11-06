# P07 selected-run safety and P02 catalog internals

**Status:** implemented offline; review/acceptance pending. No deployment, live/paid provider call, hosted export, corpus/index mutation, data migration or public rollout was performed.

**Approval reference:** owner approved **G-ROUTES** and **G-FIXTURES** while continuing P02–P10, and approved **G-AUTH** as *Cloudflare Access + Tunnel + server-side key injection + origin with no published ports*. **G-AUTH release verification is still pending**; no deployment was performed and no authenticated-release claim is made. This record covers P07, P02 missing-state/internals, the approved six-file fixture packaging, and deploy-only G-AUTH artifacts.

## Scope delivered

### P07 — selected-run artifact safety

1. Explicit run names are resolved strictly inside the configured evaluation root. Dot-only names, traversal, separators, absolute paths and symlink escapes raise `InvalidRunDirectoryError`; missing explicit runs raise `FileNotFoundError` and never fall back to latest.
2. Existing `load_evaluation_run` and `load_answer_quality_details` now use the same resolver, closing their previous `evals_dir / name` traversal behavior.
3. `/evaluation/steps/{stage}`, `/evaluation/steps/{stage}/records` and `/evaluation/l6/records` accept optional `run_dir`; omitting it retains latest behavior. Scoped responses echo the actual selected `run_dir`.
4. L6 JSONL reads stream the file, return at most `limit` records, skip malformed/oversized lines safely and report `malformed_count`; a small page does not load the full artifact.
5. Eval-page hydration no longer depends on a run appearing in the 20-row history page: an explicit `?run=` selection loads directly, latest responses cannot replace a different loaded selection, and stale run responses are ignored via request sequencing. Refresh stays scoped to the selected run.
6. `comparable=false`, null history aggregates and diagnostic compatibility remain unchanged. No frontend cohort validator, trend chart or dataset-to-run binding was added.

### P02 — authenticated read-only catalog internals

1. New fixed nine-ID allowlist: `golden-original`, `golden-comprehensive`, `golden-diverse`, `golden-expanded`, `golden-all`, `golden-conversations`, `d11-review`, `lab-reference`, `d11-index`. No request path, glob, discovery or provider/ingestion import.
2. Roots derive from `src/config/paths.py` constants (`PROJECT_ROOT/tests/fixtures`, `DATA_DIR/evals/review`, `DATA_RAW_DIR/LabQAR`); `ensure_dirs()` is not called and missing roots/files are not created.
3. Every read is contained, regular-file checked, capped at 5 MiB (read at most cap+1), and hashed/parsed from the same bytes. Invalid/oversized/record-capped sources become `malformed`/`unsupported` entries without erasing other entries.
4. Query fixtures report `record_count`, exact split/label-confidence maps, raw stored review status or null, and explicit missing-review counts. Conversation fixtures count conversations and stored turns and ignore support arrays (`stop_words`, metadata).
5. `d11-review` is summary-only: aggregate answerability/declared review statuses only. Reviewer IDs, manifest bodies and frozen documents are not exposed. `d11-index` is `inventory_reference` linked to existing `/documents`; no second Chroma client or fixed 2,473 claim.
6. `lab-reference` reports CSV data rows separately from any served-chunk total.
7. All57/Expanded54 overlap is computed from exact stored query strings with both current revision digests; `normalization=none`, `near_duplicate_status=not_assessed`.
8. `/research-data/datasets`, `/research-data/datasets/{dataset_id}` and `/research-data/datasets/{dataset_id}/cases` require authenticated request state. Cases require a matching revision (`409 catalog_revision_changed`), are paged 1–100/offset ≥ 0, and return `409 catalog_cases_unavailable` for summary-only entries rather than a fake empty success.
9. **G-FIXTURES applied:** the runtime image copies exactly the six approved public/synthetic fixture JSON files; no whole `tests/` copy, `.env`, local artifact or dependency change.
10. `.dockerignore` now excludes `tests/*` but re-includes only those six fixture files and `tests/fixtures/`; without this the Dockerfile COPY would fail because `tests/` was previously excluded from the build context.

### G-AUTH deployment artifacts (deploy-only, not executed)

1. `docker-compose.demo.yml` runs backend/frontend/Caddy/cloudflared with **no published host ports**; only the tunnel reaches Caddy.
2. `deploy/Caddyfile` strips `/api`, injects `X-API-Key` server-side, overrides `X-Forwarded-For`/`X-Real-IP` from `Cf-Connecting-IP`, and disables SSE buffering.
3. `.env.demo.example` documents the required host secrets and the shared-key rate-limit caveat; `scripts/prepare_demo_env.py` generates `.env.demo` (mode 600) with the session secret, operator key and matching bcrypt record without printing secrets.
4. `.github/workflows/deploy-demo.yml` builds/pushes SHA-tagged images to GHCR, syncs the compose/Caddy files, and optionally deploys over SSH behind a manual `demo` environment and `DEPLOY_ENABLED` variable.
5. `docs/deployment/cloudflare-demo.md` records the Tunnel/Access/host/verification/rotation runbook and residual risks.

## Files changed

| File | Change |
|---|---|
| `src/evals/artifact_service.py` | Confined run resolver, optional scoped step/L6/step-metric selection, streaming bounded L6 reads |
| `src/app/routes/evaluation.py` | Optional `run_dir` on step/step-record/L6 endpoints; safe 400/404 handling; select-run echo |
| `src/evals/research_catalog.py` | New allowlist, bounded snapshots, summaries, overlap and revision-bound cases |
| `src/app/schemas/research.py` | New catalog HTTP models only |
| `src/app/routes/research.py` | New authenticated GET catalog/list/detail/cases handlers |
| `src/app/routes/__init__.py`, `src/app/factory.py` | Router export and inclusion only |
| `Dockerfile` | Exactly six approved fixture COPY lines |
| `tests/unit/evals/test_run_scoped_records.py` | Explicit vs latest, traversal/symlink, bounded/malformed L6, route echo/auth |
| `tests/unit/evals/test_research_catalog.py` | Allowlist, missing/malformed/oversize/record caps, units, overlap, review privacy, revisions, Dockerfile/.dockerignore packaging |
| `tests/unit/app/test_research_routes.py` | Auth, unknown IDs, revision 409, summary-only 409, unavailable entries |
| `tests/integration/app/test_app_security.py` | No-key research catalog 401 and keyed allowlist listing |
| `frontend/src/lib/utils/api.ts` | Optional `run_dir` on scoped record helpers |
| `frontend/src/routes/eval/+page.svelte` | Selection-first hydration, direct out-of-history load, stale-response guards, scoped refresh |
| `frontend/tests/history-comparability.spec.ts` | Out-of-history explicit run and no implicit run fetch |
| `docs/20260424-openapi-swagger.yaml` | Implemented research-data paths/schemas and scoped run parameters |
| `.dockerignore`, `.gitignore` | Allow only the six fixture files into the image context; allow `.env.demo.example` to be committed |
| `docker-compose.demo.yml`, `deploy/Caddyfile`, `.env.demo.example`, `scripts/prepare_demo_env.py` | Deploy-only private demo stack and env preparation; no app behavior change |
| `.github/workflows/deploy-demo.yml` | Manual/tag GitHub Actions build-push and optional SSH deploy |
| `docs/deployment/cloudflare-demo.md`, `docs/README.md` | G-AUTH delivery runbook and documentation link |

No RAG, ingestion, provider/model, evaluator/winner, index, prompt, default-profile, lockfile or frontend routing file changed.

## Tests run

| Command | Result |
|---|---|
| `bash scripts/check_backend.sh fast tests/unit/evals/test_run_scoped_records.py tests/unit/app/test_evaluation_routes.py tests/unit/evals/test_history_comparability.py -q` | **60 passed** |
| `bash scripts/check_backend.sh fast tests/unit/evals/test_research_catalog.py tests/unit/app/test_research_routes.py tests/integration/app/test_app_security.py tests/unit/evals/test_run_scoped_records.py -q` | **59 passed** |
| `bash scripts/check_backend.sh fast` | **2361 passed, 1 skipped, 115 deselected** (skip is the existing optional DeepEval/live-key test) |
| `bash scripts/check_backend.sh lint` | **passed** (Ruff check/format, mypy, import-linter, Bandit, docs consistency) |
| `npm --prefix frontend run check` | **0 errors, 0 warnings** |
| `npm --prefix frontend run build` | **passed** |
| `npm --prefix frontend run test -- tests/history-comparability.spec.ts tests/research-metrics.spec.ts tests/experiment-metrics.spec.ts` | **20 passed** |
| Full `npm --prefix frontend run test` | **60 passed, 9 skipped, 2 failed** — the two inherited `pipeline.spec.ts` failures (uncalibrated "Overall Confidence" expectation; strict `.message` locator on New Chat) |
| `bash scripts/check_backend.sh fast tests/unit/evals/test_research_catalog.py -q` | **14 passed** (includes Dockerfile/.dockerignore packaging guards) |
| YAML parse of compose/workflow/OpenAPI + `check_docs_consistency.sh` | passed |

Docker itself is not installed in this environment, so the backend/frontend images and compose stack were **not built or started** here. The G-AUTH workflow will exercise the image build; packaging is statically guarded by tests and must be confirmed by the first CI image build.

Playwright required the pre-existing `/tmp/qna-browser-libs` extraction on `LD_LIBRARY_PATH` because system NSS/NSPR libraries are absent; no repository or system package was installed.

## Backward compatibility / migration notes

- Scoped step/step-record/L6 responses are additive: `run_dir` (and `malformed_count` for L6) join existing fields. Callers omitting `run_dir` keep latest behavior.
- Catalog endpoints are new and read-only. Old clients ignore them. Catalog revisions fingerprint current bytes only; they are not historical dataset/label identity.
- `?run=` can now load runs outside the current history page. Selecting a missing run shows an unavailable error, not latest data.
- Review statuses are declared/raw only; no normalized default is presented as stored data.

## Residual risks / pending work

- **G-AUTH** shape is approved and deploy artifacts exist, but **no deployment/image build/authenticated smoke test has been executed**, so no release claim is made.
- Origin-side Cloudflare Access JWT verification is not implemented; the boundary is tunnel-only ingress with no published ports.
- Every visitor shares the injected operator key, so Cloudflare edge rate limiting is required and documented.
- **G-ROUTES** is approved but P03 has not started; root/chat have not moved.
- Packaging behavior is statically verified and missing/present states are tested against temporary roots; no container image was built or deployed in this slice.
- Full-frontend inherited failures remain untouched, per handoff.
- `documents.py` remains middleware-only; authenticated-boundary verification must cover it under G-AUTH.

## Rollback

Remove the new catalog router/files/tests and the six Dockerfile COPY lines; revert `artifact_service`/`evaluation.py` scoped parameters and the eval-page hydration/test changes. The demo deployment is additive: delete `docker-compose.demo.yml`, `deploy/`, `.env.demo.example`, the deploy workflow and its runbook. No data, index, fixture content or migration rollback is needed; `docker compose down` and deleting the Access app/tunnel returns the host to its prior state.

## Next proposed slice

**P03 shell/navigation + chat relocation to `/ask` + research root**, now unblocked by G-ROUTES, preserving legacy `/eval`, `/eval/ablation`, `/experiments`, `/health`, `/settings`, `/help`, `/docs/pipeline`. P06 follows P02+P03; G-AUTH remains the release gate.
