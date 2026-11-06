# Continuation handoff — local preview next; deployment after PR

**Snapshot:** 2026-11-02, branch `design/evidence-led-redesign`.
**State:** **P01–P10 and the P09.1/P10.1 review follow-ups are implemented offline in the shared working tree.**
**Not done:** commit, PR/merge, image build/publish, Cloudflare Tunnel/Access setup, deployment, authenticated-release verification.
**Local preview:** Docker is installed; `.env.demo.local` and a localhost-only ingress override are prepared. See [local preview handoff](../../docs/deployment/local-preview-handoff.md).
**Release posture:** private lab; no public/anonymous rollout authorized.

This is the pickup point for a fresh agent/thread. Start with the [local preview handoff](../../docs/deployment/local-preview-handoff.md), then the [P10 readiness report](../../docs/plans/20261101-p10-readiness.md), [deployment pickup brief](../../docs/plans/20261101-deployment-pickup.md), [specification](implementation-specification.md), [file map](implementation-map.md) and [plan](implementation-plan.md).

## 1. Working-tree facts (preserve)

- All implementation, tests, deploy artifacts and reports are **uncommitted** in the shared working tree. No commit was created.
- `assets/svg/`, all new `docs/plans/20261101-*` reports, the deploy stack, the catalog/run-safety backend and the research routes are untracked.
- The branch is `design/evidence-led-redesign`. A fresh worktree from the branch alone will **not** contain this work.
- Do not reset, clean, stash, checkout or overwrite the tree. Preserve unrelated user changes byte-for-byte.
- Do not redo completed slices without defect evidence. Do not “fix” tests by weakening assertions.
- Docker is installed now. The demo images were **not** built or published in the prior session; the local preview handoff is the immediate next action.

## 2. Completed slices

| Task | State | Report |
|---|---|---|
| P01 archive identity, metric semantics, experiment auth | Offline implemented | [P01](../../docs/plans/20261101-p01-archive-identity-and-metric-semantics.md) |
| P02 catalog internals + six-file packaging | Offline implemented; image unbuilt | [P02/P07](../../docs/plans/20261101-p07-selected-run-safety-and-p02-catalog-internals.md) |
| P03 tokens/shell/nav, root workspace, `/ask` | Offline implemented | [P03](../../docs/plans/20261101-p03-shell-workspace-and-ask-relocation.md) |
| P04 evaluations coverage + methodology | Offline implemented | [P04](../../docs/plans/20261101-p04-evaluation-coverage-and-methodology.md) |
| P05 feature evidence + archived labels | Offline implemented | [P05](../../docs/plans/20261101-p05-feature-evidence.md) |
| P06 dataset catalog + case inspector | Offline implemented | [P06](../../docs/plans/20261101-p06-dataset-catalog.md) |
| P07 selected-run artifact safety | Offline implemented | [P02/P07](../../docs/plans/20261101-p07-selected-run-safety-and-p02-catalog-internals.md) |
| P08 evidence facets + source detail | Offline implemented; `/documents` → `/evidence` | [P08](../../docs/plans/20261101-p08-evidence-facets-and-detail.md) |
| P09 Q&A turn state, SSE, recorded inspector | Offline implemented | [P09](../../docs/plans/20261101-p09-qa-turn-state-and-inspection.md) |
| P10 integration/accessibility/readiness | Offline complete | [P10](../../docs/plans/20261101-p10-readiness.md) |

Product routes now include `/` (research workspace), `/ask`, `/research/evaluations`, `/research/features`, `/research/datasets[/datasetId]`, `/research/methodology`, `/evidence[/id]`, plus retained `/eval`, `/eval/ablation`, `/experiments`, `/health`, `/settings`, `/help`, `/docs/pipeline`. `/research` redirects to `/`; `/documents` redirects to `/evidence` preserving safe filters.

## 3. Verified offline baseline

| Gate | Result |
|---|---|
| `bash scripts/check_backend.sh fast` | **2367 passed, 1 skipped, 115 deselected** |
| `bash scripts/check_backend.sh offline` | **2388 passed, 1 skipped, 94 deselected** |
| `bash scripts/check_backend.sh lint` | passed |
| `npm --prefix frontend run check` | 0 errors, 0 warnings |
| `npm --prefix frontend run build` | passed |
| Full `npm --prefix frontend run test` | **108 passed, 9 skipped, 0 failed** |
| Docs/OpenAPI consistency | passed |

Playwright needs the existing temporary `/tmp/qna-browser-libs` NSS/NSPR extraction on `LD_LIBRARY_PATH` because system libraries are absent. Do not install system/repo packages without approval.

The Ask page now uses the workbench rail, opens the recorded trace only on request and treats the inspector as a native modal dialog. `/health`, dataset detail, `/eval`, ablation empty state, report-ID wrapping, evidence mobile density, contrast and reduced motion were hardened after the visual review.

## 4. What remains

### A. Local Docker preview, then PR/merge (immediate)

Follow [local preview handoff](../../docs/deployment/local-preview-handoff.md): check `docker info`, recreate the localhost-only ingress override if `/tmp` was cleared, stop the old dev servers, build the actual images, start `backend/frontend/ingress`, inspect **http://localhost:8080**, then commit/push/open a PR only if accepted.

### B. Deployment / authenticated release (owner decision + execution)

The approved shape is **Cloudflare Access + Tunnel + server-side key injection + origin with no published ports**. Artifacts are staged:

- `docker-compose.demo.yml`
- `deploy/Caddyfile`
- `.env.demo.example` + `scripts/prepare_demo_env.py`
- `.github/workflows/deploy-demo.yml` (manual/tag; `DEPLOY_ENABLED` off)
- `docs/deployment/cloudflare-demo.md`
- [Local preview handoff](../../docs/deployment/local-preview-handoff.md)
- [Deployment pickup brief](../../docs/plans/20261101-deployment-pickup.md)

Required before any authenticated-release claim:

1. Owner inputs: Cloudflare-managed domain; host type (VPS with SSH vs home/NAT); whether live chat/provider spend is allowed; Access allowlist; package visibility.
2. Commit/push the work so GitHub Actions can build images; the current tree is uncommitted.
3. First image build and fixture-presence/missing-state verification.
4. Host data restore via `docs/data-sync-runbook.md`; `.env.demo` generated on the host (never committed).
5. Cloudflare Tunnel + Access application + WAF chat rate limit.
6. Deploy, then record evidence: Access login works, no-key research/eval/experiments return 401, direct origin ports closed, `/documents` reachable only through the boundary, no key in browser bundle, tunnel healthy.
7. Only then update G-AUTH from “shape approved” to “release verified”.

Do **not** deploy, spend provider quota, publish images, change DNS, expose ports, or call it release-ready without explicit owner approval.

### C. Optional/quality follow-ups (not release blockers)

- Origin-side Cloudflare Access JWT verification (needs a JWT dependency/approved change).
- Real role policy / audit F-02; currently all active keys are operator-equivalent.
- `/documents` route-level auth (currently middleware-only inside the app; Access protects it at the edge).
- Physical NVDA/JAWS/VoiceOver session; automated axe and Chromium accessibility-tree/keyboard evidence is in [accessibility.md](../../docs/testing/accessibility.md).
- Full 320/768/1024/1440 screenshot matrix beyond the route sweep; reviewed widths currently pass without page overflow.
- G-BRAND: keep existing title or finalize “Fieldnote”.

### D. Deliberately deferred product work (separate spec/approval)

Verified comparison cohorts; catalog-to-historical-case binding; durable chat traces; provider-call event ledger; whole-index search; confidence intervals; public anonymous demo/rollout. Do not invent these.

## 5. Fixes to carry forward

- `frontend/tests` route mocks matching `/\/chat/` also match `/chat-state`; the state module is named `conversation-state.svelte.ts` to avoid breaking Vite module loading. Do not rename it back.
- Page titles now come from page-level `<svelte:head>`; the layout no longer sets a competing `<title>`.
- Chat hydration is exposed as `.chat-container[data-hydrated="true"]`; synchronous test input before hydration is lost.
- Full frontend suite currently passes; do not reintroduce the old confidence/`.message` test debt.

## 6. New-thread kickoff prompt

> Continue from the shared Fieldnote working tree. Read `AGENTS.md`, `assets/svg/continuation-handoff.md`, `docs/deployment/local-preview-handoff.md`, `docs/plans/20261101-p10-readiness.md`, `docs/plans/20261102-p09p10-ask-surface-and-hardening.md`, the deployment pickup brief, the per-slice reports and the implementation spec/map/plan. Verify Docker access, build/start the local preview on http://localhost:8080, and inspect it with the owner. Preserve all uncommitted work; do not commit/PR until the local check is accepted. The next work after that is the owner-approved Cloudflare Access/Tunnel deployment and G-AUTH evidence. Do not deploy, publish images, spend provider quota, mutate data/index, or claim release readiness before the owner inputs and G-AUTH evidence exist.

## 7. Change/approval mechanics

- Root `AGENTS.md` requires a bounded plan before code changes.
- Any new architectural/auth platform, dependency/lock change, data/index migration, provider spend, deployment or gate bypass needs explicit owner approval.
- One integrator owns shared `types.ts`, `api.ts`, nav/shell, factory wiring and test helpers.
- Keep code/tests/docs together; use the per-slice report template.
- No commit unless the owner requests it; the current dirty tree must be preserved.

## 8. Source-of-truth links

- [P01 report](../../docs/plans/20261101-p01-archive-identity-and-metric-semantics.md)
- [P02/P07 report](../../docs/plans/20261101-p07-selected-run-safety-and-p02-catalog-internals.md)
- [P03 report](../../docs/plans/20261101-p03-shell-workspace-and-ask-relocation.md)
- [P04 report](../../docs/plans/20261101-p04-evaluation-coverage-and-methodology.md)
- [P05 report](../../docs/plans/20261101-p05-feature-evidence.md)
- [P06 report](../../docs/plans/20261101-p06-dataset-catalog.md)
- [P08 report](../../docs/plans/20261101-p08-evidence-facets-and-detail.md)
- [P09 report](../../docs/plans/20261101-p09-qa-turn-state-and-inspection.md)
- [P10 readiness report](../../docs/plans/20261101-p10-readiness.md)
- [P09.1/P10.1 follow-up report](../../docs/plans/20261102-p09p10-ask-surface-and-hardening.md)
- [Local preview handoff](../../docs/deployment/local-preview-handoff.md)
- [Deployment pickup brief](../../docs/plans/20261101-deployment-pickup.md)
- [Cloudflare demo runbook](../../docs/deployment/cloudflare-demo.md)
- [Transfer and run on another machine](../../docs/deployment/transfer-and-run.md)
- [Normative specification](implementation-specification.md)
- [File map](implementation-map.md)
- [Phased plan](implementation-plan.md)
- [Interaction specification](interaction-spec.md)
- [Screen-data map](screen-data-map.md)
- [SVG index](README.md)
- [Validation record](validation.md)
