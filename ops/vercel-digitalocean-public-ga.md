# Vercel + DigitalOcean Public GA

This runbook turns the current repository state into a public production candidate using Vercel for `apps/web` and `apps/docs`, plus a single DigitalOcean Droplet for the MCP API runtime.

## 1. Release gate

Run the repo-level release checks from the root revision you intend to deploy:

```bash
pnpm validate:release
```

Expected result:

- `pnpm validate:docs` passes
- `pnpm validate:web` passes
- `pnpm test:backend` passes

## 2. Provision the DigitalOcean runtime host

Create one Ubuntu Droplet and attach one persistent DigitalOcean Volume.

- Mount the volume on the Droplet at `/srv/viberecall/data`
- Create these subdirectories before first launch:
  - `/srv/viberecall/data/falkordb`
  - `/srv/viberecall/data/redis`
  - `/srv/viberecall/data/objects`
  - `/srv/viberecall/data/exports`
- Install:
  - Docker Engine
  - Docker Compose plugin
  - Caddy
- Configure the firewall to allow only:
  - `22/tcp`
  - `80/tcp`
  - `443/tcp`

Do not expose Redis or FalkorDB directly to the public internet.

## 3. Vercel web + docs deployment

Create the control-plane Vercel project with these settings:

- Root Directory: `apps/web`
- Framework Preset: `Next.js`
- Production domain: `app.<your-domain>`

Set these production env vars in Vercel:

- `NEXT_PUBLIC_APP_URL=https://app.<your-domain>`
- `NEXT_PUBLIC_DOCS_URL=https://docs.<your-domain>`
- `NEXT_PUBLIC_SUPABASE_URL=...`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=...`
- `NEXT_PUBLIC_MCP_BASE_URL=https://api.<your-domain>`
- `PUBLIC_MCP_BASE_URL=https://api.<your-domain>`
- `CONTROL_PLANE_API_BASE_URL=https://api.<your-domain>`
- `CONTROL_PLANE_INTERNAL_SECRET=...`
- `DEPLOYMENT_VERSION=<release-id>`
- `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY=<stable-base64-key>`

Notes:

- `NEXT_PUBLIC_*` values are baked in at build time; set them before the Vercel build starts.
- Keep `DEPLOYMENT_VERSION` fixed per release so multi-instance rollouts preserve version-skew protection.
- Keep `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY` stable across all web instances for the same app.

Create the public docs Vercel project with these settings:

- Root Directory: `apps/docs`
- Framework Preset: `Other`
- Install Command: `pnpm install --frozen-lockfile`
- Build Command: `pnpm build`
- Output Directory: `build`
- Production domain: `docs.<your-domain>`

Set these production env vars in the docs Vercel project:

- `DOCUSAURUS_URL=https://docs.<your-domain>`

## 4. DigitalOcean API + worker + graph deployment

Copy the production env template at the repo root:

```bash
cp .env.production.example .env.production
```

Set or confirm these values in `.env.production` on the Droplet:

- `PUBLIC_MCP_BASE_URL=https://api.<your-domain>`
- `PUBLIC_WEB_URL=https://app.<your-domain>`
- `ALLOWED_ORIGINS=https://app.<your-domain>`
- `DATABASE_URL=...`
- `TOKEN_PEPPER=...`
- `CONTROL_PLANE_INTERNAL_SECRET=...`
- `EXPORT_SIGNING_SECRET=...`
- `SUPABASE_SERVICE_ROLE_KEY=...`
- `STRIPE_WEBHOOK_SECRET=...`
- `MEMORY_BACKEND=falkordb`
- `KV_BACKEND=redis`
- `QUEUE_BACKEND=celery`
- `FALKORDB_HOST=falkordb`
- `FALKORDB_PORT=6379`
- `REDIS_URL=redis://redis:6379/0`
- `CELERY_BROKER_URL=redis://redis:6379/0`
- `CELERY_RESULT_BACKEND=redis://redis:6379/1`

Important:

- `CONTROL_PLANE_INTERNAL_SECRET` must match exactly between Vercel and the Droplet.
- The DigitalOcean compose file overrides `OBJECT_LOCAL_DIR` and `EXPORT_LOCAL_DIR` to volume-backed paths automatically.
- Postgres remains external in this topology.

Launch the runtime from the repository root on the Droplet:

```bash
docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production up -d --build
```

Expected services:

- `api` bound only on `127.0.0.1:8010`
- `worker` consuming Celery queue `memory`
- `redis` with append-only persistence enabled
- `falkordb` with persistent graph data

## 5. Caddy reverse proxy

Point `api.<your-domain>` at the Droplet, then install the provided Caddy config:

```bash
sudo cp ops/caddy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Before reloading Caddy, replace `api.example.com` in the file with your real API domain.

## 6. Seed QA fixtures

Before browser QA, sign in with a dedicated test account and ensure that account owns at least one project with one active token.

Use the deployed MCP token to create recent usage/log/timeline data:

```bash
pnpm smoke:mcp:deployed -- \
  --base-url https://api.<your-domain> \
  --project-id <project_id> \
  --token <plaintext_mcp_token>
```

This smoke command validates:

- `initialize`
- `tools/list`
- `viberecall_get_status`
- `viberecall_save`
- `viberecall_search`
- `viberecall_get_facts`
- `viberecall_update_fact`
- `viberecall_timeline`
- `viberecall_delete_episode`

## 7. Authenticated browser QA

Sign in as the dedicated test user and verify these routes on the deployed web app:

- `/projects`
- `/projects/[projectId]/tokens`
- `/projects/[projectId]/api-logs`
- `/projects/[projectId]/usage`
- `/projects/[projectId]/graphs/playground`

Public GA only proceeds if all five routes load without control-plane assertion failures, stale-session failures, or graph degradation in the happy path.

## 8. Cutover rule

Promote the release only when all four conditions are true:

1. `pnpm validate:release` passed on the release revision
2. deployed MCP smoke passed against `https://api.<your-domain>`
3. authenticated browser QA passed on `https://app.<your-domain>`
4. public docs site loads successfully on `https://docs.<your-domain>` and `https://app.<your-domain>/docs` redirects there
