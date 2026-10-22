# Logfire explicit-export + P3-C canaries handoff — 2026-10-21

**Purpose: closing record for the approved core slice (T1–T3) of the [next-slice brief](20261021-next-slice-brief.md), and pickup point for the next thread.** Executed by parent + `glm-worker` (implementation) + `luna-reviewer` (review) per the owner-directed orchestration. The expansion tasks T4–T7 remain unconfirmed and untouched.

## What landed

- **T1 — Lock verification (read-only).** The pre-provisioned dirty-tree lock already carried exactly the approved family: `logfire==5.2.0`, OTel api/sdk/OTLP-exporters `1.45.1`, `protobuf 6.33.6`. Stanza-level diff vs HEAD is family-only (+5 packages, −`deprecated`, OTel/proto/semantic-conventions upgrades, protobuf 4.25.9→6.33.6); chromadb 1.5.5 / deepeval 3.9.7 / litellm / google-genai unchanged; installed dist-info versions match the lock; the logfire wheel SHA-256 matches the spike record. Report: `/tmp/qna-eval-logfire-canaries-24sEXz/t1-lock-report.md`.
- **T2 — Logfire as explicit-export destination.** `_make_hosted_exporter()` in `src/infra/telemetry.py` now constructs the official pinned `OTLPSpanExporter` (the exact transport logfire 5.2.0 uses internally) fully explicitly: config-derived endpoint (`origin + /v1/traces`), raw-token `Authorization` header (unchanged semantics), `timeout=shutdown_timeout_seconds`, `NoCompression`, `trust_env=False` session, `NoOpMeterProvider`. The hand-rolled `_ExplicitOTLPExporter` is deleted. Manual span model, `_NonThrowingExporter`, batch bounds, `SpanLimits`, content guards, local/disabled modes, and token-less startup are unchanged. No `logfire` import or configure path exists (AST-asserted by tests).
- **T3 — P3-C offline canaries.** New `tests/integration/telemetry/test_content_canaries.py`: secret/cookie/patient-ID/prompt canaries through span attributes (metadata mode), `record_case_content` in both content modes (including rejection paths: forbidden canary, consent/review, oversize, invalid IDs), error/retry attribute hygiene, application log output, and report/artifact paths (`telemetry_metadata.json`, `manifest.json`, budget-diagnostics report). New `tests/unit/infra/test_explicit_export_destination.py`: destination construction, env neutralization, payload hygiene, bounded lifecycle, no-logfire static guard. Both files are in the gate inventory.

## Review chain (GLM → Luna → repairs → Luna → repair → Luna)

1. First review: **approve with repairs** — M1 exporter-internal failure logs could leak collector-controlled text; M2 standalone `SYNTHETIC_BEARER_TOKEN_CANARY` passed the content guard; M3 env-neutralization overstated (OTel 1.45.1 merges extra `OTEL_EXPORTER_OTLP_HEADERS` keys and always reads TLS cert vars) + fail-closed gap; L1 deadline tolerance; L2 substring static test.
2. Repair round 1 closed M2 (guard extension + regression), M3 (accurate comment + `_RESIDUAL_OTLP_ENV_VARS` fail-closed guard, 8 verified names), M1 (log-sanitizing filter on the pinned exporter logger namespace, install/remove lifecycle), L1, L2.
3. Re-review: M2/M3/L1 closed; P2 remained — filter installation was fail-open. Repair round 2 made installation raise (install-before-construct, undo on failure, degrade path → unavailable) + env-test isolation + dynamic-loader AST checks.
4. Second re-review: P2 and env isolation closed; final P3 — keyword form `import_module(name="logfire")` evaded the AST guard. Fixed by parent exactly as prescribed (keyword-aware check + regression assertion). Verdicts preserved verbatim in `/tmp/qna-eval-logfire-canaries-24sEXz/review.md`.

## Verification (snapshot `/tmp/qna-eval-logfire-canaries-24sEXz/`)

- Isolated gate via `scripts/verify_phase123_offline.sh` only: **1,717 passed / 5 warnings, zero skips, ×2 fresh processes** (`gate-final5*.log`; progression 1,673 → 1,700 → 1,715 → 1,716 → 1,717 across repair rounds; the one intermediate failure `gate-first.log` — docstring literal tripping the static test — was repaired and is kept as honest evidence).
- Statics: Ruff check/format 332 files; MyPy 159 src files; 4 import contracts kept; docs consistency passed.
- Preservation (`preservation.py`, allowed-set comparison): tracked diffs outside {gate script, docs/README.md} unchanged; prior untracked bytes intact except the slice-owned telemetry.py; status paths preserved; `uv.lock`/`frontend/bun.lock` identical to slice start.
- Slice-attributable telemetry diff vs reconstructed slice-start image: `final-telemetry.diff` (9 hunks); test diffs `final-t2tests.diff`, `final-t3tests.diff`.

## Residuals and explicit pre-export gates (not closed by this slice)

- **OTLP environment residual:** extra `OTEL_EXPORTER_OTLP_HEADERS` keys and TLS CA/client-cert env vars are not constructor-neutralizable in OTel 1.45.1. The slice now **fails closed** on all 8 residual names when hosted export is constructed (telemetry degrades to unavailable). Hosted export additionally remains separately permissioned per the 2026-10-20 policy (dedicated project, 30-day retention, minimal access, metadata-only first) — none of it configured or executed here.
- Filter-install fault model is raise-instead-of-append; a pathological append-and-raise `addFilter` is out of model (documented in `repair2-report.md`).
- Non-`Exception` `BaseException` during hosted construction bypasses the degrade handler (pre-existing shape, unchanged).
- The reviewer noted (Info): `summary.json` artifact path untested by canaries (candidate for T4 blind-spot batch).

## Exit accounting (do not overclaim)

**Closed by this slice:** the P3-A dependency/adoption item (lock family + explicit-export destination with capture-off and bounded lifecycle verified against pinned versions) and the P3-C offline-canary item. **Still open, unchanged:** identity-authenticated review authority (until the named reviewer's first manifest), judge-ID pinning and matched-run capture (D17 remainder), full budget admission (chat/in-flight/overage), hosted destination setup + hosted smoke (with the env-sanitization gate above), Docker/container smoke, reranker assets, live baselines, Phase 4, and the expansion tasks T4–T7 (each needs its own bounded plan + approval; T4 should not be treated as closing the OTLP env residual — that gate is hosted-export-specific and already implemented fail-closed).

## Next thread pickup

Confirm T4 (review-polish batch) scope and present its bounded plan per the [next-slice brief](20261021-next-slice-brief.md) ownership map and conflict warnings (keep T4 off `telemetry.py`; T6 imports `retrieval_eval.py` helpers only). Starting state to verify: HEAD `a4edbc8dae9e73ac8653aa47062e65fe8e0be84a`, dirty tree untouched, gate 1,717 ×2 (`gate-final5*.log`), statics as above.
