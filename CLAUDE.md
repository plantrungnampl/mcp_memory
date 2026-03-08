# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

pnpm monorepo (`pnpm-workspace.yaml`) with two apps:
- `apps/mcp-api` — Python FastAPI + FastMCP backend (MCP tools + control-plane HTTP API)
- `apps/web` — Next.js 16 App Router control-plane UI

Spec/architecture notes live in `viberecall_spec_md/`. Operational files (Docker Compose, etc.) live in `ops/`. `CONTINUITY.md` is a canonical implementation ledger — consult it for key decisions before making architectural changes.

## Commands

### Frontend (`apps/web`)
```bash
pnpm install              # install workspace dependencies (run from repo root)
pnpm dev:web              # run web app on http://localhost:3000
pnpm build:web            # production build
pnpm lint:web             # run ESLint
pnpm --dir apps/web typecheck  # TypeScript check (required by CI)
```

### Backend (`apps/mcp-api`)
```bash
cd apps/mcp-api
uv sync --locked                                                # install deps
uv run uvicorn viberecall_mcp.app:create_app --factory --reload --port 8010  # run API
uv run pytest -q                                                # run all tests
uv run pytest tests/test_mcp_tools.py -q                        # run a single test file
```

### Run with local FalkorDB + Redis
```bash
docker compose -f ops/docker-compose.runtime.yml up -d
cd apps/mcp-api
MEMORY_BACKEND=falkordb KV_BACKEND=redis QUEUE_BACKEND=eager \
  uv run uvicorn viberecall_mcp.app:create_app --factory --reload --port 8010
```

### Run Celery worker
```bash
cd apps/mcp-api
MEMORY_BACKEND=falkordb KV_BACKEND=redis QUEUE_BACKEND=celery \
  uv run celery -A viberecall_mcp.workers.celery_app worker -l info
```

### Optional integration tests (require live services)
```bash
cd apps/mcp-api
RUN_RUNTIME_INTEGRATION=1 uv run pytest tests/test_runtime_integration.py -q
RUN_RUNTIME_E2E_CELERY=1 MEMORY_BACKEND=falkordb KV_BACKEND=redis QUEUE_BACKEND=celery \
  uv run pytest tests/test_runtime_e2e_celery.py -q
```

## Architecture

### Backend (`apps/mcp-api/src/viberecall_mcp/`)

**Entry point:** `app.py` — `create_app()` factory wires FastAPI, mounts FastMCP Streamable HTTP at `/`, and adds `/healthz` and `/metrics`.

**MCP layer:**
- `mcp_app.py` — builds the FastMCP app; middleware handles PAT auth, tenant enforcement, rate limiting, idempotency, and audit logging per request.
- `tool_handlers.py` — implements the five MCP tool handlers: `handle_save`, `handle_search`, `handle_get_facts`, `handle_update_fact`, `handle_timeline`.
- `tool_registry.py` — schema/definition registry for all five MCP tools.

**Runtime backend selection** (`runtime.py`) — selectors are read from env vars at startup; singletons are created once and returned by getter functions:
- `MEMORY_BACKEND=local|falkordb|graphiti` → `LocalMemoryCore` / `FalkorDBMemoryCore` / `GraphitiMemoryCore`
- `KV_BACKEND=local|redis` → `LocalIdempotencyStore` + `LocalRateLimiter` / Redis equivalents
- `QUEUE_BACKEND=eager|celery` → `EagerTaskQueue` (runs inline) / `CeleryTaskQueue`

Default (`local/local/eager`) requires no external services. Production uses `falkordb/redis/celery`.

**Memory core interface** (`memory_core/interface.py`) — all adapters implement this interface. FalkorDB uses per-project graph names `vr-<project_id>` (safe chars). Graphiti wraps `graphiti-core` behind the same interface.

**Control-plane** (`control_plane.py`) — project CRUD, token lifecycle (mint/rotate/revoke), usage rollups, exports, billing overview, API logs, Stripe webhook, maintenance actions (retention/purge/migrate-inline-to-object). All routes require `X-Control-Plane-Secret` and `X-Control-Plane-User-Id` headers from the web BFF.

**Workers** (`workers/tasks.py`) — Celery tasks: `ingest_episode_task`, `update_fact_task`, `export_project_task`, `retention_project_task`, `purge_project_task`, `migrate_inline_to_object_task`.

**Object storage** (`object_storage.py`) — raw episodes are stored inline in Postgres when ≤ `RAW_EPISODE_INLINE_MAX_BYTES` (default 64 KB); larger content is stored in local dir or R2 (`OBJECT_STORAGE_MODE=local|r2`) and Postgres keeps a `content_ref`.

**Config** (`config.py`) — `get_settings()` is `@lru_cache`. Settings reads `/.env` from repo root first, then falls back to `apps/mcp-api/.env`.

**DB migrations** — plain SQL files in `apps/mcp-api/migrations/`, numbered `001`–`010`. Apply manually or via Supabase MCP.

**Repositories** (`repositories/`) — one module per entity: `projects`, `tokens`, `episodes`, `usage_events`, `exports`, `audit_logs`, `maintenance`, `webhooks`.

**Ports:** MCP API on `:8010`; web on `:3000`; any Graphiti instance runs separately on `:8000`.

### Frontend (`apps/web/src/`)

**App Router structure:**
- `app/` — routes: `/` (landing), `/login`, `/docs`, `/projects`, `/projects/[projectId]/*` (tokens, usage, billing, api-logs)
- `app/projects/actions.ts` — all Next.js Server Actions; they call `lib/api/control-plane.ts` which is the sole BFF client.
- `components/` — `ui/` (shadcn/Radix primitives), `landing/`, `projects/`
- `lib/api/control-plane.ts` — typed fetch wrappers for every control-plane endpoint; injects `X-Control-Plane-Secret` + `X-Control-Plane-User-Id` from `lib/server-env.ts`
- `lib/supabase/` — Supabase SSR helpers; auth checks use `auth.getUser()` (not `getSession()`)

**State:** Zustand for client store; TanStack Query for cache; `sonner` for toast notifications.

**UI conventions:** Dark-themed (`#0a0810`/`#130d1d` backgrounds, `#7a2dbe` purple accent). 2-space indentation, PascalCase components, kebab-case filenames.

## Key Conventions

- **Business logic lives in** `src/lib` (web) and `src/viberecall_mcp` (backend) — not in UI glue or routes.
- **Token revocation:** `revoked_at > now` means the token is still in its grace window and is treated as valid.
- **Idempotency:** mutations accept an `Idempotency-Key` header; the backend deduplicates by `provider + event_id` for webhooks.
- **Graph naming:** per-project FalkorDB graph names use safe identifiers with `-` separators (e.g. `vr-<id>`).
- **Purge safety:** purge operations require the caller to type the exact `project_id` to confirm.
- **MCP endpoint URL:** built from `PUBLIC_MCP_BASE_URL`, not inferred from the request host.

## Environment Setup

Copy `.env.example` to `.env` at the repo root and fill in required values. The backend reads from the root `.env` automatically. The web app has its own `apps/web/.env` for `NEXT_PUBLIC_*` and Supabase keys.

Required for control-plane web mutations:
- `CONTROL_PLANE_API_BASE_URL`
- `CONTROL_PLANE_INTERNAL_SECRET`
- `PUBLIC_MCP_BASE_URL`
- `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` + `SUPABASE_SERVICE_ROLE_KEY`
