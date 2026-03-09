# 00 — Tổng quan

## 1) Tầm nhìn
**VibeRecall** là project-scoped MCP memory platform cho coding agents. Mỗi project có MCP endpoint riêng, token riêng, memory graph riêng, và control-plane riêng để theo dõi usage, logs, graph state, export, và code index.

Hệ thống hiện hỗ trợ:
- lưu episode với fast-ack + async enrichment
- search facts + recent raw episodes
- temporal update / timeline / delete episode
- repo indexing + entity search + context pack cho agent workflows
- owner-scoped control plane cho projects, tokens, usage, API logs, graph, export, retention

## 2) Current product mode
- **MCP-first**: coding agent kết nối vào `/p/{project_id}/mcp`
- **Control-plane web**: người dùng quản lý project, token, usage, exports, graph playground tại web app
- **Stateful indexing**: code index được lưu trong Postgres snapshot tables và đọc qua `index_status`, `search_entities`, `get_context_pack`

## 3) Non-goals của current release
- Không mở public REST API thay thế toàn bộ MCP tool surface
- Không expose import pipeline công khai cho memory/export
- Không ship prompt/resources capability cho MCP ở release hiện tại
- Không triển khai cross-project shared memory

## 4) Hard decisions hiện tại
1. **MCP endpoint shape**: `/p/{project_id}/mcp`
2. **IDE auth**: bearer Project Access Token
3. **Control-plane auth**: Supabase session ở web; web gọi backend bằng signed assertion
4. **Isolation**: graph-per-project trên FalkorDB naming/prefix của runtime
5. **Save pipeline**: sync ACK + queued enrichment
6. **Indexing**: async job, snapshot persisted trong Postgres, latest `READY` là nguồn đọc chuẩn
7. **Deployment**: Vercel cho web, Render cho API/worker/FalkorDB
8. **Tool contract policy**: giữ ổn định prefix `viberecall_*`, mở rộng backward-compatible

## 5) Current public deliverables
- 11 public MCP tools
- owner-scoped project/token lifecycle
- usage analytics, MCP API logs, graph playground
- export jobs với signed download
- retention, purge, migrate-inline-to-object maintenance actions
- async code indexing + context-pack retrieval

## 6) Important clarifications
- Runtime graph backend canonical hiện tại là **FalkorDB**. Neo4j không còn là runtime target trong repo này.
- Export hiện là **control-plane workflow**, không phải public MCP tool.
- Plan/billing metadata vẫn tồn tại ở control plane, nhưng MCP runtime hiện cho phép toàn bộ public tools với mọi token hợp lệ; quota hiện dùng cho metering/analytics, chưa hard-block tool execution.
