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

## Anonymous Chat Rate Limiting

`POST /chat` requests without an API key are limited by client IP, not by a browser
cookie:

- the rate-limit key is `anon-chat:<client_ip>`, resolved by
  `RateLimitMiddleware._get_client_ip()` (`src/app/middleware/rate_limit.py`)
- the former `anon_browser_id` cookie is no longer issued or read; the
  `anonymous_browser_cookie_name` setting is retained only so existing configuration
  files still parse, and it has no effect
- the limit is `APP__API__ANONYMOUS_CHAT_RATE_LIMIT_PER_MINUTE` (default 12/min)

Keying on the client IP closes the old bypass: because the cookie was client-controlled
and unsigned, any caller could send a fresh value on every request and stay under the
limit forever.

**Tradeoff — shared IPs.** All users behind one NAT, office network, CGNAT carrier
gateway, or corporate proxy share a single anonymous `/chat` bucket and can exhaust each
other's quota. Give that deployment a larger
`APP__API__ANONYMOUS_CHAT_RATE_LIMIT_PER_MINUTE`, put a shared frontend key in front of
`/chat`, or add edge-layer rate limiting with per-user signals.

**Proxy headers.** `_get_client_ip()` honors `X-Forwarded-For` / `X-Real-IP` only when
`APP__API__TRUST_PROXY_HEADERS=true`. Enable that **only** when every request reaches
the backend through your own trusted proxy or load balancer; otherwise a caller can
spoof the header and rotate the bucket on every request, restoring the bypass.

## Retention

- Cookie lifetime is controlled by `CHAT_SESSION_COOKIE_MAX_AGE_SECONDS`.
- File-backed history retention is controlled by `CHAT_HISTORY_TTL_SECONDS`.
- Expired sessions are pruned during normal history reads and writes; this is not scheduled erasure.
- `DELETE /history` can return 409 while a turn is active; require a successful response before treating history as cleared. Deletion does not cascade to logs, artifacts, backups, or provider copies.
- See [data-processing boundaries](data-processing-boundaries.md) for access, retention, deletion, and third-party limitations. There is no automatic PHI scrubbing.

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
