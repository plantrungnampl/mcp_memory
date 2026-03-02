# viberecall-mcp

FastAPI and FastMCP backend bootstrap for VibeRecall.

## Graphiti source policy

- Canonical dependency source uses vendored Graphiti source at `apps/mcp-api/vendor/graphiti` via `tool.uv.sources` local editable path.
- Vendor currently tracks upstream Graphiti tag `v0.28.1` / commit `76053036e3db086f57444a29c53d427b0d635a80`.
- Refresh vendor from upstream:

```bash
cd apps/mcp-api
mkdir -p vendor
git clone --depth 1 --branch v0.28.1 https://github.com/getzep/graphiti.git vendor/graphiti
uv lock
```

## Run

```bash
uv sync
uv run uvicorn viberecall_mcp.app:create_app --factory --reload --port 8010
```

## Runtime notes

- Backend config reads the repository root `/.env` by default; if it does not exist, it falls back to `apps/mcp-api/.env`.
- Runtime backend selection is explicit:
  - `MEMORY_BACKEND=local|neo4j|graphiti`
  - `KV_BACKEND=local|redis`
  - `QUEUE_BACKEND=eager|celery`
- Graphiti runtime settings:
  - `GRAPHITI_API_KEY` is required to enable Graphiti sync.
  - `GRAPHITI_LLM_MODEL` defaults to `gpt-4.1-mini`.
  - `GRAPHITI_EMBEDDER_MODEL` defaults to `text-embedding-3-small`.
  - `GRAPHITI_TELEMETRY_ENABLED=false` is recommended for local development.
- Raw episode storage rule (spec v0.1):
  - `RAW_EPISODE_INLINE_MAX_BYTES` (default `65536`): save inline in Postgres when below/equal threshold.
  - Larger payloads are persisted to object storage and Postgres keeps `content_ref`.
- Object storage configuration:
  - `OBJECT_STORAGE_MODE=local|r2`
  - `OBJECT_LOCAL_DIR=.runtime-objects` for local mode
  - For `r2`: set `OBJECT_BUCKET`, `OBJECT_ENDPOINT`, `OBJECT_REGION`, `OBJECT_ACCESS_KEY_ID`, `OBJECT_SECRET_ACCESS_KEY`
- Inline migration gate:
  - `INLINE_MIGRATION_DB_SIZE_THRESHOLD_BYTES` controls when `migrate_inline_to_object` auto-run should be allowed unless forced.
- Control-plane HTTP routes require internal headers from the web BFF:
  - `X-Control-Plane-Secret` (must match `CONTROL_PLANE_INTERNAL_SECRET`)
  - `X-Control-Plane-User-Id`
- Stripe webhook endpoint is available at `/api/control-plane/stripe/webhook` and validates `Stripe-Signature` using `STRIPE_WEBHOOK_SECRET`.
- Stripe webhook processing is idempotent by `event.id` via `webhooks` table (migration `004_webhooks.sql`) and supports retry of previously failed events.
- Local lightweight mode uses `local/local/eager`.
- Real local-services mode uses `neo4j/redis/eager`.
- Production mode uses `neo4j/redis/celery`.

## Run with local Neo4j + Redis

```bash
docker compose -f ../../ops/docker-compose.runtime.yml up -d
MEMORY_BACKEND=neo4j KV_BACKEND=redis QUEUE_BACKEND=eager \
uv run uvicorn viberecall_mcp.app:create_app --factory --reload --port 8010
```

## Run worker

```bash
MEMORY_BACKEND=neo4j KV_BACKEND=redis QUEUE_BACKEND=celery \
uv run celery -A viberecall_mcp.workers.celery_app worker -l info
```

## Runtime integration tests (Neo4j + Redis)

```bash
RUN_RUNTIME_INTEGRATION=1 uv run pytest tests/test_runtime_integration.py -q
```

## Runtime E2E test (Neo4j + Redis + Celery worker)

```bash
# terminal 1: local services
docker compose -f ../../ops/docker-compose.runtime.yml up -d

# terminal 2: celery worker
MEMORY_BACKEND=neo4j KV_BACKEND=redis QUEUE_BACKEND=celery \
uv run celery -A viberecall_mcp.workers.celery_app worker -l warning -Q memory --pool=solo --concurrency=1

# terminal 3: run opt-in e2e test
RUN_RUNTIME_E2E_CELERY=1 MEMORY_BACKEND=neo4j KV_BACKEND=redis QUEUE_BACKEND=celery \
uv run pytest tests/test_runtime_e2e_celery.py -q
```

If the test times out, verify Redis/Neo4j availability and that the worker process is connected to the same broker/result backend.

## Trigger inline-content migration

```bash
curl -X POST "http://localhost:8010/api/control-plane/projects/<project_id>/migrate-inline-to-object" \
  -H "Content-Type: application/json" \
  -H "X-Control-Plane-Secret: dev-control-plane-secret" \
  -H "X-Control-Plane-User-Id: user_demo" \
  -d '{"force": true}'
```

## Claim legacy unowned projects

```bash
uv run python scripts/claim_legacy_projects.py --owner-id <user_id> --dry-run
uv run python scripts/claim_legacy_projects.py --owner-id <user_id>
```
