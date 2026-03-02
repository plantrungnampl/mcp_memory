# 02 — MCP Protocol (Remote Server)

## 1) Endpoint
- Primary: **Streamable HTTP**
- URL: `https://mcp.viberecall.ai/p/{project_id}/mcp`

## 2) Transport behavior
- POST: gửi message (JSON) lên MCP server
- GET: optional mở stream (SSE) nếu server muốn push notifications

> Nếu client không dùng SSE: vẫn hoạt động bình thường (request/response via POST).

## 3) Versioning & negotiation
- Server hỗ trợ nhiều phiên bản MCP (primary + fallback).
- Client gửi `initialize` với version nó support.
- Server trả về version negotiated.
- Server có thể enforce header `MCP-Protocol-Version` cho các request sau handshake (nếu client gửi).

## 4) Lifecycle bắt buộc
1. Client → `initialize`
2. Server → `InitializeResult` (capabilities + serverInfo)
3. Client → `notifications/initialized`
4. Client → `tools/list`
5. Client → `tools/call`

## 5) Capabilities
### Tools (required)
- `tools/list` (cursor pagination)
- `tools/call`

### Optional (để “MCP full” hơn)
- Resources: expose timeline/export như “readable objects” + subscribe
- Prompts: workflow templates (recall-before-plan, save-after-decision)

## 6) Notifications
- `notifications/tools/list_changed`: khi plan thay đổi → tool set thay đổi
- (optional) `notifications/resources/updated`: timeline/export updated nếu bật resources

## 7) Error strategy
- Tool errors trả `isError=true` trong tool result
- Đồng thời trả HTTP status phù hợp khi transport cho phép (401/403/429/500)


## 8) Product surface (chốt cứng v0.1)

Để khóa scope MVP rõ ràng:
- **Transport**: chỉ **Streamable HTTP** (1 endpoint). Không triển khai SSE server-push riêng trong v0.1.
- **Capabilities**: chỉ bật **Tools** (`tools/list`, `tools/call`).  
  - **Resources** và **Prompts**: out-of-scope v0.1 (phase sau).
- **MCP-Protocol-Version**: server **enforce** strict sau khi negotiate (client thiếu header vẫn được tolerate trong v0.1, nhưng log warning).

Kết quả: MVP tập trung ship “tools native” ổn định, không kéo scope sang resources/prompts.

