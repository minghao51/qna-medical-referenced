# Local Docker preview — restart handoff

**Snapshot:** 2026-11-02, branch `design/evidence-led-redesign`.
**Purpose:** preview the actual demo images behind the Caddy key-injection boundary before any Cloudflare deployment or PR merge.

## Current machine state

- Docker **29.9.2** and Compose **v5.6.1** are installed.
- `howt` is in the `docker` group in `/etc/group`, but the shell that prepared this handoff was started before the group change. A fresh login/session should have socket access.
- `.env.demo.local` has been generated in the repository root. It is **gitignored**, mode `600`, and contains:
  - `DEMO_ORIGIN=http://localhost:8080`
  - `REGISTRY=local`
  - `IMAGE_TAG=local`
  - a generated operator key/hash and session signing secret
  - a dummy `CLOUDFLARE_TUNNEL_TOKEN=local-preview-only`
  - blank provider credentials
- `/tmp/fieldnote-preview-compose.yml` contains the localhost-only ingress port override. `/tmp` may be cleared on reboot; recreate it from §2.
- The old Vite dev server and a review backend may still be running on `127.0.0.1:5173` and `127.0.0.1:8000`. They are not the Docker stack and can be stopped.
- Nothing was built or started with Docker yet. No commit, push or PR exists.

## 1. Check Docker access in the new session

```bash
cd /home/howt/work/qna-medical-referenced
id -nG | grep -q docker && echo "docker group active"
docker info --format '{{.ServerVersion}}'
```

If access is still denied after the restart, either log out/in again or temporarily run:

```bash
sudo chgrp howt /var/run/docker.sock
```

Restore `sudo chgrp docker /var/run/docker.sock` (or restart Docker) when finished.

## 2. Recreate the localhost-only compose override if needed

```bash
cat > /tmp/fieldnote-preview-compose.yml <<'YAML'
services:
  ingress:
    ports:
      - "127.0.0.1:8080:8080"
YAML
```

This publishes only Caddy on localhost. The backend and frontend remain internal. Do not use this override on the Cloudflare host.

## 3. Stop the old dev processes

```bash
kill $(cat /tmp/qna-vite-review.pid) $(cat /tmp/qna-backend-review.pid) 2>/dev/null || true
ss -ltnp | grep -E ':(5173|8000|8080)\b' || true
```

## 4. Build the actual demo images

```bash
cd /home/howt/work/qna-medical-referenced
docker compose --env-file .env.demo.local -f docker-compose.demo.yml build
```

The build may take several minutes: it installs Python dependencies, NLTK data and the Bun frontend build. The frontend is compiled with `VITE_API_URL=http://localhost:8080/api`.

## 5. Start only backend, frontend and ingress

No `cloudflared` container yet:

```bash
docker compose --env-file .env.demo.local -f docker-compose.demo.yml \
  -f /tmp/fieldnote-preview-compose.yml up -d backend frontend ingress
docker compose --env-file .env.demo.local -f docker-compose.demo.yml \
  -f /tmp/fieldnote-preview-compose.yml ps
```

## 6. Open the preview

Use **http://localhost:8080** — not `http://127.0.0.1:8080`. The allowed CORS origin is `http://localhost:8080`, and the frontend bundle uses `http://localhost:8080/api`.

Check:

```bash
curl -sS -o /dev/null -w 'frontend=%{http_code}\n' http://localhost:8080/
curl -sS -o /dev/null -w 'backend-through-caddy=%{http_code}\n' http://localhost:8080/api/health
ss -ltnp | grep ':8080 '
```

Expected: frontend `200`, backend `200`, only `127.0.0.1:8080` published. Caddy injects the operator key; the browser never has it.

Read-only research/evaluation/evidence pages should load from `data/`. Q&A generation will fail unless provider credentials are filled into `.env.demo.local`; do not add them unless provider spend is approved.

## 7. Stop the preview

```bash
docker compose --env-file .env.demo.local -f docker-compose.demo.yml \
  -f /tmp/fieldnote-preview-compose.yml down
```

Keep `data/`; do not run `down -v` unless you intend to remove Caddy volumes.

## 8. After the visual check: PR/merge

The tree has **88 uncommitted entries**; `.env.demo.local` is ignored and must not enter the commit. Only after the local preview is accepted:

```bash
git status --short
git add -A
git diff --cached --stat
git commit -m "design: evidence-led Fieldnote redesign and demo hardening"
git push -u origin design/evidence-led-redesign
```

Then open a PR into `main`:

```bash
gh pr create --base main --head design/evidence-led-redesign \
  --title "Evidence-led Fieldnote redesign" \
  --body "P01–P10 plus P09.1/P10.1 hardening: research workspace, Ask workbench, evidence/catalog pages, run safety, accessibility, deploy artifacts. Offline verified: backend fast/offline/lint, frontend check/build, Playwright 108 passed/9 skipped, axe 0 violations. No deployment or authenticated-release claim."
```

If `gh` is unavailable/unauthenticated, use the GitHub web UI. Do not merge until CI passes and the owner has completed the local visual check. Do not commit `.env.demo.local`, `data/`, `test-results/` or `/tmp` files.

## 9. Still blocked after the preview

The Cloudflare demo and G-AUTH evidence still require:

1. Cloudflare-managed domain/zone.
2. Host choice: VPS with SSH or home/NAT.
3. Live chat/provider spend permission.
4. Access allowlist.
5. GHCR package visibility (or use the local-build path).

Use `docs/deployment/transfer-and-run.md` for the target-machine transfer and `docs/deployment/cloudflare-demo.md` for Tunnel/Access/WAF. The local preview is **not** G-AUTH evidence.
