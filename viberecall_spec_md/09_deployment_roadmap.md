# 09 — Deployment & Roadmap

## 1) Current deployment decisions
- **Web**: Vercel
- **API**: Render web service
- **Worker**: Render worker service
- **Graph memory**: Render private FalkorDB service
- **Postgres**: external managed Postgres
- **Redis / broker**: Render Key Value hoặc equivalent Redis-compatible service

Repository artifacts hiện có:
- `render.yaml`
- `ops/render/falkordb/Dockerfile`
- `ops/vercel-render-public-ga.md`
- `.env.production.example`

## 2) Production-shaped service layout
- `viberecall-api`
- `viberecall-worker`
- `viberecall-falkordb`
- Vercel project cho `apps/web`

## 3) Required env contract
Web:
- `NEXT_PUBLIC_APP_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `NEXT_PUBLIC_MCP_BASE_URL`
- `CONTROL_PLANE_API_BASE_URL`
- `CONTROL_PLANE_INTERNAL_SECRET`
- `DEPLOYMENT_VERSION`
- `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY`

API/worker:
- `APP_ENV`
- `LOG_LEVEL`
- `PUBLIC_MCP_BASE_URL`
- `PUBLIC_WEB_URL`
- `ALLOWED_ORIGINS`
- `DATABASE_URL`
- `TOKEN_PEPPER`
- `CONTROL_PLANE_INTERNAL_SECRET`
- `MEMORY_BACKEND`
- `KV_BACKEND`
- `QUEUE_BACKEND`
- `FALKORDB_HOST`
- `FALKORDB_PORT`
- `FALKORDB_GRAPH_PREFIX`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `INDEX_REPO_ALLOWED_ROOTS`
- `GRAPHITI_API_KEY`
- `GRAPHITI_LLM_MODEL`
- `GRAPHITI_EMBEDDER_MODEL`
- `GRAPHITI_MCP_BRIDGE_MODE`
- `GRAPHITI_TELEMETRY_ENABLED`
- `OBJECT_STORAGE_MODE`
- `OBJECT_LOCAL_DIR`
- `OBJECT_BUCKET`
- `OBJECT_ENDPOINT`
- `OBJECT_REGION`
- `OBJECT_ACCESS_KEY_ID`
- `OBJECT_SECRET_ACCESS_KEY`
- `OBJECT_FORCE_PATH_STYLE`
- `RAW_EPISODE_INLINE_MAX_BYTES`
- `INLINE_MIGRATION_DB_SIZE_THRESHOLD_BYTES`
- `RATE_LIMIT_TOKEN_CAPACITY`
- `RATE_LIMIT_PROJECT_CAPACITY`
- `RATE_LIMIT_WINDOW_SECONDS`
- `RECENT_EPISODE_WINDOW_SECONDS`
- `EXPORT_STORAGE_MODE`
- `EXPORT_LOCAL_DIR`
- `EXPORT_URL_TTL_SECONDS`
- `EXPORT_SIGNING_SECRET`
- `SUPABASE_SERVICE_ROLE_KEY`
- `STRIPE_WEBHOOK_SECRET`

## 4) Release gate
Chuẩn release gate hiện tại:
- `pnpm validate:web`
- `pnpm test:backend`
- `pnpm validate:release`

## 5) Deployed verification
Sau khi deploy:
1. chạy deployed MCP smoke
2. seed QA project/token
3. chạy authenticated browser QA cho:
   - `/projects`
   - `/projects/[projectId]/tokens`
   - `/projects/[projectId]/api-logs`
   - `/projects/[projectId]/usage`
   - `/projects/[projectId]/graphs/playground`

## 6) Near-term roadmap
- giữ spec package đồng bộ với repo state
- tiếp tục harden graph/runtime degradation paths
- tiếp tục theo dõi wrapper/client behavior quanh stale MCP sessions
- cân nhắc future policy cho quota gating nếu pricing chuyển sang enforce thực sự
