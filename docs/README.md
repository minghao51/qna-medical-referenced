# Documentation Index

This folder is organized by purpose, not by chronology.

## Reference Guides

- `quickstart.md` — Prerequisites and first-time setup
- `local-workflows.md` — Canonical local runbook for ingestion, serving, and evals
- [Data sync and portability runbook](data-sync-runbook.md) — Off-machine R2 mirror, restore to another setup, and frozen-identity verification
- `configuration.md` — Full environment variable and deployment settings reference
- [Data-processing boundaries](data-processing-boundaries.md) — Content, access, retention, deletion, provider processing, and no-automatic-PHI-scrubbing limits
- `dependencies.md` — Dependency management, extras, and troubleshooting
- `wandb-metrics-verbosity.md` — Weights & Biases metrics logging levels
- `20260416-feature-flags.md` — Feature flags for retrieval and indexing (reranking, HyDE, HyPE, keyword extraction)

## Architecture

- `architecture/overview.md` — Repository map, runtime vs offline responsibilities, frontend overview
- `architecture/rag-system.md` — Ingestion and retrieval data flow, module ownership
- `architecture/pipeline-strategies.md` — Pipeline DAGs, configurable strategies, gap tracker

## Deployment

- `public-app-deployment.md` — Publishing the app with anonymous public access
- `anonymous-sessions.md` — Cookie-backed chat history behavior
- `admin-api-auth.md` — Optional backend API-key usage

## Data

- `data/sources.md` — Ingestion source inventory
- [Data sync and portability runbook](data-sync-runbook.md) — R2 mirror of corpus/raw/review, restore procedure, frozen-identity verification

## Evaluation

- `evaluation/pipeline_quality_assessment_plan.md` — Implemented evaluation system reference
- `feature_ablation_findings.md` — Latest feature-family ablation results on the 54-query benchmark (supersedes older ablation studies)

## Testing

- `testing/backend-tests.md` — Backend test commands
- `testing/playwright.md` — Frontend E2E usage

## Plans

Active design documents:

- [Multi-harness migration planning package](plans/migration/README.md) — Implementation spec, phased plan, decision register, and environment/API-key guide
- [Phase 4 fresh-session pickup brief](plans/migration/20261021-phase4-pickup-brief.md) — Next work: Pydantic AI / Go MiMo capability spike; staged approvals, no live calls yet
- [Auth preflight parity closure](plans/migration/20261021-auth-preflight-parity-handoff.md) — Latest verified implementation: legacy-hash/JSON-precedence readiness repaired; gate 1,814 ×2
- [Offline hardening closure](plans/migration/20261021-offline-hardening-handoff.md) — HyDE logging repaired; review-context/API-key assessments complete; gate 1,794 ×2
- [T7 boundary-documentation handoff](plans/migration/20261021-t7-boundaries-handoff.md) — T7 docs complete; operational privacy/hosted gates remain open
- [T6 review-manifest tool handoff](plans/migration/20261021-t6-review-manifest-tool-handoff.md) — T6 complete (offline schema-v1 attested-manifest authoring tool, fail-closed; gate 1,787 ×2)
- [T5 D11 frozen-identity snapshot handoff](plans/migration/20261021-t5-d11-snapshot-handoff.md) — T5 complete (offline identity builder, honest empty-corpus/index state)
- [T4 review-polish handoff](plans/migration/20261021-t4-review-polish-handoff.md) — T4 complete (error-code origin classification, budget dedup, single review-context computation, blind-spot tests)
- [Logfire explicit-export + P3-C canaries handoff](plans/migration/20261021-logfire-canaries-handoff.md) — Approved core slice T1–T3 complete (gate 1,717 ×2, review chain closed)
- [Next slice brief — Logfire/OTel adoption, P3-C canaries, expansion tasks](plans/migration/20261021-next-slice-brief.md) — Approved core slice T1–T3, 2026-10-20 decisions, orchestration change, and expansion task list
- [Phases 1–3 tracing handoff](plans/migration/20261020-evaluation-tracing-handoff.md) — Local evaluation/attempt tracing, logging repairs, isolated verification and remaining phase exits
- [Phases 1–3 integration checkpoint](plans/migration/20261019-phases-1-3-integration-handoff.md) — Historical lifecycle/evidence/accounting integration and dependency approvals
- [Gemini HTTPX repair handoff](plans/migration/20261017-gemini-httpx-fix-handoff.md) — Historical transport-only verification and scoped review
- [Prior SDK retry/cleanup batch](plans/migration/20261017-p1-c3a-handoff.md) — Original C3a delivery and transport finding, resolved for the generation adapter in the follow-up
- [Guard-review repair](plans/migration/20261017-review-repair-handoff.md) — Nullable detail-view/median fixes, earlier verification and blocked browser cases
- [Prior guard batch](plans/migration/20261016-guard-batch-handoff.md) — Security/history guards and isolated Logfire compatibility research
- [Guard-batch Luna xhigh review](plans/migration/20261016-guard-batch-review.md) — Original findings, subsequently repaired and re-reviewed; browser execution remains unverified
- [Logfire compatibility spike](plans/migration/20261016-logfire-compatibility-spike.md) — Exact candidate/dependency effects, network-denied SDK probes and adoption blockers
- [Historical resume scope](plans/migration/20261016-phases-1-3-resume-handoff.md) — Prior pause, approved batch, D17 `baseline` and dirty-tree preservation
- `plans/20260416-medical-copilot-design.md` — Multi-modal medical AI co-pilot design
- `plans/20260416-phase1-exploration-design.md` — Phase 1 exploration design

**Archived plans** (completed or superseded):
- `archive/plans/` — Historical design documents (technical roadmap, code review remediation, medical intake agent)

## Historical Reports

Dated implementation notes, summaries, and historical snapshots are now in `archive/`:

- `archive/reports/2025-02/` — Early documentation improvements
- `archive/reports/2025-03/` — Frontend dashboard implementation phases
- `archive/reports/2026-02/` — Pipeline visualization, Playwright testing, verification summaries
- `archive/reports/2026-03/` — RAG pipeline reports, tracing improvements, completed plans, operational how-tos
- `archive/handoffs/` — Historical handoff documents (feature ablation, phase 2 followups, ablation study)

## Archive Structure

Historical documentation organized by type:

- `archive/reports/2025-02/` — Early documentation improvements
- `archive/reports/2025-03/` — Frontend dashboard implementation phases
- `archive/reports/2026-02/` — Pipeline visualization, Playwright testing, verification summaries
- `archive/reports/2026-03/` — RAG pipeline reports, tracing improvements, completed plans
- `archive/handoffs/` — Historical handoff documents (feature ablation, phase 2 followups, ablation study)
- `archive/plans/` — Historical design documents (technical roadmap, code review remediation, medical intake agent)

## Conventions

- Keep current reference material in the top-level sections above.
- Move completed, dated writeups into `archive/` by type.
- Remove or relocate one-off verification notes instead of leaving them at repo root.
