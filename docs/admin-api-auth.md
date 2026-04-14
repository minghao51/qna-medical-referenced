# Optional API Key Auth

The current public app can run with backend API-key auth disabled. API keys are still useful for admin, internal, or scripted access.

## When To Use API Keys

- protecting non-public backend access
- internal dashboards or automation
- admin-only evaluation endpoints
- staging and pre-production environments

## Configuration

Use either:

- `API_KEYS=key1,key2,key3`
- `API_KEYS_JSON=[{"id":"frontend","key":"secret","owner":"web","role":"client","status":"active"}]`

See [`configuration.md`](./configuration.md) for the full setting reference.

## Request Format

Send the key in the `X-API-Key` header.

Example:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{"message":"What is a normal cholesterol level?"}'
```

## Recommended Usage

- Keep public chat anonymous if that is your product choice.
- If you later add internal tooling, protect those callers with API keys first.
- If you want a trusted “master” demo/admin key, use `API_KEYS_JSON` plus `RATE_LIMIT_BYPASS_KEY_IDS` or `RATE_LIMIT_BYPASS_ROLES` rather than disabling rate limiting globally.
- If you add real end-user accounts later, do not treat API keys as a substitute for user auth.
