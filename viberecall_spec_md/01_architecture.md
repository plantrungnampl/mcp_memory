# 01 — Kiến trúc tổng thể (End-to-End)


## 0) Tech stack (chốt cứng v0.1)
- **Backend (MCP Gateway + API)**: **Python (FastMCP + FastAPI)**
- **Graph DB**: **Neo4j** (multi-tenant theo *1 project = 1 database* hoặc *1 project = 1 graph* tuỳ topology Neo4j)
- **Queue/Cache**: Redis + Celery
- **Metadata**: Supabase Postgres
  
## Frontend (Control Plane - app.viberecall.ai)
- Framework: Next.js 16.1+ (App Router)
- UI: Tailwind CSS + shadcn/ui + Radix
- Auth: Supabase Auth (GitHub + Email)
- State: TanStack Query + Zustand
- Deploy: cùng Fly.io với backend (monorepo)

## 1) Phân tách Control Plane / Data Plane

### Control Plane — `app.viberecall.ai`
Chức năng:
- Auth (GitHub/Google)
- Quản lý Projects
- Quản lý Tokens (create/rotate/revoke)
- Plan/Billing + Usage dashboard
- Webhooks (optional), Audit log

Data store:
- Postgres (Supabase) lưu metadata: users/projects/tokens/plans/usage/audit/webhooks

### Data Plane — `mcp.viberecall.ai``
Chức năng:
- MCP Remote Server (Streamable HTTP)
- Auth middleware (Bearer PAT)
- Tenancy routing (project → graph)
- Rate limit + quota + metering
- Tool routing → Memory Core (Graphiti + Graph DB)
- Background jobs: enrichment/export/webhook

## 2) Thành phần chính



## 2.1) Graph DB (chốt cứng v0.1)

**Vendor:** **Neo4j**  
**Isolation mode:** **1 project = 1 Neo4j database** (multi-database).  
- `db_name = "vr_" + project_id` (sanitize)  
- Gateway/adapter luôn route theo `db_name` (không nhận project_id/group_id từ client).

**Storage model (canonical, không mơ hồ):** Facts là **nodes** (không phải edge) để:
- gắn bi-temporal fields (`valid_at`, `invalid_at`, `ingested_at`) và provenance rõ ràng
- dedupe, update temporal, export ổn định

**Canonical labels/relationships**
- `(:Episode {episode_id, reference_time, ingested_at, content_ref, metadata_json, ...})`
- `(:Entity {entity_id, type, name, aliases[], ...})`
- `(:Fact {fact_id, text, valid_at, invalid_at, ingested_at, confidence, ...})`
Relationships:
- `(Episode)-[:MENTIONS]->(Entity)`
- `(Episode)-[:SUPPORTS]->(Fact)`
- `(Fact)-[:ABOUT]->(Entity)` (1..N entities)

**Indexes / constraints (v0.1)**
- UNIQUE: `Episode(episode_id)`, `Entity(entity_id)`, `Fact(fact_id)`
- BTREE: `Entity(type, name)` ; `Fact(valid_at)` ; `Fact(invalidated_at)` ; `Episode(ingested_at)`
- FULLTEXT: `Fact.text`, `Episode.content_ref_or_text` (tuỳ storage)
- (Optional) VECTOR: `Fact.embedding`, `Episode.embedding` (nếu dùng vector index trong Neo4j)

> Note: FalkorDB chỉ là *future alternative* (không nằm trong v0.1) để tránh ambiguity + licensing discussion trong scope v0.1.

```text
IDE (Cursor / Claude Code / Windsurf)
  ↓ MCP (Streamable HTTP + optional SSE)
MCP Gateway (stateless)
  ↓ internal calls + queue
Memory Core (Graphiti adapter)
  ↓
Graph DB (Neo4j; 1 project = 1 database)
  ↑↓
Redis (rate limit, idempotency, queue)
  ↑↓
Metadata DB (Supabase Postgres) + Stripe webhook
```

## 3) Trách nhiệm từng service

### MCP Gateway (stateless)
- TLS termination
- Validate MCP headers + lifecycle
- Verify `Authorization: Bearer ...`
- Resolve `project_id`, `scopes`, `plan`
- Rate limit / payload cap / idempotency
- Route `tools/call` đến handler tương ứng
- Ghi audit & usage events

### Memory Core (Graphiti adapter)
- Map tool inputs → Graphiti operations
- Bind graph theo tenant (không tin input group_id từ client)
- Temporal semantics (reference_time / valid_at / as_of_ingest)
- Normalize outputs (fact/entity/provenance)

### Workers
- `ingest_job`: add_episode + extract facts/entities
- `update_fact_job`: invalidate old + create new
- `export_job`: dump graph → object storage → signed URL
- `webhook_job`: retries + DLQ

## 4) Lưu ý kiến trúc
- “<200ms latency” áp dụng cho `save` nếu **fast-ack** + async.
- Search có thể >200ms, target theo SLO (p95 < 1.5s).
