# 00 — Tổng quan

## 1) Tầm nhìn
**VibeRecall** là *Memory-as-a-Service* cho coding agents (Claude Code, Cursor, Windsurf…), giúp agent:
- Nhớ **quyết định thiết kế**, **bug đã fix**, **requirement**, **file structure**, **code style**…
- **Temporal-aware / bi-temporal**: phân biệt *event time* (`reference_time`) và *transaction time* (`ingested_at`)
- **Incremental update** (không rebuild graph)
- **Isolation 100%** theo project

**Slogan:** “Never forget a single line of code again.”  
**Tagline:** Long-term memory for your coding agent — Native MCP.

## 2) Non-goals (v0.1)
- Không làm chat app
- Không làm full repo indexing/crawler (phase sau)
- Không làm realtime collaboration phức tạp (phase sau)

## 3) Product mode
- **Pro (Native MCP tools)**: user connect 1 lần vào IDE → có tools built-in.
- Có **REST fallback** (optional) cho client chưa hỗ trợ MCP.

## 4) Chốt “decision points” trước khi code
1. **MCP endpoint**: `https://mcp.viberecall.ai/p/{project_id}/mcp`
2. **IDE auth**: chỉ dùng **Project Access Token (PAT)** qua `Authorization: Bearer ...`
3. **Save pipeline**: **2-phase write** (fast-ack + async enrich)
4. **Temporal update**: `update_fact` bắt buộc có `effective_time`
5. **Isolation**: `1 project = 1 graph` (hard isolation)
6. **Pricing**: theo **token** (định nghĩa VibeTokens & metering rõ ràng)

## 4.1) Tech decisions (đã chốt cứng cho v0.1)
- **Backend language/framework**: **Python (FastMCP + FastAPI)**
- **Graph DB vendor**: **Neo4j** (*ưu tiên SaaS licensing rõ ràng + ecosystem tooling ổn định*)

> Ghi chú: thiết kế vẫn giữ adapter layer để có thể thay Graph DB (ví dụ FalkorDB) ở phase sau nếu cần.

## 5) Core deliverables (MVP)
- MCP Gateway + Auth + Rate limit
- 5 tools: save/search/get_facts/update_fact/timeline
- Dashboard: login + create project + show MCP URL + token (copy 1 lần) + rotate/revoke
- Usage metering (token) + Stripe webhook (upgrade/downgrade)
