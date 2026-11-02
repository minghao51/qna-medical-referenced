# Next agent: start here

## Current state

**P01–P10 and the P09.1/P10.1 review follow-ups are implemented offline in the shared working tree. Nothing is committed.** Docker is installed; the immediate next work is the local Docker preview, then PR/merge and the owner-approved deployment.

Read in this order:

1. Root `AGENTS.md` and any scoped instructions; inspect `git status` and preserve all uncommitted work.
2. [Continuation handoff](continuation-handoff.md) — current state, verified baseline, next work and boundaries.
3. [Local preview handoff](../../docs/deployment/local-preview-handoff.md) — Docker setup, local image build, preview URL and PR steps.
4. [P10 readiness report](../../docs/plans/20261101-p10-readiness.md) — offline gates, residual risks and release posture.
5. [Deployment pickup brief](../../docs/plans/20261101-deployment-pickup.md) — owner inputs, G-AUTH evidence and rollback.
6. [Cloudflare demo runbook](../../docs/deployment/cloudflare-demo.md) — exact host/Tunnel/Access steps.
7. [Implementation specification](implementation-specification.md), [file map](implementation-map.md), [plan](implementation-plan.md) and per-slice reports under `docs/plans/20261101-*`.
8. [Interaction contract](interaction-spec.md), [data map](screen-data-map.md), [design rationale](design-rationale.md) and SVGs via [index](README.md).

## First work — local preview, then PR

### A. Local Docker preview (immediate)

Follow [local preview handoff](../../docs/deployment/local-preview-handoff.md). Build the actual images, run `backend/frontend/ingress` with the localhost-only override, and inspect **http://localhost:8080**. Do not start `cloudflared`. After the owner accepts it, commit/push/open a PR into `main`.

### B. Deploy the private demo

Ask for the five owner inputs in the deployment pickup brief (Cloudflare domain, host type, chat spend, Access allowlist, GHCR visibility). Then follow the transfer/deployment runbooks. Do not deploy or publish images before explicit approval.

### C. Review/polish the offline implementation

Pick an explicit follow-up from continuation-handoff §4C (origin Access JWT verification, role policy, `/documents` route auth, physical screen-reader sign-off). Present a bounded plan before changing code. Do not reopen completed slices without defect evidence.

### D. Resume a deferred product contract

Only with a new specification/approval: verified comparison cohorts, catalog-to-historical-case binding, durable traces, provider-call ledger, whole-index search, confidence intervals or public demo. These are not hidden prerequisites and must not be invented.

## Verified baseline to re-run

```bash
bash scripts/check_backend.sh fast
bash scripts/check_backend.sh offline
bash scripts/check_backend.sh lint
npm --prefix frontend run check
npm --prefix frontend run build
npm --prefix frontend test
```

Expected: backend fast2367 passed/1 skip/115 deselected; offline2388/1/94; frontend check/build pass; Playwright108 passed/9 skipped/0 failed. Playwright needs the existing temporary `/tmp/qna-browser-libs` NSS/NSPR extraction on `LD_LIBRARY_PATH`; do not install system/repo packages without approval.

## Hard boundaries

- No deployment, image publish, provider spend, hosted export, corpus/index mutation, data migration or public rollout without explicit owner approval.
- No API key in `VITE_*`, browser storage, docs, logs or screenshots. No anonymous bypass.
- No fake comparison cohort, latest-run fallback, catalog-case join, durable trace or clinical claim.
- No new auth platform/state library/dependency without approval.
- Preserve the uncommitted tree; no reset/clean/stash/checkout. No commit unless asked.
- Record exact tests/results, residual risks and rollback per slice. Distinguish offline-verified from authenticated-verified/released.

## Ready-to-use prompt

> Continue from the shared Fieldnote working tree. Read `AGENTS.md`, `assets/svg/continuation-handoff.md`, `docs/deployment/local-preview-handoff.md`, the P10 readiness report, the P09.1/P10.1 follow-up report, the deployment pickup brief, the per-slice reports and the implementation spec/map/plan. Verify Docker access, build/start the local preview on http://localhost:8080, and inspect it with the owner. Preserve all uncommitted work; do not commit/PR until the local check is accepted. Then proceed to the owner-approved Cloudflare Access/Tunnel deployment and G-AUTH evidence. Do not deploy, publish images, spend provider quota, mutate data/index or claim release readiness before the owner inputs and evidence exist.
