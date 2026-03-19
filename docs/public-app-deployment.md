# Public App Deployment

This guide covers the smallest reasonable setup for publishing the app without adding a full user account system.

## Recommended Baseline

- Put the backend behind Cloudflare Free.
- Keep backend API-key auth disabled for the public chat experience.
- Keep backend anonymous rate limiting enabled.
- Use the built-in anonymous session cookie for chat history isolation.
- Set a real production `CORS_ALLOWED_ORIGINS` value.
- Keep `TRUST_PROXY_HEADERS=false` unless traffic only reaches the backend through your trusted proxy/load balancer.

## Suggested Production Settings

```dotenv
ENVIRONMENT=production
CORS_ALLOWED_ORIGINS=https://your-frontend.example.com
RATE_LIMIT_PER_MINUTE=60
ANONYMOUS_CHAT_RATE_LIMIT_PER_MINUTE=12
CHAT_SESSION_COOKIE_MAX_AGE_SECONDS=2592000
CHAT_HISTORY_TTL_SECONDS=2592000
TRUST_PROXY_HEADERS=true
```

Only set `TRUST_PROXY_HEADERS=true` when the app is actually deployed behind Cloudflare or another trusted reverse proxy.

## Cloudflare Free Setup

1. Add your domain to Cloudflare and move DNS to Cloudflare.
2. Proxy the backend hostname through Cloudflare.
3. Enable HTTPS and use strict origin TLS if possible.
4. Add a rate-limit rule for `POST /chat`.
5. Optionally enable Bot Fight Mode, but test it against your frontend and API traffic.
6. Keep the backend limiter enabled as a second layer.

## Session Model

- The backend now issues an anonymous `HttpOnly` chat session cookie.
- Chat history is scoped to that cookie, not a caller-supplied `session_id`.
- `DELETE /history` clears the current session and rotates to a fresh one.

## Remaining Limits

This setup is fine for a small public app, but it is still intentionally minimal:

- chat history is file-backed, not multi-instance shared
- rate limiting is still origin-local inside the app
- there is no end-user identity, moderation workflow, or abuse appeals flow

If traffic grows or you move to multiple backend instances, plan to revisit shared storage and edge-layer controls.
