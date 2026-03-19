# Anonymous Sessions And History

The public chat experience uses a server-issued anonymous session cookie instead of a client-generated session ID.

## How It Works

- The first `POST /chat` or `GET /history` request receives a `chat_session_id` cookie.
- The backend uses that cookie to find the current conversation history.
- The frontend does not store chat session IDs in `localStorage`.
- Legacy `session_id` request fields and `/history/{session_id}` paths are deprecated and ignored for ownership.

## Current Endpoints

- `POST /chat`
- `GET /history`
- `DELETE /history`

Legacy compatibility routes still exist:

- `GET /history/{session_id}`
- `DELETE /history/{session_id}`

These routes operate on the current cookie-bound session and should not be used for new integrations.

## Retention

- Cookie lifetime is controlled by `CHAT_SESSION_COOKIE_MAX_AGE_SECONDS`.
- File-backed history retention is controlled by `CHAT_HISTORY_TTL_SECONDS`.
- Expired sessions are pruned during normal history reads and writes.

## Security Properties

This model improves on the old client-generated session ID flow because:

- one browser cannot fetch another browser's history just by guessing an ID
- the browser cannot read the `HttpOnly` session cookie from JavaScript
- starting a new chat rotates to a fresh anonymous session

## What It Does Not Do

- It does not identify a real user across devices.
- It does not share history across browsers.
- It does not provide account recovery or login.
- It does not support multi-instance shared storage.
