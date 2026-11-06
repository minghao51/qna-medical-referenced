# Implementation-package review

## Scope and status
Read-only specification/map review by Codex `gpt-5.6-luna` using the previously verified explicit fallback, followed by Sol's direct source checks and document corrections. This reviewed a proposed implementation contract, not implemented application code. The plan/starting brief were being drafted concurrently with the review; final link checks were performed afterward.

## Findings addressed in the specification and plan

| Finding | Resolution / remaining gate |
|---|---|
| Experiment endpoints lack explicit authenticated-state enforcement | P01 now explicitly proposes guard coverage for list/results/config. New401 behavior for unauthenticated/no-key callers is disclosed as an intentional change requiring slice approval. G-AUTH still governs real private UI delivery. |
| Runtime catalog roots were underspecified | Fixed trusted roots from `src/config/paths.py`, literal logical ID→filename mapping, no CWD/request-selected path, no ensure_dirs side effect, bounded same-byte hashing/parsing and containment tests. |
| Fixtures absent from default image | Availability explicitly deployment-dependent; six exact approved fixture filenames listed; G-FIXTURES and missing-image tests required. No hardcoded frontend replacement. |
| Legacy eval hydrates latest before historical selection resolves | Explicit selection becomes authoritative before dependent fetches; rendered identity must match loaded data, refresh stays scoped and runs outside the current history page can load directly. |
| Current report IDs/digests not yet provided | Current filename/path-only identity distinguished from proposed byte identity; frontend cannot infer it from experiment_name. |
| Current fixture link could imply historical case binding | Added explicit historical_binding=not_established with reasons; verified binding remains deferred. No ordinal/text joins or reconstructed observations. |
| Global facets are not current API functionality | Additive field remains a backend prerequisite; old-backend fallback cannot invent an unfiltered All total. |
| Relative API base breaks current chatStreamUrl | Classified as existing migration defect; absolute HTTP(S), root-relative prefix and empty same-origin forms require tests and SSR-safe resolution. |
| Risk of duplicate metric normalization | research.ts is archive adaptation only; shared arithmetic/format/count logic stays in existing eval.ts/metric definitions. |

## Review claims not accepted without source verification
- Reviewer reported missing `docs/testing/playwright.md` and `docs/20260424-openapi-swagger.yaml`; both exist in this checkout, confirmed directly. They remain legitimate existing edit targets.
- Reviewer saw plan/next-agent references before their concurrent draft completed. Both final files now exist; final relative-link validation covers them.
- Sol separately read `src/app/routes/config.py`: `/config` already has an explicit authenticated-state guard. The spec distinguishes it from middleware-only `/documents`; no unverified auth exposure claim is carried forward.

## Additional planning safeguards
- Catalog/report reads are bounded and read-only; no provider/ingestion imports or new store client.
- P10 auth testing uses isolated/stubbed state or an already-approved runtime. Existing startup metadata-write issue F-03 is not silently repaired or exercised against D11 under a UI-validation pretext.
- No application implementation, deployment, live provider evaluation, fixture generation, lock change or data migration occurred in this phase.

## Validation evidence and next checkpoint
Existing focused baseline:58 tests passed in2.52s using the canonical offline test surface. Final package links/path anchors/task IDs were checked separately. New API/frontend behaviors still need implementation and acceptance testing.

Current checkpoint: P01 is implemented and offline-verified in its [completion report](../../docs/plans/20261101-p01-archive-identity-and-metric-semantics.md). Continue remaining tasks via [continuation-handoff.md](continuation-handoff.md). G-AUTH/G-FIXTURES/G-ROUTES and future cohort/case-binding/storage decisions remain unresolved—not implied complete.
