# Transfer and run Fieldnote on another machine

This is the handoff for moving the current **uncommitted** working tree to a machine that will run the private demo. It covers source transfer, data transfer, local image build, startup, smoke checks and the G-AUTH evidence to record.

**Do not use a fresh `git clone` as the source of truth.** The redesign, deploy artifacts and reports are uncommitted; a clone of the branch will not contain them.

## 1. What must move

| Item | Transfer? | Notes |
|---|---|---|
| Working tree (all modified/untracked files) | Yes | Includes `deploy/`, `docs/`, `assets/svg/`, `frontend/src/routes/*`, `scripts/`, tests and reports. |
| `.git/` | Recommended | Preserves branch/history so the target can review and later commit. It does not contain the uncommitted changes by itself. |
| `data/` | Yes, separately | ~104 MB now. Use the data sync runbook or direct transfer. |
| `.env.demo` | **No** | Generate on the target or transfer out-of-band. Never put it in the archive. |
| `.env` | **No** | Source development secrets; never transfer. |
| `frontend/node_modules`, `.venv`, `.svelte-kit`, `build`, caches | No | Rebuilt/installed on the target. |
| `data/chat_history.json`, `data/rate_limits.db` | No | Runtime state; omit for a clean demo. |
| `test-results/`, screenshots | No | Audit artifacts. |

## 2. Create the source bundle on the current machine

Stop the dev servers first. From the repository root:

```bash
tar -czf fieldnote-worktree-20261102.tar.gz \
  --exclude='./.venv' \
  --exclude='./frontend/node_modules' \
  --exclude='./frontend/.svelte-kit' \
  --exclude='./frontend/build' \
  --exclude='./test-results' \
  --exclude='./.pytest_cache' \
  --exclude='./.ruff_cache' \
  --exclude='./data' \
  --exclude='./.env' \
  --exclude='./.env.demo' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  .
sha256sum fieldnote-worktree-20261102.tar.gz > fieldnote-worktree-20261102.tar.gz.sha256
```

The archive intentionally includes `.git/`, `assets/svg/`, all untracked deploy/docs files and the complete working tree.

Transfer the archive:

```bash
scp fieldnote-worktree-20261102.tar.gz* user@target:/tmp/
```

Alternative, if the target is reachable by SSH:

```bash
rsync -a --info=progress2 \
  --exclude='.venv' --exclude='frontend/node_modules' \
  --exclude='frontend/.svelte-kit' --exclude='frontend/build' \
  --exclude='test-results' --exclude='.pytest_cache' --exclude='.ruff_cache' \
  --exclude='data' --exclude='.env' --exclude='.env.demo' \
  ./ user@target:/opt/fieldnote-demo-src/
```

On the target:

```bash
sudo install -d -o "$USER" -g "$USER" /opt/fieldnote-demo-src
cd /opt/fieldnote-demo-src
sha256sum -c /tmp/fieldnote-worktree-20261102.tar.gz.sha256
tar -xzf /tmp/fieldnote-worktree-20261102.tar.gz
git status --short | wc -l   # current tree has ~88 entries; do not expect a clean tree
```

## 3. Transfer the frozen data

Restore only the data the demo reads. A clean transfer is:

```bash
rsync -a --info=progress2 \
  --exclude='chat_history.json' \
  --exclude='rate_limits.db' \
  --exclude='evals/cache' \
  data/ user@target:/opt/fieldnote-demo-src/data/
```

Required contents:

- `data/chroma-d11/` — frozen D11 index, 2,473 chunks.
- `data/evals/review/` — D11 review manifest/cases.
- `data/raw/LabQAR/reference_ranges.csv` — 471 reference rows.
- `experiments/outputs/medical_semantic_chunking_exp_report.json` — included in the repository/worktree, not `data/`.

Keep `data/` at the project root that contains `docker-compose.demo.yml`; the compose file mounts `./data:/app/data`.

Verify:

```bash
du -sh data/chroma-d11 data/evals/review data/raw/LabQAR/reference_ranges.csv
```

## 4. Prepare the target machine

Minimum:

- Linux x86_64, Docker Engine 24+ with Compose v2.
- 2 GB RAM, 5 GB free disk beyond the data.
- Outbound HTTPS (Docker pulls, Cloudflare Tunnel, provider API).
- No inbound app ports are required.
- Optional: Python 3.12 + `uv` only if generating `.env.demo` locally.
- Optional: Node/Bun only if running the frontend outside Docker.

Check:

```bash
docker --version
docker compose version
df -h /opt
```

## 5. Create `.env.demo` on the target

Preferred: generate it on the target from this worktree.

```bash
cd /opt/fieldnote-demo-src
uv run python scripts/prepare_demo_env.py --origin https://lab.example.com
chmod 600 .env.demo
```

If `uv`/Python is unavailable, generate it on the source machine and transfer it out-of-band (password manager or a direct `scp` with immediate `chmod 600`). Never place it in the tar archive.

Edit `.env.demo` and set:

- `DEMO_ORIGIN` — the final Access hostname, no trailing slash.
- `REGISTRY=local` and `IMAGE_TAG=local` if building locally; use `ghcr.io/<owner>` and a commit SHA for GHCR.
- `CLOUDFLARE_TUNNEL_TOKEN`.
- `APP__LLM__PYDANTIC_AI_API_KEY` for OpenCode Go generation/judging and `APP__LLM__DASHSCOPE_API_KEY` for the frozen Qwen embeddings.
- Keep `APP__API__API_KEYS_JSON` matching `OPERATOR_API_KEY`.

For a local build without GHCR, the image names are local tags such as `local/qna-medical-referenced-backend:local`; nothing is pushed.

## 6. Build and start

### Option A — build locally (works without GHCR or GitHub Actions)

```bash
cd /opt/fieldnote-demo-src
docker compose --env-file .env.demo -f docker-compose.demo.yml build
docker compose --env-file .env.demo -f docker-compose.demo.yml up -d
docker compose --env-file .env.demo -f docker-compose.demo.yml ps
```

The first build downloads Python/Bun base images and dependencies. The frontend is compiled with `VITE_API_URL=${DEMO_ORIGIN}/api`; if the origin changes, rebuild the frontend image.

### Option B — use GHCR images and the workflow

Commit/push the working tree, set the GitHub variables/secrets described in `cloudflare-demo.md`, and let the `Deploy Demo` workflow build and deploy. Deploy by immutable commit SHA, not an uncommitted tree.

Do **not** run `docker compose pull` for a local-only build; pull only when the images exist in GHCR.

## 7. Smoke-test before exposing the hostname

No ports are published, so test inside the Compose network:

```bash
docker compose --env-file .env.demo -f docker-compose.demo.yml exec backend \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').status)"

docker compose --env-file .env.demo -f docker-compose.demo.yml exec ingress \
  wget -qO- http://127.0.0.1:8080/api/health
```

Check all four services are healthy/running and only `cloudflared` has an outbound tunnel:

```bash
docker compose --env-file .env.demo -f docker-compose.demo.yml ps
ss -ltnp | grep -E ':(8000|5173|8080)\b' || echo "no app ports published"
docker compose --env-file .env.demo -f docker-compose.demo.yml logs --tail=50 cloudflared
```

Then follow `cloudflare-demo.md` for the Tunnel, Access application, allowlist and WAF rate limit.

## 8. G-AUTH evidence to record

Create a dated report and paste exact command output. Do not mark G-AUTH verified until all are checked:

- [ ] Unauthenticated browser request to the hostname redirects to Cloudflare Access login.
- [ ] `ss -ltnp` shows no host ports for backend/frontend/ingress.
- [ ] No-key requests from inside the backend return 401 for `/evaluation/latest`, `/experiments`, `/research-data/datasets` and `/documents`.
- [ ] `/documents` is reachable only through the Access boundary; record the middleware-only route caveat.
- [ ] `/api/health` reports healthy after login.
- [ ] Archived report and `/research/evaluations` load after login.
- [ ] Built frontend bundle contains no `OPERATOR_API_KEY` or provider key.
- [ ] Tunnel logs show one healthy connector; no second public hostname.
- [ ] WAF rate limit for `/api/chat` exists; backend limiters remain enabled.
- [ ] Image contains the six fixture files; missing fixtures show honest missing states.
- [ ] Provider budget/chat permission matches the owner decision.

No-key probe example:

```bash
docker compose --env-file .env.demo -f docker-compose.demo.yml exec backend \
  python -c "import urllib.request, urllib.error
for p in ['/evaluation/latest','/experiments','/research-data/datasets','/documents']:
    try:
        urllib.request.urlopen('http://127.0.0.1:8000'+p)
        print(p, 200)
    except urllib.error.HTTPError as e:
        print(p, e.code)"
```

## 9. Updating after transfer

Because the tree is uncommitted, do not assume `git pull` updates it. Re-run the source transfer from the current machine, then rebuild:

```bash
cd /opt/fieldnote-demo-src
# re-sync the worktree, excluding secrets/data
docker compose --env-file .env.demo -f docker-compose.demo.yml build
docker compose --env-file .env.demo -f docker-compose.demo.yml up -d --remove-orphans
```

If using GHCR, commit/push the intended tree first and deploy by immutable SHA.

## 10. Shutdown and rollback

```bash
cd /opt/fieldnote-demo-src
docker compose --env-file .env.demo -f docker-compose.demo.yml down
```

- Keep `data/` across restarts.
- Roll back local images by rebuilding the prior worktree or setting `IMAGE_TAG` to a prior GHCR SHA.
- Delete the Access application/tunnel to remove public reachability.
- Rotate `OPERATOR_API_KEY` and `CLOUDFLARE_TUNNEL_TOKEN` if the host or archive was exposed.
- No index/data migration is required for rollback.

## 11. Current limits to carry forward

- Access JWT is not verified at the origin; the boundary is tunnel-only ingress plus no published ports.
- Role values do not gate routes yet (audit F-02); all active keys are operator-equivalent.
- The operator key is shared by all visitors at the edge; WAF rate limiting is mandatory.
- Provider cancellation is cooperative after disconnect; the ASGI iterator and focused backend tests are covered, but immediate provider billing stop cannot be guaranteed.
- No physical NVDA/JAWS/VoiceOver session was run; axe and Chromium accessibility-tree/keyboard evidence is in `docs/testing/accessibility.md`.
- No deployment, image publish or authenticated-release evidence has happened yet.
