# VibeRecall Memory

VibeRecall is a monorepo for a project-scoped MCP memory platform and its control-plane UI. It is designed for coding-agent workflows where each project gets its own MCP endpoint, bearer-token access, persistent memory operations, code indexing, and operator-facing visibility into usage, logs, and graph state.

This repository currently contains:

- a public MCP/control-plane API built with FastAPI + FastMCP
- a Next.js App Router control-plane web app
- local and production-candidate runtime surfaces for Postgres, FalkorDB, Redis, and Celery

## Overview

VibeRecall gives coding agents a project-bound memory layer instead of a single global context blob. The backend exposes `viberecall_*` tools for saving events, searching facts, retrieving timelines, deleting episodes, indexing code, and building context packs. The web app handles project onboarding, token lifecycle, API log visibility, usage analytics, and graph exploration.

Core capabilities:

- project-scoped MCP endpoints using bearer tokens
- persistent memory flows: save, search, facts, timeline, update, delete
- code indexing and context-pack retrieval for agent workflows
- control-plane workflows for project setup, token issuance, usage, and logs
- graph playground for visualizing memory entities and relationships

Current public MCP tool surface:

- `viberecall_save`
- `viberecall_search`
- `viberecall_get_facts`
- `viberecall_update_fact`
- `viberecall_timeline`
- `viberecall_get_status`
- `viberecall_delete_episode`
- `viberecall_index_repo`
- `viberecall_index_status`
- `viberecall_search_entities`
- `viberecall_get_context_pack`

## Architecture At A Glance

The repo is organized around two runtime applications:

- `apps/web`
  Next.js 16 App Router control plane for sign-in, project onboarding, token management, usage analytics, API logs, and graph exploration.
- `apps/mcp-api`
  FastAPI + FastMCP backend that serves the MCP transport, control-plane endpoints, memory operations, code indexing, and background task orchestration.

Operational runtime dependencies:

- `Postgres` for canonical relational state
- `FalkorDB` for graph-backed memory operations
- `Redis` for KV, queue broker, and task result backend
- `Celery` for background execution in production-shaped runtime

The intended production-candidate topology is:

- `apps/web` on Vercel
- API + worker + FalkorDB on Render
- Redis-compatible key-value provisioned alongside the API/worker

## Repository Layout

| Path | Purpose |
| --- | --- |
| `apps/web` | Next.js control-plane UI |
| `apps/mcp-api` | FastAPI + FastMCP backend |
| `ops/` | Deployment and operational runbooks |
| `.env.example` | Local development environment contract |
| `.env.production.example` | Production-shaped environment contract |
| `render.yaml` | Render blueprint for API, worker, and FalkorDB |
| `.github/workflows/ci.yml` | Baseline CI for web and backend validation |

## Prerequisites

- Node.js `20.9+`
- `pnpm` `10+`
- Python `3.12+`
- `uv`
- Docker, if you want the full local graph/queue runtime

## Quick Start

### 1. Install dependencies

```bash
pnpm install
cd apps/mcp-api
uv sync
cd ../..
```

### 2. Create local environment config

Copy the root example and fill the required values:

```bash
cp .env.example .env
```

At minimum, local development needs:

- `DATABASE_URL`
- `CONTROL_PLANE_INTERNAL_SECRET`
- `TOKEN_PEPPER`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

### 3. Start the web app

```bash
pnpm dev:web
```

### 4. Start the API

```bash
cd apps/mcp-api
uv run uvicorn viberecall_mcp.app:create_app --factory --reload --port 8010
```

### 5. Open the onboarding surface

Once both services are running:

- control plane: `http://localhost:3000`
- onboarding docs: `http://localhost:3000/docs`
- MCP API health: `http://localhost:8010/healthz`

### 6. Start graph/queue dependencies when needed

If you want graph-backed memory or runtime integration suites locally:

```bash
docker compose -f ops/docker-compose.runtime.yml up -d
```

## Environment Configuration

Use the root env files as the canonical source of truth:

- local development: [`/.env.example`](./.env.example)
- production-shaped runtime: [`/.env.production.example`](./.env.production.example)

Key env groups:

### Web and public URLs

- `NEXT_PUBLIC_APP_URL`
- `NEXT_PUBLIC_MCP_BASE_URL`
- `PUBLIC_MCP_BASE_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`

### Internal control-plane auth

- `CONTROL_PLANE_API_BASE_URL`
- `CONTROL_PLANE_INTERNAL_SECRET`
- `PUBLIC_WEB_URL`
- `ALLOWED_ORIGINS`

### Runtime backends

- `DATABASE_URL`
- `TOKEN_PEPPER`
- `MEMORY_BACKEND`
- `KV_BACKEND`
- `QUEUE_BACKEND`
- `FALKORDB_HOST`
- `FALKORDB_PORT`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

### Production-only release values

- `DEPLOYMENT_VERSION`
- `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY`
- `EXPORT_SIGNING_SECRET`
- `STRIPE_WEBHOOK_SECRET`

## MCP Quickstart

To connect an IDE or coding agent to VibeRecall:

1. Sign in to the control plane.
2. Create a project.
3. Mint an MCP token and copy the plaintext value immediately.
4. Configure the MCP client to call:

   ```text
   http://localhost:8010/p/<project_id>/mcp
   ```

   For deployed environments, replace the base URL with your public API domain.

5. Send the token as a bearer token:

   ```text
   Authorization: Bearer vr_mcp_sk_...
   ```

6. Verify the connection by calling:
   - `viberecall_get_status`
   - `viberecall_save`
   - `viberecall_search`

Important transport note:

- If your MCP client starts returning `404 Session not found` after a backend reload or reconnect, reinitialize the MCP session. The transport is stateful and stale `mcp-session-id` values are rejected.

## Validation

Canonical repo-level checks:

```bash
pnpm validate:web
pnpm test:backend
pnpm validate:release
```

What they do:

- `pnpm validate:web`
  runs `typecheck`, `lint`, and `build` for `apps/web`
- `pnpm test:backend`
  runs the backend test suite from `apps/mcp-api/tests`
- `pnpm validate:release`
  runs both web and backend validation gates

Optional integration suites:

```bash
cd apps/mcp-api
RUN_RUNTIME_INTEGRATION=1 uv run pytest tests/test_runtime_integration.py -q
RUN_RUNTIME_E2E_CELERY=1 MEMORY_BACKEND=falkordb KV_BACKEND=redis QUEUE_BACKEND=celery uv run pytest tests/test_runtime_e2e_celery.py -q
```

## Deployment

### Local production-shaped stack

The repo includes a production-shaped local stack:

```bash
cp .env.production.example .env.production
docker compose -f ops/docker-compose.production.yml --env-file .env.production up --build
```

This stack assumes:

- web on port `3000`
- API on port `8010`
- Celery worker enabled
- Redis + FalkorDB as runtime dependencies
- external Postgres through `DATABASE_URL`

### Intended hosted topology

- `apps/web` on Vercel
- API + worker + FalkorDB on Render
- Redis-compatible key-value provisioned separately

Deployed MCP smoke:

```bash
pnpm smoke:mcp:deployed -- --base-url https://api.example.com --project-id <project_id> --token <plaintext_mcp_token>
```

For the complete rollout sequence, see:

- [`ops/vercel-render-public-ga.md`](./ops/vercel-render-public-ga.md)
- [`render.yaml`](./render.yaml)
- [`apps/mcp-api/README.md`](./apps/mcp-api/README.md)

## Documentation Map

Start here depending on what you need:

- backend runtime and MCP specifics:
  [`apps/mcp-api/README.md`](./apps/mcp-api/README.md)
- public-GA rollout checklist:
  [`ops/vercel-render-public-ga.md`](./ops/vercel-render-public-ga.md)
- local production-shaped compose surface:
  [`ops/docker-compose.production.yml`](./ops/docker-compose.production.yml)
- local runtime dependencies:
  [`ops/docker-compose.runtime.yml`](./ops/docker-compose.runtime.yml)
- environment contracts:
  [`/.env.example`](./.env.example) and [`/.env.production.example`](./.env.production.example)

## Troubleshooting

### `404 Session not found` from the MCP endpoint

Cause:

- the client is sending a stale or expired `mcp-session-id`

Fix:

- reconnect or restart the MCP client so it performs `initialize` again

### Graph-backed tools fail locally

If `viberecall_save`, `viberecall_search`, `viberecall_get_facts`, or `viberecall_timeline` fail with FalkorDB connection errors:

- start local runtime dependencies with `docker compose -f ops/docker-compose.runtime.yml up -d`
- verify `http://localhost:8010/healthz`

### Control-plane requests fail between web and API

If project pages cannot load control-plane data:

- make sure `CONTROL_PLANE_INTERNAL_SECRET` matches across web and API
- make sure `PUBLIC_WEB_URL` and `ALLOWED_ORIGINS` are configured consistently
- restart both services after changing auth-related env vars
