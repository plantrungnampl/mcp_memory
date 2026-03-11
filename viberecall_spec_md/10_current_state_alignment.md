# 10 — Current State Alignment

Tài liệu này neo spec vào artifact thực tế trong repo để giảm khả năng spec drift.

## 1) Repo anchors

### MCP runtime
- `apps/mcp-api/src/viberecall_mcp/mcp_app.py`
- `apps/mcp-api/src/viberecall_mcp/tool_registry.py`
- `apps/mcp-api/src/viberecall_mcp/tool_access.py`
- `apps/mcp-api/src/viberecall_mcp/tool_handlers.py`
- `apps/mcp-api/src/viberecall_mcp/canonical_memory.py`

### Persistence / schema
- `apps/mcp-api/src/viberecall_mcp/repositories/canonical_memory.py`
- `apps/mcp-api/src/viberecall_mcp/repositories/operations.py`
- `apps/mcp-api/migrations/014_canonical_memory_v3.sql`
- `apps/mcp-api/migrations/016_pin_memory_salience.sql`
- `apps/mcp-api/migrations/017_entity_resolution_foundation.sql`
- `apps/mcp-api/migrations/018_unresolved_mentions_identity.sql`

### Control-plane API
- `apps/mcp-api/src/viberecall_mcp/control_plane.py`
- `apps/mcp-api/src/viberecall_mcp/control_plane_auth.py`
- `apps/mcp-api/src/viberecall_mcp/control_plane_assertion.py`

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
- 25 public MCP tools
- project-scoped PAT auth with scope-aware tool discovery/call enforcement
- signed web -> backend assertion
- canonical Postgres memory foundation (`facts`, `entities`, `search docs`, `operations`, `working memory`)
- graph read surfaces (`search_entities`, `get_neighbors`, `find_paths`, `explain_fact`)
- entity-resolution surfaces (`resolve_reference`, `merge_entities`, `split_entity`) plus unresolved-mention persistence
- salience pinning/read-through support
- async Postgres-backed indexing and context-pack retrieval
- control-plane exports and maintenance jobs
- Vercel + Render public-GA deployment artifacts

## 3) Deferred / intentionally not public
- public import pipeline cho exported memory
- MCP Resources / Prompts capability
- hard quota blocking ở MCP runtime
- cross-project shared memory
- dedicated unresolved-mention backlog/admin read surface

## 4) Drift rules
- Nếu tool list đổi, cập nhật `04_tools_contract.md`, `00_overview.md`, và README entrypoints cùng lúc.
- Nếu env/deployment contract đổi, cập nhật `09_deployment_roadmap.md` và README docs.
- Nếu indexing/output shape đổi, cập nhật `05_data_model_temporal.md`, `06_pipelines_latency.md`, và appendices liên quan.
- Nếu trust boundary hoặc scope model đổi, cập nhật `03_auth_tenancy.md` ngay trong cùng PR.
