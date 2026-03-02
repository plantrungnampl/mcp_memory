# 09 — Deployment & Roadmap


## 0) Deployment decisions (chốt cứng v0.1)

- **Primary platform (MVP)**: **Fly.io** (data plane)  
- **Region**: **Singapore (sin)** (tối ưu latency cho VN/TH/SEA)  
- **Control plane**: **Supabase** (Auth + Postgres)  
- **Redis**: **Upstash Redis**  
- **Object storage**: **Cloudflare R2** (exports + large episodes)  
- **Secrets management**: Fly secrets + Supabase env vars  
- **Backups**:
  - Supabase: managed backups
  - Neo4j: nightly dump per database + store in R2 (retention 7–30 days)


## 1) MVP deployment (single-region)
- 1 container: MCP Gateway + API + Worker (monolith)
- Redis managed
- Postgres (Supabase)
- Graph DB single node (**Neo4j**)
- Object storage (optional) cho exports/raw episodes

## 2) Scale-out
Split services:
- `mcp-gateway` (stateless autoscale)
- `workers` (autoscale theo queue depth)
- Graph DB cluster (**Neo4j cluster**)
- Redis cluster (nếu cần)

## 3) CI/CD
- GitHub Actions: build + test + deploy (Railway/Fly/K8s)
- Migration scripts (DB schema)

## 4) Roadmap 7 ngày (MVP)
Day 1–2:
- Supabase schema + token mgmt
- MCP gateway skeleton + initialize/tools/list/call
- Graph-per-project routing

Day 3:
- Auth middleware + rate limit + quota counters
- Idempotency framework

Day 4:
- Implement 5 tools + integration tests với Cursor/Claude/Windsurf (backend: FastMCP + FastAPI)

Day 5:
- Dashboard: login, project list, create, show URL/token, rotate/revoke

Day 6:
- Docker compose + deploy
- Usage metering (VibeTokens) + Stripe webhook

Day 7:
- Landing + docs onboarding + launch channels

## 5) Definition of Done (v0.1)
- A dev connect MCP URL+token trong IDE → thấy tools → save/search hoạt động.
- Không thể leak cross-project data.
- Usage token metering lên dashboard.
