# T7 data-processing boundaries handoff — 2026-10-21

T7 of the [next-slice brief](20261021-next-slice-brief.md) is delivered. See [data-processing boundaries](../../data-processing-boundaries.md); previous checkpoint: [T6](20261021-t6-review-manifest-tool-handoff.md).

## Delivered scope

Docs only: source-referenced inventory of chat/history/cookies, browser traces, logs, evaluation artifacts and review manifests, disk and volatile caches, local/optional remote Chroma, telemetry, providers, historical W&B paths, and credential-setting boundaries. Each distinguishes content, access, retention/deletion and third-party processing. Includes explicit **no automatic PHI scrubbing**, public/synthetic-only inputs, no cascading deletion, lazy history expiry, active-turn deletion conflicts, and operator access/retention/deletion checklist.

Approved Logfire policy (dedicated project, 30-day retention, minimal named access, metadata-only smoke first) is not represented as configured or tested. Approved case content can remain in local bounded memory even without hosted export. The eight residual OTLP header/certificate/key variables are checked for presence, not sanitized/unset.

Parent updated `docs/README.md`, `docs/anonymous-sessions.md`, and `phases.md`; no runtime code/configuration, locks, user data, credentials or operational settings changed. No deletion or hosted/provider calls performed.

## Review and verification

GLM authoring → Luna approve-with-repairs → two bounded documentation repair rounds → **T7 CLOSED**, no actionable documentation findings. Final verdict preserved verbatim in `/tmp/qna-eval-t7-boundaries-TpLUzl/review.md`; worker/repair reports in the same snapshot.

Parent verification: Ruff/format, MyPy `src`, four import contracts, docs consistency; isolated gate **1,787 passed / five warnings ×2**, fresh processes via `scripts/verify_phase123_offline.sh`. Snapshot contains binary starting patch, NUL-delimited `-uall` status, 111 existing untracked-file hashes, both lock digests, logs and preservation checker. Closing allowed-set preservation verified.

## Disclosed source risks — not repaired by documentation

- At T7 closure, conditional HyDE/query-expansion logs could include raw queries and exception strings. This was subsequently repaired in the [offline hardening follow-up](20261021-offline-hardening-handoff.md); sanitized owned paths still do not certify all logs.
- No-key development configuration bypasses evaluation API-key enforcement; production startup requirements are distinct.
- Application API-key configuration fields are plain strings rather than all being `SecretStr`.
- History deletion can fail with 409 during an active turn; successful deletion does not remove artifacts, backups, caches, or remote/provider copies.

## Exit accounting

All T1–T7 tasks of this brief are delivered; neither whole Phase 3 nor operational privacy controls are certified. Review-authority exercise, corpus/index materialization with provenance, D17 judge pinning, budget limitations, hosted destination/region/access/retention setup and smoke, Docker smoke, reranker assets, live baselines and Phase 4 remain open. Actual provider/remote-store deletion and backup lifecycle require independent operational verification. No runtime or hosted privacy guarantee is inferred from this documentation.
