# P01 — Archive identity and metric semantics

**Status:** implemented offline; review/acceptance pending. Application changes are limited to the approved P01 slice. No deployment, live provider call, hosted export, data/index mutation or default/provider change was performed.

**Approval reference:** user approved P01 and the deliberate experiment-endpoint **401** change; all other gates remain pending.

## Scope delivered

1. Experiment list/results/config handlers require authenticated request state. This applies even when no API-key middleware records are configured.
2. Experiment reads use canonical `PROJECT_ROOT` paths rather than the process working directory.
3. Report listing/read uses a bounded 5 MiB buffer; SHA-256 is calculated from the same bytes parsed as JSON.
4. Only one explicitly registered mismatched pair is associated: report `medical_semantic_chunking_exp` ↔ config `medical_semantic_exp`. No fuzzy matching or effective-runtime inference.
5. Results add `_artifact` byte-revision provenance while preserving archived root fields and `comparable: false`.
6. Malformed, unsupported, oversized, invalid-ID and symlink-escaping inputs are unavailable/422 rather than valid-looking empty archives.
7. Frontend metric utilities distinguish missing/invalid/zero, expose coverage states and separate score-point from relative deltas.
8. Existing experiments page no longer renders absent numeric metrics as zero; deltas follow metric direction; archived winner is labelled historical and not promoted.
9. The known config/report mismatch can be selected in the existing experiments page only through the server-declared `config_ref` association.

## Files changed

| File | Change |
|---|---|
| `src/app/routes/experiments.py` | Route auth, canonical roots, bounded reads, containment, archive metadata/schema status, explicit association |
| `src/experiments/config.py` | Optional pre-read `raw_text` for `load_experiment_file`; existing callers unchanged |
| `tests/unit/app/test_new_routes.py` | Auth/no-middleware tests, report identity/digest, association, invalid/malformed/oversized/symlink/config bounds |
| `frontend/src/lib/types.ts` | Additive archive provenance, coverage, metric-definition and delta types |
| `frontend/src/lib/utils/eval.ts` | Finite/count validation, coverage normalization/aggregation, direction-aware metric deltas |
| `frontend/src/lib/utils/metric-definitions.ts` | Metric family/unit/direction mapping; legacy vs reviewed-evidence vs answer-judge semantics |
| `frontend/src/lib/utils/research.ts` | Known-legacy archive adapter; explicit historical binding remains unestablished |
| `frontend/src/routes/experiments/+page.svelte` | Null-safe table/chart values, historical winner wording, absolute/relative delta display, explicit association lookup |
| `frontend/src/lib/components/MetricChart.svelte` | Permit missing chart values (`null`) instead of substituting zero |
| `frontend/tests/research-metrics.spec.ts` | Pure coverage, delta and actual local archive fixture checks |
| `frontend/tests/experiment-metrics.spec.ts` | Browser check for mismatch association, missing metric, units and historical winner disclosure |
| `docs/20260424-openapi-swagger.yaml` | Experiment auth/401/422 responses and additive report metadata documentation |

No RAG, ingestion, model/provider, index, default profile, dependency or lockfile file changed.

## Verified actual archive behavior

Read-only inspection through the updated route against the existing local archive produced:

```json
{
  "report_id": "medical_semantic_chunking_exp",
  "report_sha256": "0e47dc7612ebc7cc897ee7844ddf61c6413b78f8d3b67cb3c4a1f0a966a84d34",
  "schema_kind": "legacy_feature_addition",
  "availability": "available",
  "config_ref": "medical_semantic_exp",
  "config_binding": "explicit_archive_association",
  "case_records_availability": "not_exposed_by_report_api",
  "comparable": false
}
```

Actual baseline faithfulness remains mean `0.9798534799`, count `15`, error count `42`; the UI adapter reports 268 measured/342 expected metric slots and 74 failed across six answer metrics. It does not invent 42 per-case failures or a complete seven-factor score.

## Tests run

| Command | Result |
|---|---|
| `bash scripts/check_backend.sh fast tests/unit/app/test_new_routes.py tests/unit/app/test_evaluation_routes.py tests/unit/evals/test_history_comparability.py -q` | **65 passed** |
| `bash scripts/check_backend.sh fast` | **2322 passed, 1 skipped, 115 deselected**; skip is the existing optional DeepEval/live-key test |
| `bash scripts/check_backend.sh lint` | **passed** (Ruff, format, mypy, imports, Bandit, docs consistency) |
| `npm --prefix frontend run check` | **0 errors, 0 warnings** |
| `npm --prefix frontend run build` | **passed** |
| `npm --prefix frontend run test -- tests/experiment-metrics.spec.ts tests/research-metrics.spec.ts` | **11 passed** |
| Full `npm --prefix frontend run test` | **58 passed, 9 skipped, 2 failed in untouched chat/pipeline specs** |

The two full-suite failures are inherited, not introduced in P01:

- `frontend/tests/pipeline.spec.ts:249` expects the old uncalibrated “Overall Confidence” wording; the current UI already says “Pipeline diagnostic (uncalibrated)” in untouched `PipelinePanel.svelte`.
- `frontend/tests/pipeline.spec.ts:562` uses a strict `.message` locator when two message nodes exist; reproduced independently after P01. The page snapshot showed the welcome state. This is in untouched chat code/tests.

No P01-specific regression was found. Those tests were not modified because fixing them is outside this slice.

## Backward compatibility / migration notes

- Experiment route callers that do not supply authenticated request state intentionally receive **401**. Authorized clients retain raw result roots (`winner`, `baseline`, `variants`, `config`).
- Report `winner` in list metadata remains a historical string. No new eligibility is asserted.
- `file` values in experiment listings are now repository-relative rather than absolute host paths. `report_id` is the stable accepted identifier for `/results`; `experiment_id` remains the config identifier.
- The current catalog/report identifier is filename-based; the digest covers the exact current bytes only. It is not historical dataset or index identity.
- `config_ref` is an explicit archive association, not proof of effective runtime settings.
- Document/evaluation comparison behavior was not changed.

## Residual risks / pending work

- P01 does not implement a login UI or private gateway; authenticated operator delivery remains G-AUTH.
- P02–P10 remain to do. The owner has asked a new agent thread to continue all remaining slices; G-AUTH, G-FIXTURES and G-ROUTES still require explicit decisions.
- The local archive's case-run directories remain absent; observed per-case evidence is not fabricated and dataset binding stays `not_established`.
- The uncalibrated-confidence and New Chat test debt noted here was closed in P09; this report remains the historical P01 record.

## Next checkpoint

**Superseded (2026-11-01):** P01–P10 are now implemented offline. See [P10 readiness](20261101-p10-readiness.md), the [continuation handoff](../../assets/svg/continuation-handoff.md) and the [deployment pickup brief](20261101-deployment-pickup.md). The confidence/New Chat test debt noted above was closed in P09; authenticated release remains pending.
