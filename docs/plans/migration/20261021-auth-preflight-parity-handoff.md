# Authentication preflight parity closure — 2026-10-21

Follow-up to the [offline hardening closure](20261021-offline-hardening-handoff.md). The identified P2 preflight/runtime legacy-hash mismatch is closed; no runtime authentication policy changed.

## Delivered

- `src/cli/preflight.py`: legacy SHA256 JSON hashes count toward usable authentication readiness only in development, matching runtime request verification. Uppercase hashes and surrounding whitespace follow runtime normalization. Whitespace-only effective record IDs are rejected.
- Truthy JSON configuration takes precedence over plain keys, as at runtime; ignored plain keys cannot mask unusable JSON. The report marks ignored plain keys not ready and not required by API authentication.
- `tests/unit/cli/test_preflight.py`: 20 additional cases cover production/staging legacy rejection, development acceptance/case normalization, inactive records, mixed records, JSON precedence, isolated whitespace-ID failure, padded hash, bcrypt-only format readiness, development aliases and value-free serialization. Existing gate inventory already includes this file.

Bcrypt-prefix readiness is a static configuration-shape check, **not proof of successful authentication**. Runtime startup can load legacy records; outside-development request verification rejects them. The fix does not claim startup itself previously rejected every legacy-only configuration. Development/no-key behavior, actual credentials, settings types and runtime security code remain unchanged.

## Verification

GLM implementation → Luna repairs requested (effective-source reporting and isolated negative test) → repair → Luna **CLOSED**, no actionable findings. Final reviewer response retained verbatim in `/tmp/qna-eval-auth-parity-eWAZBF/closure-review.md`; worker and repair reports alongside it.

Parent: Ruff/format (337 files), MyPy `src` (160 source files), four import contracts, docs consistency. Isolated offline gate **1,814 passed / five warnings ×2**, fresh processes (`gate-final.log`, `gate-final-repeat.log`). Closing preservation passes for out-of-scope tracked patches, existing untracked bytes, status paths, new-path allowlist and both lock digests. No live calls, credential inspection, hosted setup, user-data changes, default/policy/dependency changes or commits.

Evidence limitation: these source/test files were already untracked at snapshot time. Baseline hashes were retained, not their full contents; the reviewer checked current files and source contracts rather than claiming an independently reconstructed before/after diff. Remaining nonblocking test blind spots: full report-field assertions for the plain-only alternative and unusable-JSON-plus-plain branch are not both pinned independently; inspected branch logic is consistent.

## Scope closure

T1–T7 plus the approved logging/assessment and auth-parity follow-ups are delivered. Review-context revalidation is deliberately retained; API-key `SecretStr` migration remains optional coordinated hardening, not an unfinished approved change.

Operational exits remain: real review-authority exercise, materialized provenance-carrying corpus/index, judge pinning and matched baseline, budget limitations, hosted configuration and permissioned smoke, Docker smoke, reranker assets, live baselines and Phase 4. No whole-phase completion, authenticated reviewer identity or global privacy certification is inferred.
