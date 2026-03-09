# 01 — Kiến trúc tổng thể

## 1) Tech stack hiện tại
- **Web control plane**: Next.js 16 App Router, Tailwind, shadcn/ui, TanStack Query
- **Backend API + MCP runtime**: FastAPI + FastMCP
- **Relational state**: Postgres
- **Graph memory**: FalkorDB, với adapter `local | falkordb | graphiti`
- **KV / rate limit / idempotency / queue broker**: Redis hoặc local fallback
- **Async workers**: eager queue cho local, Celery cho production-shaped runtime
- **Object storage**: local filesystem hoặc R2-compatible object store cho large episodes

## 2) System split

### A. Web control plane — `apps/web`
Chịu trách nhiệm:
- Supabase-authenticated session
- projects directory và project workspace
- token lifecycle
- usage analytics, API logs, exports, maintenance actions
- graph playground và timeline UI
- BFF route handlers dưới `app/api/projects/**`

### B. Control-plane API — `apps/mcp-api`
Chịu trách nhiệm:
- owner-scoped CRUD/read endpoints cho projects, tokens, usage, graph, logs, exports
- signed assertion verification cho request từ web
- request correlation qua `X-Request-Id`
- enqueue các background jobs cho export, retention, purge, inline migration

### C. MCP data plane — `apps/mcp-api`
Chịu trách nhiệm:
- Streamable HTTP MCP endpoint tại `/p/{project_id}/mcp`
- PAT auth, project binding, origin/payload checks, rate limiting, idempotency
- dispatch 11 public `viberecall_*` tools
- normalize tool outputs theo output envelope ổn định

### D. Worker runtime
Chịu trách nhiệm:
- ingest episode vào graph memory
- temporal update
- export generation
- retention / purge / migrate-inline-to-object
- async repo indexing

## 3) Storage topology

### Postgres
Lưu canonical relational state:
- projects, owners, tokens
- episodes, usage events, audit logs
- exports, webhooks
- code index runs/files/entities/chunks

### FalkorDB
Lưu graph memory theo project:
- episodes, facts, entities, provenance relationships
- graph state được truy cập qua memory-core adapter

### Redis
Dùng cho:
- rate limiting
- idempotency store
- Celery broker/result backend trong production-shaped runtime

### Object storage
Dùng cho:
- raw episode content vượt threshold inline
- export artifact JSON

## 4) Runtime modes
- `MEMORY_BACKEND=local`: local in-memory adapter cho dev/test
- `MEMORY_BACKEND=falkordb`: canonical runtime graph backend
- `MEMORY_BACKEND=graphiti`: graphiti-backed mode nhưng vẫn phụ thuộc graph runtime/dependency path hiện tại
- `QUEUE_BACKEND=eager`: job chạy inline
- `QUEUE_BACKEND=celery`: job chạy qua worker riêng

## 5) Current deployment topology
```text
Browser / IDE client
  -> Vercel (apps/web)
      -> BFF route handlers + Server Actions
          -> Render API (apps/mcp-api)
              -> Postgres
              -> FalkorDB
              -> Redis
              -> Celery worker
```

## 6) Web architecture notes
- `app/projects/(app-shell)` giữ shared shell và query provider
- `(workspace)` và `(ops)` route groups tách workspace tabs khỏi ops surfaces
- project detail mặc định redirect vào Graph Playground
- BFF handlers dưới `app/api/projects/**` giữ auth ở server-side và chuẩn hóa lỗi upstream

## 7) Backend architecture notes
- FastMCP được mount trực tiếp vào FastAPI app
- control-plane router và MCP runtime cùng chia sẻ request correlation / env contract
- health probe báo `ok | degraded` theo dependency state
- graph-backed tool failures được chuẩn hóa thành deterministic runtime errors thay vì lỗi opaque
