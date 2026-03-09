# 08 — Observability & Security

## 1) Structured logs
Các request/tool calls hiện cần correlation qua:
- `request_id`
- `project_id`
- `token_id` khi có
- `tool_name`
- `status`
- `latency_ms`

Control-plane requests từ web cũng log:
- assertion attached hay không
- user identity presence
- backend response request id

## 2) Metrics
Các metric classes quan trọng:
- MCP initialize latency
- tool call latency
- queue depth
- worker job duration
- token burn gauge
- graph/runtime dependency health

## 3) Health & degradation
- `/healthz` báo `ok` hoặc `degraded`
- graph dependency outages phải surfaced rõ ràng
- graph-backed tool failures phải trả deterministic runtime errors thay vì opaque internal failures
- `get_status` phải phản ánh dependency degradation tương tự health probe

## 4) Security controls
- TLS only ở deployed environment
- strict token -> project binding
- signed `X-Control-Plane-Assertion` giữa web và backend
- `X-Request-Id` echo để debug mà không log secret payload
- payload size caps
- rate limit per token và per project
- idempotency cho write paths
- revoke / expiry enforcement cho PAT
- origin allowlist khi được cấu hình

## 5) Session / transport risks
- stale `mcp-session-id` có thể gây `404 Session not found`
- wrong `Accept` negotiation có thể gây `406`
- thiếu `MCP-Protocol-Version` hiện chỉ warning, nhưng nên được client gửi đúng

## 6) Dependency risks
- FalkorDB availability là critical dependency cho graph-backed runtime
- Graphiti mode vẫn phụ thuộc graph runtime path hiện tại
- Redis/Celery là critical trong production-shaped async runtime
- object storage outage ảnh hưởng export và large-episode paths

## 7) Audit policy
- MCP tools và control-plane actions đều ghi audit logs
- API Logs operator-facing page hiện chỉ tập trung vào MCP `tools/call`
- raw internal audit rows vẫn có thể tồn tại cho vận hành backend
