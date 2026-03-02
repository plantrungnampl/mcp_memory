# 08 — Observability & Security

## 1) Logs (structured)
Mỗi request/tool call ghi:
- `request_id`, `mcp_session_id`
- `project_id`, `token_id`
- `tool_name`, `args_hash`
- `latency_ms`, `status`, `error_code`

## 2) Metrics (Prometheus)
- `tool_call_latency_ms{tool=...}` (p50/p95)
- `mcp_initialize_latency_ms`
- `rate_limited_count`
- `queue_depth{queue=...}`
- `job_duration_ms{job=...}`
- `graph_db_latency_ms`
- `tokens_burn_rate{project=...}`

## 3) Tracing (OpenTelemetry)
Trace chain:
MCP request → auth → quota → store raw → enqueue → worker → graph write

## 4) Security checklist (MCP-specific)
- TLS only + HSTS
- Validate `Origin` allowlist (DNS rebinding mitigation)
- Bearer token required on all MCP calls
- Strict token ↔ project binding (URL path must match token mapping)
- Payload size caps
- Rate limit per token + per project
- Idempotency for writes
- Token rotation + revoke
- Audit logs (immutable-ish)

## 5) Data retention & deletion
- Retention per project (days)
- Purge project:
  - drop graph
  - delete raw episodes (DB/object storage)
  - delete exports
  - scrub sensitive content in logs (store hashes only)

## 6) Dependency risk notes
- Graph DB vendor chốt v0.1: **Neo4j** (per-project database). Theo dõi health/latency/heap/page cache.

- Upstream MCP/Graphiti changes: pin versions, keep `viberecall_*` tools stable.
- Graph DB licensing: đảm bảo legal path nếu public SaaS.
