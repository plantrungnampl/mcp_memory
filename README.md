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
   - `PUBLIC_MCP_BASE_URL`
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

## Optional runtime integration suites

- Neo4j + Redis roundtrip:
  `cd apps/mcp-api && RUN_RUNTIME_INTEGRATION=1 uv run pytest tests/test_runtime_integration.py -q`
- Neo4j + Redis + Celery worker end-to-end:
  `cd apps/mcp-api && RUN_RUNTIME_E2E_CELERY=1 MEMORY_BACKEND=neo4j KV_BACKEND=redis QUEUE_BACKEND=celery uv run pytest tests/test_runtime_e2e_celery.py -q`
