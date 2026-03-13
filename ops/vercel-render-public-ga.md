# Vercel + Render Public GA

This runbook turns the current repository state into a public production candidate using Vercel for `apps/web` and `apps/docs`, plus Render for the MCP API runtime.

## 1. Release gate

Run the repo-level release checks from the root revision you intend to deploy:

```bash
pnpm validate:release
```

Expected result:

- `pnpm validate:docs` passes
- `pnpm validate:web` passes
- `pnpm test:backend` passes

## 2. Vercel web + docs deployment

Create the control-plane Vercel project with these settings:

- Root Directory: `apps/web`
- Framework Preset: `Next.js`
- Production domain: `app.<your-domain>`

Set these production env vars in Vercel:

- `APP_ENV=production`
- `NEXT_PUBLIC_MARKETING_URL=https://www.<your-domain>`
- `NEXT_PUBLIC_APP_URL=https://app.<your-domain>`
- `NEXT_PUBLIC_DOCS_URL=https://docs.<your-domain>`
- `NEXT_PUBLIC_SUPABASE_URL=...`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=...`
- `NEXT_PUBLIC_MCP_BASE_URL=https://api.<your-domain>`
- `CONTROL_PLANE_API_BASE_URL=https://api.<your-domain>`
- `CONTROL_PLANE_INTERNAL_SECRET=...`
- `INDEX_REMOTE_GIT_ENABLED=false`
- `DEPLOYMENT_VERSION=<release-id>`
- `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY=<stable-base64-key>`

Notes:

- `NEXT_PUBLIC_*` values are baked in at build time; set them before the Vercel build starts.
- `CONTROL_PLANE_API_BASE_URL` is the server-side control-plane origin for web requests and `/api/health`; do not leave it on an internal Docker hostname.
- `NEXT_PUBLIC_MARKETING_URL` is the canonical landing/SEO origin; keep `NEXT_PUBLIC_APP_URL` reserved for auth and dashboard flows on `app.<your-domain>`.
- Keep `DEPLOYMENT_VERSION` fixed per release so multi-instance rollouts preserve version skew protection.
- Keep `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY` stable across all instances of the same deployment.
- Put a reverse proxy or platform edge in front of the Node runtime if you self-host outside Vercel.

Create the public docs Vercel project with these settings:

- Root Directory: `apps/docs`
- Framework Preset: `Other`
- Install Command: `pnpm install --frozen-lockfile`
- Build Command: `pnpm build`
- Output Directory: `build`
- Production domain: `docs.<your-domain>`

Set these production env vars in the docs Vercel project:

- `DOCUSAURUS_URL=https://docs.<your-domain>`

## 3. Render API + worker deployment

Import `render.yaml`, then set the unresolved secrets in Render before promoting:

- `PUBLIC_MCP_BASE_URL=https://api.<your-domain>`
- `PUBLIC_WEB_URL=https://app.<your-domain>`
- `ALLOWED_ORIGINS=https://app.<your-domain>`
- `DATABASE_URL=...`
- `TOKEN_PEPPER=...`
- `CONTROL_PLANE_INTERNAL_SECRET=...`
- `REDIS_URL=...`
- `CELERY_BROKER_URL=...`
- `CELERY_RESULT_BACKEND=...`
- `EXPORT_SIGNING_SECRET=...`
- `SUPABASE_SERVICE_ROLE_KEY=...`
- `STRIPE_WEBHOOK_SECRET=...`

Additional Render provisioning:

- Create one Render Key Value instance in the same region as the API and worker.
- Point `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` at that Key Value instance.
- Bind `api.<your-domain>` to the `viberecall-api` web service.

The blueprint provisions:

- `viberecall-api` as the public MCP/control-plane API
- `viberecall-worker` as the Celery background worker
- `viberecall-falkordb` as a private persistent service

## 4. Seed QA fixtures

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

## 5. Authenticated browser QA

Sign in as the dedicated test user and verify these routes on the deployed web app:

- `/projects`
- `/projects/[projectId]/tokens`
- `/projects/[projectId]/api-logs`
- `/projects/[projectId]/usage`
- `/projects/[projectId]/graphs/playground`

Public GA only proceeds if all five routes load without control-plane assertion failures, stale-session failures, or graph degradation in the happy path.

## 6. Cutover rule

Promote the release only when all four conditions are true:

1. `pnpm validate:release` passed on the release revision
2. deployed MCP smoke passed against `https://api.<your-domain>`
3. authenticated browser QA passed on `https://app.<your-domain>`
4. public docs site loads successfully on `https://docs.<your-domain>` and `https://app.<your-domain>/docs` redirects there
