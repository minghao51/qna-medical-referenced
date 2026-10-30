# Public App Deployment

This guide covers the smallest reasonable setup for publishing the app without adding a full user account system.

## Recommended Baseline

- Put the backend behind Cloudflare Free.
- Set API keys for production. An API key must **never** be shipped in browser code or a `VITE_*` variable; if a key is used at all, inject it only server-side from a trusted reverse proxy (see [API Keys and the Public Frontend](#api-keys-and-the-public-frontend)). An app with API-key auth disabled is not a supported production posture (see [Authentication Reality](#authentication-reality)).
- Keep the anonymous `POST /chat` limiter enabled.
- Keep the general backend limiter enabled too; use privileged bypass keys for internal/admin traffic instead of setting `APP__API__RATE_LIMIT_PER_MINUTE=0`.
- Use the built-in anonymous chat session cookie for chat history isolation.
- Set a real production `APP__API__CORS_ALLOWED_ORIGINS` value.
- Keep `APP__API__TRUST_PROXY_HEADERS=false` unless traffic only reaches the backend through your trusted proxy/load balancer. Anonymous `/chat` limiting is keyed by client IP, so trusting proxy headers you do not control is an easy bypass.
- Prefer a same-site deployment for frontend and backend so the anonymous session cookie works cleanly in browsers.

## Configuration Names

`Settings` uses `env_prefix="APP__"` and `env_nested_delimiter="__"`, so every variable mirrors the nested settings path in upper case. There is **no** legacy flat-name mapping: names such as `CORS_ALLOWED_ORIGINS` or `RATE_LIMIT_PER_MINUTE` are ignored. See [`configuration.md`](./configuration.md) for the full reference.

## Suggested Production Settings

```dotenv
APP__APP__ENVIRONMENT=production
APP__API__CORS_ALLOWED_ORIGINS=https://your-frontend.example.com
APP__API__API_KEYS=replace-with-a-long-random-key
APP__API__RATE_LIMIT_PER_MINUTE=60
APP__API__ANONYMOUS_CHAT_RATE_LIMIT_PER_MINUTE=12
APP__API__CHAT_SESSION_COOKIE_MAX_AGE_SECONDS=2592000
APP__API__CHAT_HISTORY_TTL_SECONDS=2592000
APP__API__TRUST_PROXY_HEADERS=true
```

Only set `APP__API__TRUST_PROXY_HEADERS=true` when the app is actually deployed behind Cloudflare or another trusted reverse proxy, and only once that proxy overwrites/strips client-supplied `X-Forwarded-For`/`X-Real-IP` and direct backend access is blocked. See [API Keys and the Public Frontend](#api-keys-and-the-public-frontend).

## Authentication Reality

The global `APIKeyMiddleware` is a pass-through when no API-key records are configured (`APP__API__API_KEYS` / `APP__API__API_KEYS_JSON` empty): every request is admitted anonymously. Route-level checks still exist, so the effective behavior with auth disabled is:

| Path | With API keys configured | With API keys disabled |
|---|---|---|
| `/chat`, `/history` | `X-API-Key` required | open |
| `/config` | `X-API-Key` required | **401** (route-level check, no auth context exists) |
| `/evaluation`, `/evaluation/*` | `X-API-Key` required | **401** (route-level check) |
| `/documents` | `X-API-Key` required | **open** |
| `/experiments`, `/experiments/*` | `X-API-Key` required | **open** |

Because `/documents` and `/experiments` are reachable without a key when auth is disabled, production deployments should configure API keys. Startup validation outside development requires them.

Role-based admin authorization and an admin UI are **not implemented yet**. Roles in `API_KEYS_JSON` currently only feed rate-limit bypass selection (`APP__API__RATE_LIMIT_BYPASS_ROLES`); they do not gate any route. Do not treat a role value as an authorization boundary.

CORS is the outermost middleware layer, so browser preflight requests and auth-error responses (including 401s) carry the `Access-Control-Allow-*` headers the frontend needs.

## API Keys and the Public Frontend

An API key is a server-side secret. It must **never** be shipped in browser code, committed to the frontend bundle, or exposed through a `VITE_*` variable — `VITE_*` values are compiled into the JavaScript every visitor downloads, so publishing one there publishes the key.

Current reality: the SvelteKit frontend sends no `X-API-Key` header. A deployment that enables `APP__API__API_KEYS` / `APP__API__API_KEYS_JSON` therefore needs a server-side proxy or guard that injects the header for public traffic; the backend cannot be called directly by the browser in that posture without a 401.

If a trusted reverse proxy injects a key, it must also enforce per-IP or edge rate limiting. Requests carrying a valid key enter the authenticated branch of the limiter (keyed by the authenticated principal), **not** the anonymous per-IP `/chat` bucket, so without proxy-side limiting all proxied visitors effectively share one authenticated bucket and the anonymous protection no longer applies.

Any proxy configured with `APP__API__TRUST_PROXY_HEADERS=true` must:

- overwrite or strip client-supplied `X-Forwarded-For` / `X-Real-IP` so callers cannot choose their rate-limit key;
- block direct access to the backend (firewall, private network, or origin-only binding), so requests cannot reach the app without passing through the proxy.

Role-based admin authorization and an admin UI are **not implemented yet** (see [Authentication Reality](#authentication-reality)); key-protected deployments still have no per-user identity, admin roles, or moderation surface.

## Privileged Access

If you want a “master” key for demos, configure it via `APP__API__API_KEYS_JSON` with `APP__API__RATE_LIMIT_BYPASS_KEY_IDS` or `APP__API__RATE_LIMIT_BYPASS_ROLES`. See [`configuration.md`](./configuration.md) for the full setting reference.

This bypass only affects the app-level rate limiter. It does not create a user account system, does not grant any route-level authorization beyond successful key authentication, and it should still be treated like a highly sensitive secret.

## Cloudflare Free Setup

1. Add your domain to Cloudflare and move DNS to Cloudflare.
2. Proxy the backend hostname through Cloudflare.
3. Enable HTTPS and use strict origin TLS if possible.
4. Add a rate-limit rule for `POST /chat`.
5. Optionally enable Bot Fight Mode, but test it against your frontend and API traffic.
6. Keep the backend limiter enabled as a second layer.
7. Enable `APP__API__TRUST_PROXY_HEADERS=true` only once traffic really arrives through Cloudflare, Cloudflare overwrites client-supplied `X-Forwarded-For`/`X-Real-IP`, and the backend is unreachable except through Cloudflare.

## Session Model

- The backend issues an anonymous `HttpOnly` chat session cookie.
- Chat history is scoped to that cookie, not a caller-supplied `session_id`.
- `DELETE /history` clears the current session and rotates to a fresh one.
- Anonymous `/chat` rate limiting is keyed by the client IP, not by a cookie. No `anon_browser_id` cookie is issued. See [anonymous-sessions.md](./anonymous-sessions.md) for the shared-IP tradeoff.

## Remaining Limits

This setup is fine for a small public app, but it is still intentionally minimal:

- chat history is file-backed, not multi-instance shared
- rate limiting is still origin-local inside the app
- anonymous chat limiting collapses users behind one NAT/shared IP into a single bucket
- there is no end-user identity, no role-based admin authorization, no admin UI, no moderation workflow, and no abuse appeals flow
- frontend and backend should ideally be served on the same site or through a reverse proxy if you want cookie-backed sessions without cross-site surprises

If traffic grows or you move to multiple backend instances, plan to revisit shared storage and edge-layer controls.
