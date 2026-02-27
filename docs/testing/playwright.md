# Playwright Testing

## Overview

The project uses Playwright for end-to-end testing of the frontend application. Tests are located in `frontend/tests/`.

## Running Tests

### Prerequisites

1. Install Playwright browsers:
   ```bash
   cd frontend && npx playwright install
   ```

2. Ensure services are running (see [Running the Application](../README.md#running-the-application))

### Run All Tests

```bash
cd frontend && bun run test
```

### Run Tests with UI

```bash
cd frontend && bun run test:ui
```

### Run Tests in Headed Mode

```bash
cd frontend && bun run test:headed
```

### Run Specific Test File

```bash
cd frontend && bun run test chat.spec.ts
```

### Run Specific Test

```bash
cd frontend && bun run test --grep "chat page loads"
```

### Generate HTML Report

```bash
cd frontend && bun run test:report
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLAYWRIGHT_BASE_URL` | `http://localhost:5173` | Frontend URL |
| `API_URL` | `http://localhost:8001` | Backend API URL |

Example:
```bash
PLAYWRIGHT_BASE_URL=http://localhost:5174 bun run test
```

## Test Files

### chat.spec.ts

Tests for the main chat interface.

| Test | What it Checks |
|------|----------------|
| `chat page loads correctly` | Page title, header, welcome message, input area |
| `can type in input field` | Input field accepts text |
| `send button is disabled when input is empty` | Send button disabled state |

### pipeline.spec.ts

Tests for pipeline visualization and API integration.

| Test Suite | Tests |
|------------|-------|
| Pipeline Visualization | Toggle visibility, enable/disable, button appearance |
| Pipeline Panel | Panel visibility, source display |
| API Integration | Health endpoint, chat endpoint, pipeline parameter |
| Error Handling | Empty input, New Chat clears messages |

## Configuration

The Playwright config is in `frontend/playwright.config.ts`. Key settings:

- `testDir`: `./tests`
- `timeout`: 30 seconds per test
- `projects`: chromium, firefox, webkit
- `webServer`: Automatically starts dev server in CI

## CI Usage

In CI environments, tests run with:
```bash
CI=true bun run test
```

This ensures:
- Tests don't use `reuseExistingServer`
- Parallelism is limited to prevent flakiness
- Forbid test `.only` flags

## Known Issues

1. **Button disabled state**: Some tests fail due to Svelte 5 reactivity issues with the send button's disabled attribute. The tests expect the button to be disabled when input is empty, but the binding may not update correctly in test environment.

2. **API URL**: The frontend uses `VITE_API_URL` environment variable. For docker, set this to `http://localhost:8001`.

3. **Firefox/Webkit**: Not installed by default. Install with:
   ```bash
   npx playwright install firefox webkit
   ```
