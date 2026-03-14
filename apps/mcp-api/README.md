# viberecall-mcp

FastAPI and FastMCP backend bootstrap for VibeRecall.

## MCP tools (public)

- `viberecall_save_episode`
- `viberecall_save`
- `viberecall_search_memory`
- `viberecall_search`
- `viberecall_get_fact`
- `viberecall_get_facts`
- `viberecall_update_fact`
- `viberecall_pin_memory`
- `viberecall_timeline`
- `viberecall_get_status`
- `viberecall_delete_episode`
- `viberecall_get_operation`
- `viberecall_index_repo`
- `viberecall_get_index_status`
- `viberecall_index_status`
- `viberecall_search_entities`
- `viberecall_get_neighbors`
- `viberecall_find_paths`
- `viberecall_explain_fact`
- `viberecall_resolve_reference`
- `viberecall_merge_entities`
- `viberecall_split_entity`
- `viberecall_get_context_pack`
- `viberecall_working_memory_get`
- `viberecall_working_memory_patch`

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

- MCP runtime currently treats `plan` as non-blocking metadata:
  - `free`, `pro`, and `team` share the same tool catalog.
  - `tools/list` and `tools/call` still enforce token scope filtering.
  - Token validity, expiry, revocation, project binding, and rate limiting remain enforced.
- Control-plane plan/billing metadata still exists outside MCP runtime and may continue to show `free|pro|team`.
- Backend config reads the repository root `/.env` by default; if it does not exist, it falls back to `apps/mcp-api/.env`.
- Process-level environment variables override `.env`. If you previously exported `FALKORDB_HOST`, `FALKORDB_PORT`, `MEMORY_BACKEND`, or queue/KV vars in your shell, the running process may ignore values from `/.env`.
- Runtime backend selection is explicit:
  - `MEMORY_BACKEND=local|falkordb|graphiti`
  - `KV_BACKEND=local|redis`
  - `QUEUE_BACKEND=eager|celery`
- Canonical MCP scope surface now includes:
  - `memory:read`, `memory:write`, `facts:write`, `entities:read`, `graph:read`
  - `index:read`, `index:run`, `resolution:write`, `ops:read`, `delete:write`
  - legacy aliases remain accepted for compatibility on some surfaces
- Graphiti runtime settings:
  - `GRAPHITI_API_KEY` is required to enable Graphiti sync.
  - `GRAPHITI_LLM_MODEL` defaults to `gpt-4.1-mini`.
  - `GRAPHITI_EMBEDDER_MODEL` defaults to `text-embedding-3-small`.
  - `GRAPHITI_MCP_BRIDGE_MODE=legacy|upstream_bridge` (default `legacy`).
  - This app layer expects direct OpenAI-style credentials through `GRAPHITI_API_KEY`; it does not expose a separate Graphiti base URL override.
  - `upstream_bridge` keeps `viberecall_*` public tool contract but uses upstream Graphiti MCP-style bridge internally for search/facts/timeline paths.
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
- Code indexing safety:
  - `INDEX_REPO_ALLOWED_ROOTS` is an optional comma-separated allowlist for `viberecall_index_repo`.
  - When unset or blank, indexing is limited to the monorepo root by default.
  - To index another local repo in development, add its absolute path to `INDEX_REPO_ALLOWED_ROOTS`.
- `viberecall_get_context_pack` is a dual-mode retrieval surface:
  - `context_mode=code_augmented` when a READY code index snapshot exists
  - `context_mode=memory_only` when no READY code index exists but relevant memory still provides usable context
  - `context_mode=empty` only when neither code nor memory yields useful context
  - `status=READY` therefore means "usable context returned", not necessarily "READY code index exists"
  - additive fields now include:
    - `index_status=READY|MISSING`
    - `index_hint` for `viberecall_index_repo`
    - `architecture_overview`
    - `related_modules`
    - `related_files`
  - existing fields such as `architecture_map`, `relevant_symbols`, `citations`, `facts_timeline`, `decision_history`, and `working_memory_patch` remain part of the response
  - code-heavy callers should inspect `context_mode` before assuming architecture or code citations are available
- Control-plane HTTP routes require an internal signed assertion from the web BFF:
  - `X-Control-Plane-Assertion`
  - `X-Request-Id`
  - The assertion is HMAC-signed with `CONTROL_PLANE_INTERNAL_SECRET` and carries the authenticated user identity in a short-lived payload.
  - The backend echoes `X-Request-Id` on responses so web/runtime logs can be correlated without logging the raw assertion.
- Stripe webhook endpoint is available at `/api/control-plane/stripe/webhook` and validates `Stripe-Signature` using `STRIPE_WEBHOOK_SECRET`.
- Stripe webhook processing is idempotent by `event.id` via `webhooks` table (migration `004_webhooks.sql`) and supports retry of previously failed events.
- Local lightweight mode uses `local/local/eager`.
- Real local-services mode uses `falkordb/redis/eager`.
- Production mode uses `falkordb/redis/celery`.

### Troubleshooting stale env in running process

```bash
# Check effective env of current uvicorn process
PID="$(pgrep -f 'uvicorn viberecall_mcp.app:create_app' | head -n 1)"
tr '\0' '\n' < "/proc/${PID}/environ" | rg '^FALKORDB_HOST=|^FALKORDB_PORT=|^MEMORY_BACKEND=|^KV_BACKEND=|^QUEUE_BACKEND='

# Restart backend with root .env loaded explicitly
cd apps/mcp-api
set -a
source ../../.env
set +a
uv run uvicorn viberecall_mcp.app:create_app --factory --reload --port 8010

# Restart the Next.js dev server too after auth contract / secret changes
cd ../web
pnpm dev
```

### Troubleshooting `Missing control-plane assertion`

- Restart both the Next.js dev server and `uvicorn --reload` after changing:
  - `CONTROL_PLANE_INTERNAL_SECRET`
  - internal control-plane auth headers/contracts
- Hard refresh the browser and sign in again if the page still shows a stale workspace/auth error.
- Use the echoed `X-Request-Id` / UI request id to correlate:
  - web server logs for `control_plane_request_*`
  - backend logs for `control_plane_auth_*`

## Run with local FalkorDB + Redis

```bash
docker compose -f ../../ops/docker-compose.runtime.yml up -d
MEMORY_BACKEND=falkordb KV_BACKEND=redis QUEUE_BACKEND=eager \
uv run uvicorn viberecall_mcp.app:create_app --factory --reload --port 8010
```

## Run with current local `.env` defaults (`graphiti + eager + local KV`)

```bash
# terminal 1: required graph dependency
docker compose -f ../../ops/docker-compose.runtime.yml up -d

# terminal 2: backend (loads repository root .env automatically)
uv run uvicorn viberecall_mcp.app:create_app --factory --reload --port 8010

# terminal 3: required post-start checks
curl http://localhost:8010/healthz
```

Expected startup checks before using `viberecall-local`:

- `/healthz` returns `"status": "ok"` and `checks.falkordb.status = "ok"`.
- `viberecall_get_status` returns `"status": "ok"`.
- If `/healthz` is `degraded` with `localhost:6380`, FalkorDB is not available and graph-backed MCP tools like `viberecall_save`, `viberecall_search`, and `viberecall_timeline` will fail fast.
- `GRAPHITI_MCP_BRIDGE_MODE=legacy|upstream_bridge` does not remove the FalkorDB dependency for canonical save/search/facts/timeline paths when `MEMORY_BACKEND=graphiti`.

### Troubleshooting stale MCP sessions

- `POST /p/<project_id>/mcp` returning `404` with `Session not found` means the client sent an unknown or expired `mcp-session-id`.
- The backend is stateful for Streamable HTTP. Requests that omit the session header create a fresh session; requests with a stale session id are rejected.
- Common trigger: the MCP client keeps an old session alive after `uvicorn --reload`, backend restart, or other transport reset.
- Fix on the client side: reconnect or restart the MCP client so it runs `initialize` again and obtains a fresh `mcp-session-id`.
- `GET /p/<project_id>/mcp` returning `406 Not Acceptable` means the client did not advertise the required MCP media types. Streamable HTTP requests must accept both `application/json` and `text/event-stream`.

## Run worker

```bash
MEMORY_BACKEND=graphiti KV_BACKEND=redis QUEUE_BACKEND=celery \
uv run celery -A viberecall_mcp.workers.celery_app worker -l info
```

## Production container surface

- Repository root now includes `.env.production.example` plus `ops/docker-compose.production.yml`.
- Repository root also includes `ops/docker-compose.digitalocean.yml` for the hosted DigitalOcean Droplet runtime.
- Default public-GA runtime shape is:
  - `MEMORY_BACKEND=graphiti`
  - `KV_BACKEND=redis`
  - `QUEUE_BACKEND=celery`
  - `GRAPHITI_API_KEY=<OpenAI API key>`
  - FalkorDB remains required for canonical storage even when Graphiti is enabled.
- Start the full production-shaped stack from the repository root:

```bash
cp .env.production.example .env.production
docker compose -f ops/docker-compose.production.yml --env-file .env.production up --build
```

- Expected services:
  - `web` on `3000`
  - `api` on `8010`
  - `worker` consuming Celery queue `memory`
  - `redis`
  - `falkordb`
- Postgres remains external and must be provided through `DATABASE_URL`.
- For the paired Next.js container, keep `DEPLOYMENT_VERSION` fixed per release and provide a stable `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY` across all web instances.
- For public production, also set:
  - `PUBLIC_WEB_URL`
  - `PUBLIC_MCP_BASE_URL`
  - `ALLOWED_ORIGINS`
  - `NEXT_PUBLIC_MCP_BASE_URL` on the web deployment

### DigitalOcean hosted runtime

For the split deployment topology with web on Vercel and backend runtime on a single DigitalOcean Droplet:

```bash
cp .env.production.example .env.production
docker compose -f ops/docker-compose.digitalocean.yml --env-file .env.production up -d --build
```

- Expected services:
  - `api` bound to `127.0.0.1:8010`
  - `worker` consuming Celery queue `memory`
  - `redis` with append-only persistence
  - `falkordb` with persistent graph data
- Postgres remains external and must be provided through `DATABASE_URL`.
- `CONTROL_PLANE_INTERNAL_SECRET` must match exactly between the Vercel web deployment and the DigitalOcean runtime.
- The DigitalOcean compose file mounts persistent host directories for FalkorDB plus local object/export storage.
- Put a reverse proxy in front of `127.0.0.1:8010`; the repo provides `ops/caddy/Caddyfile` as the default host-level proxy config.
- For the full rollout sequence, use `ops/vercel-digitalocean-public-ga.md`.

## Deployed MCP smoke

After deploying the API, verify the public MCP transport with:

```bash
pnpm smoke:mcp:deployed -- \
  --base-url https://api.example.com \
  --project-id <project_id> \
  --token <plaintext_mcp_token>
```

The wrapper now strips the leading `--` before handing arguments to the Python entrypoint, so the documented `pnpm ... -- ...` form is the supported path.

If you are debugging the script directly, the underlying entrypoint remains:

```bash
uv run --project apps/mcp-api python apps/mcp-api/scripts/smoke_deployed_mcp.py \
  --base-url https://api.example.com \
  --project-id <project_id> \
  --token <plaintext_mcp_token>
```

By default this runs the `core` profile, which validates:

- `viberecall_save_episode`
- `viberecall_search_memory`
- `viberecall_get_fact`
- `viberecall_pin_memory`
- `viberecall_working_memory_get`
- `viberecall_working_memory_patch`
- `viberecall_save`
- `viberecall_search`
- `viberecall_get_facts`
- `viberecall_update_fact`
- `viberecall_timeline`
- `viberecall_delete_episode`

Additional opt-in profiles are available:

- `ops`
  validates `viberecall_get_status` and `viberecall_get_operation`
- `graph`
  validates `viberecall_search_entities`, `viberecall_get_neighbors`, `viberecall_find_paths`, `viberecall_explain_fact`, and `viberecall_resolve_reference`
- `index`
  validates `viberecall_index_repo`, `viberecall_get_index_status`, `viberecall_index_status`, and `viberecall_get_context_pack`
- `resolution`
  validates `viberecall_merge_entities` and `viberecall_split_entity`

Examples:

```bash
# core + ops with one shared token
pnpm smoke:mcp:deployed -- \
  --base-url https://api.example.com \
  --project-id <project_id> \
  --token <shared_token> \
  --profile core \
  --profile ops

# graph with a dedicated token
pnpm smoke:mcp:deployed -- \
  --base-url https://api.example.com \
  --project-id <project_id> \
  --profile graph \
  --graph-token <graph_token>

# index only when remote indexing is enabled and a smoke repo is available
pnpm smoke:mcp:deployed -- \
  --base-url https://api.example.com \
  --project-id <project_id> \
  --profile index \
  --index-token <index_token> \
  --index-repo-url https://github.com/example/smoke-repo.git \
  --index-ref main \
  --index-repo-name smoke-repo

# index a local repo by packaging it as a workspace bundle first
pnpm smoke:mcp:deployed -- \
  --base-url https://api.example.com \
  --project-id <project_id> \
  --profile index \
  --index-token <index_token> \
  --index-local-repo-path /absolute/path/to/local-repo \
  --index-repo-name local-repo

# resolution requires a privileged token with resolution:write
pnpm smoke:mcp:deployed -- \
  --base-url https://api.example.com \
  --project-id <project_id> \
  --profile resolution \
  --resolution-token <resolution_token>
```

Notes:

- The smoke runner uses explicit token-to-profile mapping; if a profile token is not provided it falls back to `--token`.
- `index` is intentionally gated and should only use `--index-repo-url/--index-ref` when `INDEX_REMOTE_GIT_ENABLED=true` on the target runtime.
- `--index-local-repo-path` uses the runtime `/p/{project_id}/index-bundles` upload route plus `repo_source.type=workspace_bundle`, so it does not depend on remote git indexing being enabled.
- `resolution` is intentionally destructive within the smoke project and should use a dedicated test project/token.
- If `index` is accepted but stays `QUEUED`, treat that as a runtime/worker readiness issue, not a client packaging issue.
- If `index` stays `RUNNING` for an unusually long time, inspect worker health and queue delivery before retrying the same request.
- If `index` returns `FAILED`, capture the terminal error payload and backend logs before rerunning smoke.
- Hosted runtimes cannot read a raw local filesystem path directly; use `--index-local-repo-path` only because the smoke runner uploads a workspace bundle first.

## Runtime integration tests (FalkorDB + Redis)

```bash
RUN_RUNTIME_INTEGRATION=1 uv run pytest tests/test_runtime_integration.py -q
```

## Runtime E2E test (FalkorDB + Redis + Celery worker)

```bash
# terminal 1: local services
docker compose -f ../../ops/docker-compose.runtime.yml up -d

# terminal 2: celery worker
MEMORY_BACKEND=falkordb KV_BACKEND=redis QUEUE_BACKEND=celery \
uv run celery -A viberecall_mcp.workers.celery_app worker -l warning -Q memory --pool=solo --concurrency=1

# terminal 3: run opt-in e2e test
RUN_RUNTIME_E2E_CELERY=1 MEMORY_BACKEND=falkordb KV_BACKEND=redis QUEUE_BACKEND=celery \
uv run pytest tests/test_runtime_e2e_celery.py -q

# or from the repo root
pnpm test:backend:runtime
```

This file now contains two runtime E2E paths:

- legacy save/search/update worker flow
- canonical + ops roundtrip covering `save_episode`, `get_fact`, `search_memory`, `pin_memory`, `search_entities`, `resolve_reference`, `working_memory_*`, `get_status`, and `get_operation`

Keep this suite as a dedicated pytest invocation. Mixing `test_runtime_e2e_celery.py` into a broader run with `RUN_RUNTIME_E2E_CELERY=1` still risks false-negative async engine cross-loop failures from earlier tests.

If the tests time out, verify Redis/FalkorDB availability and that the worker process is connected to the same broker/result backend.

## Trigger inline-content migration

```bash
curl -X POST "http://localhost:8010/api/control-plane/projects/<project_id>/migrate-inline-to-object" \
  -H "Content-Type: application/json" \
  -H "X-Control-Plane-Assertion: <signed-assertion-from-web-bff>" \
  -d '{"force": true}'
```

## Claim legacy unowned projects

```bash
uv run python scripts/claim_legacy_projects.py --owner-id <user_id> --dry-run
uv run python scripts/claim_legacy_projects.py --owner-id <user_id>
```
