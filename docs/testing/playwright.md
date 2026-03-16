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
- The default Playwright frontend URL is `http://localhost:5174`.
- The backend API is expected at `http://localhost:8000` unless you override the frontend API configuration.

## Useful Commands

```bash
cd frontend
npm run test -- --grep "chat page loads"
npm run test -- tests/chat.spec.ts
```

## Coverage Areas

- `chat.spec.ts` covers the main chat flow and core controls.
- `pipeline.spec.ts` covers pipeline UI behavior and API interaction.
- `quality-metrics.spec.ts` and `visual-verification.spec.ts` cover evaluation dashboard rendering.

## Notes

- The current Playwright config runs Chromium only.
- If you point Playwright at an already-running frontend, set `PLAYWRIGHT_BASE_URL`.
- Several specs make direct requests to the backend API, so `uv run python -m src.cli.serve` must be running on port `8000` unless you override `API_URL`.
