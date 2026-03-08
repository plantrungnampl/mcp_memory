# VibeRecall Memory

Monorepo bootstrap for the VibeRecall MCP backend and control-plane web app.
## Apps

- `apps/mcp-api`: Python FastAPI + FastMCP backend
- `apps/web`: Next.js App Router control-plane shell
- `.github/workflows/ci.yml`: CI for backend and web checks

## Requirements

- Node.js 20.9+
- pnpm 10+
- Python 3.12+
- `uv`

## Quick start

1. Copy `.env.example` to `.env` and fill the required values.
   Use an async SQLAlchemy DSN for `DATABASE_URL`, for example
   `postgresql+asyncpg://postgres:postgres@localhost:5432/viberecall`.
   Control-plane web mutations require these variables:
   - `CONTROL_PLANE_API_BASE_URL`
   - `CONTROL_PLANE_INTERNAL_SECRET`
   - `NEXT_PUBLIC_MCP_BASE_URL`
   Backend/browser origin alignment also requires:
   - `PUBLIC_WEB_URL`
   - `ALLOWED_ORIGINS`
2. Install frontend dependencies:

   ```bash
   pnpm install
   ```

3. Install backend dependencies:

   ```bash
   cd apps/mcp-api
   uv sync
   ```

4. Start the web app:

   ```bash
   pnpm dev:web
   ```

5. Start the MCP API:

   ```bash
   cd apps/mcp-api
   uv run uvicorn viberecall_mcp.app:create_app --factory --reload --port 8010
   ```

6. Open onboarding docs:

   ```text
   http://localhost:3000/docs
   ```

## Release validation

- Web gate:

  ```bash
  pnpm validate:web
  ```

- Backend gate:

  ```bash
  pnpm test:backend
  ```

- Combined release gate:

  ```bash
  pnpm validate:release
  ```

The backend command intentionally points pytest at `apps/mcp-api/tests` so local runs from the repo root do not accidentally collect vendored Graphiti tests.

## Production container surface

- Copy `.env.production.example` to `.env.production` and fill all non-local values.
- Build and run the production-shaped stack:

  ```bash
  docker compose -f ops/docker-compose.production.yml --env-file .env.production up --build
  ```

- This production surface assumes:
  - web on port `3000`
  - MCP/control-plane API on port `8010`
  - Celery worker enabled
  - Redis + FalkorDB as runtime dependencies
  - external Postgres via `DATABASE_URL`
- For public/self-hosted production, place a reverse proxy in front of the Next.js server and keep `DEPLOYMENT_VERSION` plus `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY` stable for each release image.
- The production env contract now explicitly includes:
  - `NEXT_PUBLIC_MCP_BASE_URL` for browser-side MCP links
  - `PUBLIC_MCP_BASE_URL` for backend-generated MCP URLs
  - `PUBLIC_WEB_URL` for API-side canonical web links
  - `ALLOWED_ORIGINS` for browser-origin allowlisting

## Vercel + Render rollout

- `apps/web` is intended to deploy on Vercel with `Root Directory = apps/web`.
- `render.yaml` defines the Render blueprint for:
  - `viberecall-api`
  - `viberecall-worker`
  - `viberecall-falkordb`
- Provision Render Key Value separately, then wire its internal URL into:
  - `REDIS_URL`
  - `CELERY_BROKER_URL`
  - `CELERY_RESULT_BACKEND`
- The public rollout checklist lives in `ops/vercel-render-public-ga.md`.
- Deployed MCP smoke can be run with:

  ```bash
  pnpm smoke:mcp:deployed -- --base-url https://api.example.com --project-id <project_id> --token <plaintext_mcp_token>
  ```

## Optional runtime integration suites

- FalkorDB + Redis roundtrip:
  `cd apps/mcp-api && RUN_RUNTIME_INTEGRATION=1 uv run pytest tests/test_runtime_integration.py -q`
- FalkorDB + Redis + Celery worker end-to-end:
  `cd apps/mcp-api && RUN_RUNTIME_E2E_CELERY=1 MEMORY_BACKEND=falkordb KV_BACKEND=redis QUEUE_BACKEND=celery uv run pytest tests/test_runtime_e2e_celery.py -q`
