# Documentation Index

This folder is organized by purpose, not by chronology.

## Current Docs

- `quickstart.md` for local setup and core workflows
- `local-workflows.md` for the canonical local runbook for ingestion, serving, and evals
- `configuration.md` for environment variables and deployment-facing settings
- `public-app-deployment.md` for publishing the app with anonymous public access
- `anonymous-sessions.md` for cookie-backed chat history behavior
- `admin-api-auth.md` for optional backend API-key usage
- `architecture/overview.md` for the repository map
- `architecture/pipeline-strategies.md` for comprehensive pipeline DAGs and strategy reference (HyDE vs HyPE, chunking, search modes)
- `architecture/rag-system.md` for ingestion and retrieval flow
- `evaluation/pipeline_quality_assessment_plan.md` for the implemented evaluation system
- `testing/backend-tests.md` for backend test commands
- `testing/playwright.md` for frontend E2E usage
- `data/sources.md` for the ingestion source inventory

## Plans

- `plans/` for active design documents worth keeping around

## Historical Reports

- `reports/` for dated implementation notes, summaries, and historical snapshots
- Recent cleanup notes and one-off implementation summaries should live in `reports/YYYY-MM/`, not at repo root.

## Conventions

- Keep current reference material in the top-level sections above.
- Move completed, dated writeups into `reports/`.
- Remove or relocate one-off verification notes instead of leaving them at repo root.
