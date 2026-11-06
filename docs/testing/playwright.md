# Playwright Testing

Frontend E2E tests live in `frontend/tests/`.

## Install

```bash
cd frontend
npm install
npx playwright install
```

## Run

Start the backend first in another terminal:

```bash
uv run python -m src.cli.serve
```

Then run the frontend suite:

```bash
cd frontend
npm run test
```

Useful variants:

```bash
cd frontend
npm run test:ui
npm run test:headed
npm run test:debug
npm run test:report
```

## Local Behavior

- The Playwright config starts a local frontend server automatically if `PLAYWRIGHT_BASE_URL` is not set.
- The default Playwright frontend URL is `http://127.0.0.1:4173` (see `frontend/playwright.config.ts`).
- Ordinary offline specs stub API responses; a live backend is not required. Set `PLAYWRIGHT_BASE_URL` to reuse an already-running frontend.

## Useful Commands

```bash
cd frontend
npm run test -- --grep "chat page loads"
npm run test -- tests/chat.spec.ts
```

## Coverage Areas

- `chat.spec.ts` covers the main chat flow, incomplete/error terminal states and draft navigation.
- `pipeline.spec.ts` covers recorded pipeline inspection and panel behavior.
- `sse.spec.ts` covers stream decoding and API URL resolution as pure checks.
- `research-workspace.spec.ts`, `evaluation-coverage.spec.ts`, `feature-evidence.spec.ts`, `dataset-catalog.spec.ts` and `evidence-browser.spec.ts` cover the research routes.
- `readiness.spec.ts` covers the skip link, mobile overflow and zoom-equivalent width checks.
- `quality-metrics.spec.ts` and `visual-verification.spec.ts` cover evaluation dashboard rendering.

## Notes

- The current Playwright config runs Chromium only.
- If you point Playwright at an already-running frontend, set `PLAYWRIGHT_BASE_URL`.
- Most specs stub browser API responses and deny unstubbed API traffic. Do not point ordinary design/readiness runs at a provider-backed server.
