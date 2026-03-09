# 10 — Current State Alignment

Tài liệu này neo spec vào artifact thực tế trong repo để giảm khả năng spec drift.

## 1) Repo anchors

### MCP runtime
- `apps/mcp-api/src/viberecall_mcp/mcp_app.py`
- `apps/mcp-api/src/viberecall_mcp/tool_registry.py`
- `apps/mcp-api/src/viberecall_mcp/tool_handlers.py`

### Control-plane API
- `apps/mcp-api/src/viberecall_mcp/control_plane.py`
- `apps/mcp-api/src/viberecall_mcp/control_plane_auth.py`
- `apps/mcp-api/src/viberecall_mcp/control_plane_assertion.py`

### Code indexing
- `apps/mcp-api/src/viberecall_mcp/code_index.py`
- `apps/mcp-api/migrations/011_code_index_async_postgres.sql`

### Runtime topology / env
- `render.yaml`
- `.env.production.example`
- `ops/vercel-render-public-ga.md`

### Web control plane
- `apps/web/src/app/projects/(app-shell)`
- `apps/web/src/app/api/projects`
- `apps/web/src/lib/api/control-plane.ts`
- `apps/web/src/lib/api/control-plane-headers.ts`

## 2) Implemented now
- 11 public MCP tools
- project-scoped PAT auth
- signed web -> backend assertion
- graph playground as default project detail entry
- async Postgres-backed indexing
- control-plane exports and maintenance jobs
- Vercel + Render public-GA deployment artifacts

## 3) Deferred / intentionally not public
- public import pipeline cho exported memory
- MCP Resources / Prompts capability
- hard quota blocking ở MCP runtime
- cross-project shared memory

## 4) Drift rules
- Nếu tool list đổi, cập nhật `04_tools_contract.md` trước
- Nếu env/deployment contract đổi, cập nhật `09_deployment_roadmap.md` và `README.md`
- Nếu indexing/output shape đổi, cập nhật `05_data_model_temporal.md`, `06_pipelines_latency.md`, và appendices liên quan
- Nếu trust boundary đổi, cập nhật `03_auth_tenancy.md` ngay trong cùng PR
