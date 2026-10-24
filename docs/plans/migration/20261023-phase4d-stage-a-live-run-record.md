# P4-D Stage A live run record — 2026-10-23 (incomplete: capability rejection at op 7)

**Two admission runs were made under the owner's Stage A permission** (the first before the partial-report repair, second after; cumulative 12 POSTs admitted, ≈ **$0.0155 quota-value reserved of the $1 allocation**, **$0 cash**, reservations never released). The second run's sanitized report is authoritative and reproduced below in structure. Credential sourcing was owner-instructed via `.env` sourced blindly into the process environment (value never displayed or stored); this is recorded as a deviation from the handoff's "owner runs in their own shell" line.

## Outcome: STOP per the execution addendum (capability rejection)

- Ops 1–6 **PASSED**: text, stream (TTFT 2.68 s baseline / 3.86 s adapter), and mid-stream cancellation for BOTH implementations — the P4-A unknowns "does the Go route stream?" are answered **yes**, with honest `User-Agent` + opaque `x-opencode-session` accepted and usage reported by the route for non-cancelled ops (cancellations/failed op retain reservations, `missing_usage_count: 3`).
- Op 7 `baseline_structured_json_object` **FAILED**: pydantic `ValidationError` after 1 admitted POST — the route/model response did not parse into the frozen one-field `answer` schema under the baseline client's JSON-object mode. Fail-fast stopped the run; **ops 8–9 (adapter `tool` and `native-json-schema` structured modes) were never reached and remain unverified.**
- Per the addendum stop rule ("unsupported capabilities return to the owner, never downgrade or substitute") Stage A is recorded **incomplete**, not passed. The error detail is intentionally undisclosed by the sanitizer; a diagnostic variant would need separate approval.

## Effective settings (as run)

Route `https://opencode.ai/inference/go/openai/v1`, model `mimo-v2.6-flash`, temperature 0.7, max output 2048, 30 s request timeout, one transport attempt, 12-POST cap, `LIVE_REFERENCE_RATES` ($0.14/$0.28 per M — historical P4-A reference, not verified billing). Frozen hashes: see run metadata (`answer_schema_sha256: bd19e9c3…`, `prompt_text: 86178557…`, `prompt_stream: fb3cf724…`, system `4493cd2e…`, template `c5f55529…`). Op-level payload digests are in the run output; representative: baseline text `785f4f74…`, adapter text `40e26989…`.

## Consequences for the plan

- **Stage B** was already blocked (D11 materialization); unchanged.
- **Stage C** was blocked (judge pinning, review authority); now ALSO blocked on structured-output capability: the frozen matched configuration cannot claim parity while the baseline's structured mode fails and the adapter's modes are unverified.
- **Serving/adapter posture unchanged**: the adapter remains opt-in; no default switch; `pydantic-ai` generation preflight stays fail-closed.

## Owner decision requested (pick one)

1. **Accept Stage A as incomplete/rejected** — record and move on; text+stream+cancel verified for both implementations is the deliverable.
2. **Amend the frozen sequence** with one third bounded run covering ONLY ops 8–9 (adapter `tool`, adapter `native-json-schema`; 2–4 POSTs, ≈ $0.0026 quota-value reservation) to complete the protocol picture. Requires explicit owner approval because it skips the failing op 7 — recorded as an owner amendment, not a pass.
3. Approve a sanitized-diagnostic variant (prints the validation error path, still no raw response bodies) to learn WHY op 7 failed before deciding.
