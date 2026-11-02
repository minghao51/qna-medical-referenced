# Deployment and authenticated-release pickup brief

**Status:** staged, **not executed**. P01–P10 are offline-complete. This brief is the next-thread entry point for the approved Cloudflare demo and G-AUTH evidence.

**Approved shape:** Cloudflare Access + Cloudflare Tunnel + server-side API-key injection + origin with no published ports. No anonymous public rollout, no browser key, no direct backend exposure.

## 1. Owner inputs still needed

Do not guess these. Record the answer in the continuation handoff/report before deployment:

| Input | Why |
|---|---|
| Cloudflare-managed domain/zone | Access cannot protect a quick `trycloudflare.com` hostname |
| Host choice: VPS with inbound SSH, or home/NAT | Decides GitHub SSH deploy vs pull-based/self-hosted runner |
| Live chat/provider spend allowed? | Demo Q&A calls a real provider; set budget/rate limits or disable chat |
| Access allowlist | Named emails/domain or one-time-PIN invites; no `Bypass` policy |
| GHCR package visibility | Private packages require a host `docker login` with `read:packages` |

## 1a. Offline preflight completed (2026-11-02)

The staged artifacts pass a static preflight:

- `docker-compose.demo.yml` defines `backend`, `frontend`, `ingress` and `cloudflared`; none publishes a host port.
- `deploy/Caddyfile` injects `X-API-Key` server-side and disables SSE buffering.
- `Dockerfile` contains exactly six fixture COPY lines.
- `.github/workflows/deploy-demo.yml` is manual and its deploy job is gated by `vars.DEPLOY_ENABLED == 'true'`.
- No `.env.demo`, image tag, DNS record, Tunnel or Access application exists yet.
- Docker is not installed in the current environment, so no image was built and the remote deploy cannot be verified here.

This is still **not** G-AUTH release evidence.

**Machine transfer:** see [transfer-and-run.md](../deployment/transfer-and-run.md) for the worktree/data transfer, local image build and on-host verification sequence.

## 2. Pre-deploy gates

1. Owner approval to deploy/publish images/spend provider quota.
2. Commit/push the working tree (all current work is uncommitted).
3. Re-run the offline gates:
   ```bash
   bash scripts/check_backend.sh fast
   bash scripts/check_backend.sh lint
   npm --prefix frontend run check
   npm --prefix frontend run build
   npm --prefix frontend test
   ```
4. Build both images at least once in CI (`Deploy Demo` workflow) and confirm the backend image contains `/app/tests/fixtures/golden_queries*.json` and `/app/tests/fixtures/golden_conversations.json`, and behaves with the fixtures absent.

## 3. Host setup

Follow `docs/deployment/cloudflare-demo.md`:

1. Create `/opt/fieldnote-demo`, restore `data/` with `docs/data-sync-runbook.md`, keep `.env`, chat history, logs and old run artifacts out.
2. Generate `.env.demo`:
   ```bash
   uv run python scripts/prepare_demo_env.py --origin https://lab.example.com
   chmod 600 .env.demo
   ```
3. Fill `CLOUDFLARE_TUNNEL_TOKEN` and provider credentials; rotate the operator key if needed.
4. Log the host into GHCR once if packages are private.
5. Create the Tunnel public hostname → `http://ingress:8080`.
6. Create the Access application on that hostname: Allow policy, short session, approved login methods, no Bypass.
7. Add WAF rate limiting for `/api/chat` (and optionally `/api/*`).
8. Configure GitHub variables/secrets and set `DEPLOY_ENABLED=true` only when ready.

## 4. Deploy

Use the `Deploy Demo` workflow (manual or `demo-deploy-*` tag), or on the host:

```bash
cd /opt/fieldnote-demo
IMAGE_TAG=<sha> docker compose --env-file .env.demo -f docker-compose.demo.yml pull
IMAGE_TAG=<sha> docker compose --env-file .env.demo -f docker-compose.demo.yml up -d --remove-orphans
```

If the host has no inbound SSH, use the pull-based timer or self-hosted-runner alternative in the runbook.

## 5. G-AUTH evidence to record (release blocker)

Capture exact commands/results in a dated report:

- Access login is required; unauthenticated browser request is redirected to login.
- Backend origin publishes no ports (`ss -ltnp`); only the tunnel is reachable.
- No-key `GET /evaluation/latest`, `/experiments` and `/research-data/datasets` return **401**.
- `/documents` is reachable only through the Access boundary; its route-level middleware-only status is documented.
- `/api/health` works after login; an archived report and research page load.
- Frontend bundle contains no API key/operator secret (`grep` built assets).
- Tunnel shows one healthy connector; no extra bypass hostname.
- Chat rate limit works at the edge; provider budget/profile is as approved.
- Image contains the six fixtures; missing fixtures show honest missing states.

Only after these are recorded should the handoff/readiness report change from “shape approved” to “authenticated release verified”.

## 6. Rollback / shutdown

- App: `docker compose down`; keep data volume.
- Rollback image: set `IMAGE_TAG=<previous sha>` and `up -d`.
- Disable access: delete Access application/tunnel or revoke the tunnel token.
- Rotate operator key: generate a new hash/plaintext, update `.env.demo`, restart `ingress` and `backend`.
- No data/index migration is required for rollback.

## 7. Do not do in the next thread

- No anonymous public mode or removal of Access to “make the demo easy”.
- No API key in `VITE_*`, browser storage, screenshots, logs or docs.
- No provider-key spend without owner approval; no corpus/index rebuild or data mutation for the demo.
- No claim that the app is production-grade: origin JWT verification, role policy (F-02), `/documents` route auth and a full accessibility audit remain open.

## 8. Where the next agent starts

1. Read `assets/svg/continuation-handoff.md` and the P10 readiness report.
2. Ask the owner for the five inputs in §1.
3. Confirm the tree is committed/pushed and the offline gates still pass.
4. Execute §2–§5, then create the dated G-AUTH evidence report and update the handoff.
