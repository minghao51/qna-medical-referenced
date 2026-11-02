# Private Cloudflare Access demo deployment

**Status:** deploy artifacts only. Offline preflight passed; no deployment was performed, no image was published, and no authenticated-release evidence exists yet.

For moving the current uncommitted worktree and frozen data to the target host, start with [transfer-and-run.md](transfer-and-run.md).

This is the approved G-AUTH shape: **Cloudflare Access + Tunnel + server-side key injection + an origin with no published ports**. It produces a login-gated public hostname for a private-lab showcase. It is not an anonymous public rollout.

## Topology and trust boundaries

```text
browser → Cloudflare Access (login) → Cloudflare edge
        → cloudflared tunnel → Caddy ingress
             ├── /api/* → backend:8000      + X-API-Key (server-side)
             └── /*      → frontend:5173
```

- The host publishes **no ports**. `backend`, `frontend`, `ingress` and `cloudflared` are reachable only on the Docker network.
- Caddy is the only component with the plaintext operator key. The browser bundle never contains it.
- Access is enforced at the edge. Origin-side Access JWT verification is **not** implemented (see residual risks).
- Frontend and API share one origin (`https://lab.example.com/api`), so the chat session cookie stays same-site.

## Prerequisites

- A domain zone managed by Cloudflare, with Cloudflare Zero Trust enabled. The free Zero Trust plan covers up to 50 users; Access needs a hostname in a Cloudflare zone (quick `trycloudflare.com` tunnels cannot be Access-protected).
- A Docker host with outbound HTTPS: a VPS or an always-on machine. Approximate resources: 2 GB RAM, 1 GB disk for the app + data.
- The runtime data volume (`data/chroma-d11`, `data/evals/review`, `data/raw/LabQAR`, …). Restore it with the [data sync runbook](../data-sync-runbook.md); do not rebuild the index for a demo.
- One read-only GHCR login on the host if the packages remain private.

## Environment file naming

Do not reuse the repository's development `.env` / `.env.example`. The demo uses:

- `.env.demo.example` — committed template, placeholders only
- `.env.demo` — host-only real values, `chmod 600`, gitignored

A future staging/production pair can follow the same pattern (`.env.staging`, `.env.production`). The deploy commands always pass `--env-file .env.demo` explicitly; Docker Compose does not need the file to be named `.env`.

## 1. Prepare the host directory

The host does **not** need a repository checkout. It needs `.env.demo` and `data/`; the deploy workflow copies the compose file and Caddyfile from the deployed commit.

```bash
sudo install -d -o "$USER" -g "$USER" /opt/fieldnote-demo
cd /opt/fieldnote-demo
mkdir -p deploy data/chroma data/evals data/evals_comprehensive_ablation data/processed data/raw
```

Restore the data directories from R2/host copy. Keep `data/chat_history.json`, `data/rate_limits.db` and old logs out of a fresh demo restore unless you intend to carry them over.

If the GHCR packages are private, log the host in once with a token that has `read:packages`:

```bash
printf '%s' "$GHCR_READ_TOKEN" | docker login ghcr.io -u <github-user> --password-stdin
```

## 2. Generate `.env.demo`

Run from a repository checkout (the script imports the app's bcrypt helper):

```bash
uv run python scripts/prepare_demo_env.py --origin https://lab.example.com
```

This writes `.env.demo` (mode 600) from the template and generates the session secret, the plaintext operator key and its matching bcrypt `API_KEYS_JSON` record with role `operator`. Then fill `CLOUDFLARE_TUNNEL_TOKEN` and the provider credentials. The script never prints the generated secrets.

Manual generation, if preferred:

```bash
openssl rand -hex 32   # APP__API__SESSION_SIGNING_SECRET
openssl rand -hex 32   # OPERATOR_API_KEY
uv run python -c 'from src.app.security import generate_api_key_record; import json; print(json.dumps([generate_api_key_record("ingress", "PASTE_OPERATOR_KEY", owner="gateway", role="operator")]))'
```

Use the same plaintext in `OPERATOR_API_KEY` and as the hashed record in `APP__API__API_KEYS_JSON`. Set `DEMO_ORIGIN` without a trailing slash, for example `https://lab.example.com`.

Keep `.env.demo` at `chmod 600`; it contains the provider key, session secret, tunnel token and operator key.

## 3. Create the Cloudflare Tunnel

1. Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared.
2. Name it, for example, `fieldnote-demo`, and copy the connector token into `CLOUDFLARE_TUNNEL_TOKEN`.
3. Add a public hostname:
   - Subdomain/domain: `lab.example.com`
   - Service: `http://ingress:8080`
   - No path, no TLS inside the Docker network.
4. Do not add a second public hostname that bypasses Access.

The `cloudflared` container opens outbound connections only; no inbound firewall rule is needed.

## 4. Configure Cloudflare Access and edge limiting

1. Zero Trust → Access → Applications → Add an application → Self-hosted.
2. Application domain: `lab.example.com`; session duration: 8 hours or less.
3. Policy: **Allow** only named emails, an allowed email domain, or a small Access group. Add one-time PIN and/or Google/GitHub as login methods.
4. Do not create a `Bypass` policy for the hostname.
5. Security → WAF → Rate limiting rules (recommended):
   - `http.request.uri.path eq "/api/chat"`: about 10 requests/minute per IP, block for 60 seconds.
   - Optional broader `/api/*` rule, and optional country restriction.

Edge limiting is not optional in this shape: every visitor shares the one injected key, so the backend sees a single authenticated principal instead of per-visitor anonymous buckets.

## 5. Configure GitHub

Repository **variables**:

| Variable | Value |
|---|---|
| `DEMO_ORIGIN` | `https://lab.example.com` |
| `DEPLOY_ENABLED` | unset/false until the host is ready; then `true` |

Environment **`demo`** (Settings → Environments): add required reviewers if you want a manual approval before every deploy.

Repository/environment **secrets**:

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | hostname or IP reachable from GitHub Actions |
| `DEPLOY_USER` | SSH user |
| `DEPLOY_PATH` | `/opt/fieldnote-demo` |
| `DEPLOY_SSH_KEY` | private key for that user |
| `DEPLOY_KNOWN_HOSTS` | `ssh-keyscan -H <host>` output |

Trigger the workflow from Actions → **Deploy Demo** → Run workflow, or push a `demo-deploy-*` tag. It:

1. builds and pushes tag-pinned backend/frontend images to GHCR;
2. copies `docker-compose.demo.yml` and `deploy/Caddyfile` to the host;
3. runs `docker compose pull` and `up -d` with `IMAGE_TAG=<commit sha>`.

Roll back by re-running the workflow from an older commit, or on the host:

```bash
cd /opt/fieldnote-demo
IMAGE_TAG=<previous-sha> docker compose --env-file .env.demo -f docker-compose.demo.yml up -d
```

### If the host has no inbound SSH

A home server behind NAT cannot accept the GitHub Actions SSH step. Set `DEPLOY_ENABLED=false` and use one of:

- a root-owned systemd timer that runs `docker compose pull && up -d` every few minutes (pull-based deploy), or
- a self-hosted GitHub runner on that machine, and change the deploy job to `runs-on: [self-hosted, demo]`.

The tunnel itself is unaffected: `cloudflared` connects outbound.

## 6. Verify

```bash
cd /opt/fieldnote-demo
docker compose --env-file .env.demo -f docker-compose.demo.yml ps
docker compose --env-file .env.demo -f docker-compose.demo.yml exec backend \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').status)"
ss -ltnp | grep -E ':(8000|5173|8080)\b' || echo "no public app ports"
```

Then:

1. Open `https://lab.example.com` in a private browser window; Access must ask for login.
2. After login, the UI loads and `/api/health` reports healthy.
3. `/api/evaluation/latest` returns archived data through the injected key.
4. `/documents` is reachable only after Access login; it remains middleware-only inside the app.
5. Confirm the built frontend contains no operator key or `VITE_*` secret.
6. Confirm Cloudflare Tunnel logs show one healthy connector and no bypass hostname.

## 7. Rotation and shutdown

- **Operator key:** generate a new key/hash, update `OPERATOR_API_KEY` and `APP__API__API_KEYS_JSON`, then restart `ingress` and `backend`.
- **Tunnel token:** refresh it in Zero Trust, update `.env.demo`, restart `cloudflared`.
- **Shutdown:** `docker compose down`, then delete the Access application and tunnel. No data/index migration is involved.

## 8. Residual risks and open gates

- **Access JWT is not verified at origin.** The boundary is “no published ports + tunnel-only ingress”. Origin JWT verification would need a new dependency/approved change; document it before calling this production-grade.
- **No role policy:** role values do not gate routes yet (audit F-02). Every active key is operator-equivalent; use one gateway key and rotate it.
- **Shared rate-limit bucket:** edge WAF rules are required; keep backend limiters enabled and do not configure bypass roles/IDs for the demo.
- **Startup metadata writes:** inherited audit F-03 behaviour may add collection metadata on boot; there is no index rebuild. Back up the data volume before enabling the demo.
- **SSE through the edge:** long chat streams may hit Cloudflare timeouts; Caddy disables buffering and the client SSE decoder is implemented, but live edge behavior is not release-verified.
- **UI scope:** the Fieldnote workspace, Ask workbench, research pages and accessibility hardening are implemented offline; see the continuation handoff and P09.1/P10.1 report. The demo still must be verified through Access before release.
- **No anonymous public mode.** Removing Access or publishing the app ports invalidates this G-AUTH shape.
- This runbook is the proposed delivery; authenticated-release verification evidence still has to be recorded under G-AUTH before any release claim.
