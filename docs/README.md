# Documentation Index

This folder is organized by purpose, not by chronology.

## Reference Guides

- `quickstart.md` — Get the project running locally with minimal setup
- `local-workflows.md` — Canonical local runbook for ingestion, serving, and evals
- `configuration.md` — Full environment variable and deployment settings reference
- `dependencies.md` — Dependency management, extras, and troubleshooting
- `wandb-metrics-verbosity.md` — Weights & Biases metrics logging levels

## Architecture

- `architecture/overview.md` — Repository map and system structure
- `architecture/pipeline-strategies.md` — Pipeline DAGs and strategy reference (HyDE vs HyPE, chunking, search modes)
- `architecture/rag-system.md` — Ingestion and retrieval flow

## Deployment

- `public-app-deployment.md` — Publishing the app with anonymous public access
- `anonymous-sessions.md` — Cookie-backed chat history behavior
- `admin-api-auth.md` — Optional backend API-key usage

## Data

- `data/sources.md` — Ingestion source inventory

## Evaluation

- `evaluation/pipeline_quality_assessment_plan.md` — Implemented evaluation system reference

## Testing

- `testing/backend-tests.md` — Backend test commands
- `testing/playwright.md` — Frontend E2E usage

## Plans

Active design documents worth keeping around:

- `plans/2026-03-20-medical-intake-agent.md` — Health parameter extraction from conversation
- `plans/2026-03-20-code-review-remediation.md` — Code review issue remediation plan
- `plans/technical-roadmap.md` — Strategic roadmap and enhancement proposal

## Historical Reports

Dated implementation notes, summaries, and historical snapshots:

- `reports/2025-02/` — Early documentation improvements
- `reports/2025-03/` — Frontend dashboard implementation phases
- `reports/2026-02/` — Pipeline visualization, Playwright testing, verification summaries
- `reports/2026-03/` — RAG pipeline reports, tracing improvements, completed plans, operational how-tos

## Conventions

- Keep current reference material in the top-level sections above.
- Move completed, dated writeups into `reports/YYYY-MM/`.
- Remove or relocate one-off verification notes instead of leaving them at repo root.
