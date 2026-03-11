---
title: Local Development
sidebar_position: 2
---

Use this page when you want a realistic local environment for the control plane, docs site, and MCP API. The goal is not just to compile the repository, but to make local MCP testing predictable.

## What runs locally

The repository is split into:

- `apps/web` for the control-plane UI
- `apps/docs` for the public Docusaurus site
- `apps/mcp-api` for the FastAPI + FastMCP backend

Typical local ports:

- control plane: `http://localhost:3000`
- public docs: `http://localhost:3001`
- MCP API health: `http://localhost:8010/healthz`

## 1. Install dependencies

```bash
pnpm install
cd apps/mcp-api
uv sync
cd ../..
```

If you plan to edit docs while keeping the control plane open, install root dependencies first. The docs site is part of the same workspace and should be validated from the repository root.

## 2. Configure environment

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

Important local docs note:

- the web app no longer renders docs content directly
- `/docs` in the web app redirects to `NEXT_PUBLIC_DOCS_URL`
- if you want local docs, keep that value aligned with the docs dev server

Recommended local docs setting:

```bash
NEXT_PUBLIC_DOCS_URL=http://localhost:3001
```

If port `3001` is already occupied on your machine, change both the docs dev server port and `NEXT_PUBLIC_DOCS_URL` together. The redirect is only as correct as the value baked into the web build.

## 3. Start the local surfaces

Run the control plane:

```bash
pnpm dev:web
```

Run the public docs site:

```bash
pnpm dev:docs
```

Run the API:

```bash
cd apps/mcp-api
uv run uvicorn viberecall_mcp.app:create_app --factory --reload --port 8010
```

Optional graph and queue dependencies:

```bash
docker compose -f ops/docker-compose.runtime.yml up -d
```

Use the compose stack when you need local queue, Redis, or graph-backed workflows instead of a minimal API boot.

## Local URLs

- Control plane: `http://localhost:3000`
- Public docs: `http://localhost:3001`
- MCP API health: `http://localhost:8010/healthz`

The control plane uses `NEXT_PUBLIC_DOCS_URL` to point its docs links at the Docusaurus app. Keep that value aligned with the docs host in each environment.

The local MCP endpoint shape is still project-scoped:

```text
http://localhost:8010/p/<project_id>/mcp
```

Whether that endpoint is usable depends on your token and local backend configuration, not just the path existing.

## Recommended local validation loop

1. start the docs app
2. start the web app
3. start the API
4. confirm `http://localhost:3000/docs` redirects to the live docs origin
5. confirm `http://localhost:8010/healthz` is healthy
6. run the [Quickstart](/getting-started/quickstart) flow with your chosen client

That validates the docs surface, web redirect, and MCP runtime in one pass.

## Local development modes

### Minimal UI-and-docs mode

Use this when you are changing content, layout, or control-plane links:

- run `pnpm dev:web`
- run `pnpm dev:docs`
- do not boot the full runtime unless your change needs MCP verification

### Full local runtime mode

Use this when you are debugging MCP behavior:

- run the web app
- run the docs app
- run the API
- boot the compose stack when graph- or queue-backed behavior matters

### Hosted-core plus local-shell mode

This is often the best fit for agent work:

- keep the hosted MCP server as the real memory system
- use local apps only for docs, UI, or backend debugging
- use the [Local Workspace Bridge](/agent-guides/local-workspace-bridge) pattern when uncommitted local code must influence indexing

That avoids the common mistake of assuming a hosted memory service can see your local dirty worktree.

## Common local-development mistakes

- Starting the web app but forgetting the docs app, then assuming `/docs` is broken.
- Pointing the client at the local API path without valid local tokens or backend services.
- Expecting a hosted MCP server to read the uncommitted local repository directly.
- Forgetting to boot Redis or graph dependencies before testing graph-backed flows.

## Local development for AI coding agents

If your real use case is an AI coding agent:

- keep the hosted MCP endpoint as the default memory service when possible
- use local development mainly for control-plane work, docs work, or backend debugging
- do not assume a hosted MCP server can see your uncommitted repository state
- for dirty local worktree indexing, use the [Local Workspace Bridge](/agent-guides/local-workspace-bridge) pattern

## Before you conclude that local MCP is broken

Check these in order:

1. `apps/docs` is actually running on the host baked into `NEXT_PUBLIC_DOCS_URL`
2. the API health endpoint is healthy
3. the token belongs to the `project_id` in your local endpoint
4. Redis and graph services are running if your chosen tools need them
5. the client has reconnected after any backend restart

That sequence catches most local false alarms.

## Related reading

- [Quickstart](/getting-started/quickstart)
- [Connection](/mcp-reference/connection)
- [Common Failures](/troubleshooting/common-failures)
