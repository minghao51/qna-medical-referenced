# P09 — Q&A turn state, stream correctness and recorded inspection

**Status:** implemented offline; review/acceptance pending. No deployment, live/paid provider call, hosted export, data/index mutation or public rollout was performed.

## Scope delivered

1. **Buffered SSE decoder** (`src/lib/utils/sse.ts`): handles UTF-8 split across chunks, LF/CRLF boundaries, multiple frames, multi-line `data:` fields, comments/other fields, and trailing-frame flush. Completion is classified only from an explicit `done` event; EOF without one stays incomplete.
2. **Chat stream integration**: the ask page now uses the decoder, appends only real content frames, records terminal error fields, and marks turns **pending → complete / incomplete / error**. Malformed events cannot turn partial output into success.
3. **URL resolution** (`normalizeApiBase` / `resolveApiUrl`): supports absolute http(s) bases, root-relative private prefixes and empty same-origin bases; rejects unsupported schemes. `chatStreamUrl` no longer calls `new URL` on an unresolved relative path.
4. **Composer safety**: labelled textarea, 2,000-character count, Enter/Shift+Enter with IME guard, sending disabled while pending, and a restrained `aria-live` completion/error announcement.
5. **Turn showcase**: each assistant turn shows status, source-entry count, breakdown availability and an **Inspect turn N** action. Selecting a turn opens its own recorded trace; the existing pipeline button stays compatible.
6. **In-memory conversation state** (`conversation-state.svelte.ts` + layout context): completed turns and draft survive ordinary in-app navigation; hard reload honestly loses sources/traces. In-flight work aborts on leaving; no module-global user state and no localStorage.
7. **Recorded inspection**: the pipeline panel replaces the synthetic confidence block with a recorded-evidence summary. Raw step details are available in a disclosure, and Context timing shows “not recorded” rather than a fabricated zero.
8. **Focus/Escape**: the panel focuses its close button on mount, closes on Escape and restores the previous focus on removal.
9. **Test debt closed**: the old confidence assertions were replaced with recorded-turn/panel assertions; the strict New Chat `.message` locator was replaced with a count check. Both inherited failures now pass.

## Files changed

| File | Change |
|---|---|
| `frontend/src/lib/utils/sse.ts` | New buffered decoder and terminal classifier |
| `frontend/src/lib/conversation-state.svelte.ts` | Layout-scoped in-memory conversation/draft state |
| `frontend/src/routes/+layout.svelte` | Provide chat context; removed competing layout title |
| `frontend/src/routes/ask/+page.svelte` | Decoder integration, statuses, turn summary/inspect, composer, navigation state |
| `frontend/src/lib/utils/api.ts` | API base normalization and safe URL resolution |
| `frontend/src/lib/components/PipelinePanel.svelte` | Recorded summary, raw details, recorded/placeholder timing, focus/Escape |
| `frontend/src/lib/components/StepCard.svelte` | Optional recorded-timing label |
| `frontend/src/lib/types.ts` | Message status type |
| `frontend/src/routes/eval/ablation/+page.svelte` | Own page title after layout title removal |
| `frontend/tests/sse.spec.ts` | New 8-test decoder/outcome/URL suite |
| `frontend/tests/chat.spec.ts` | Incomplete/terminal-error, draft-navigation tests; hydration waits |
| `frontend/tests/pipeline.spec.ts` | Recorded diagnostics, New Chat and hydration updates |
| `frontend/tests/markdown-rendering.spec.ts` | Hydration wait on `/ask` |

No backend, provider/default, data/index or lockfile change.

## Tests run

| Command | Result |
|---|---|
| `npm --prefix frontend run check` | 0 errors, 0 warnings |
| `npm --prefix frontend run build` | passed |
| `npm --prefix frontend run test -- tests/sse.spec.ts` | **8 passed** |
| `chat.spec.ts` + `pipeline.spec.ts` + `markdown-rendering.spec.ts` | **32 passed, 9 skipped** |
| Full Playwright | **101 passed, 9 skipped, 0 failed** |

## Residual risks / pending work

- Provider cancellation remains cooperative; aborting fetch does not prove immediate provider termination.
- The panel was a side drawer at P09 completion; the P09.1/P10.1 follow-up upgraded it to a named native modal dialog with focus containment, scroll lock and mobile full-width presentation.
- Durable turns/traces, provider-call trees, cost/TTFT and comparison cohorts remain explicitly out of scope.
- Hard reload loses sources/traces; the UI states this rather than reconstructing them.

## Next

P10 — full offline integration, responsiveness/accessibility review, authenticated-boundary readiness evidence and final rollback/release report.
