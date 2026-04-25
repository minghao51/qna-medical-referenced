# Documentation Index

This folder is organized by purpose, not by chronology.

## Reference Guides

- `quickstart.md` — Prerequisites and first-time setup
- `local-workflows.md` — Canonical local runbook for ingestion, serving, and evals
- `configuration.md` — Full environment variable and deployment settings reference
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

## Evaluation

- `evaluation/pipeline_quality_assessment_plan.md` — Implemented evaluation system reference
- `feature_ablation_findings.md` — Latest feature-family ablation results on the 54-query benchmark (supersedes older ablation studies)

## Testing

- `testing/backend-tests.md` — Backend test commands
- `testing/playwright.md` — Frontend E2E usage

## Plans

Active design documents:

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
