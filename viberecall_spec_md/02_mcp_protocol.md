# 02 — MCP Protocol

## 1) Endpoint
- Primary endpoint: `https://api.<domain>/p/{project_id}/mcp`
- Transport hiện tại: **Streamable HTTP** qua FastMCP

## 2) Lifecycle
1. `initialize`
2. `notifications/initialized`
3. `tools/list`
4. `tools/call`

Server trả:
- `protocolVersion = 2025-06-18`
- `serverInfo.name = viberecall-mcp`
- `capabilities.tools.listChanged = true`

## 3) Transport behavior hiện tại
- `POST` là đường chính cho MCP messages
- `GET` vẫn thuộc Streamable HTTP surface của FastMCP
- client phải chấp nhận media types MCP phù hợp; request không đúng có thể nhận `406`
- `MCP-Protocol-Version` được chấp nhận và validate sau initialize; thiếu header hiện tại không hard-fail nhưng bị log warning

## 4) Session semantics
- Session là **stateful**
- Nếu client gửi `mcp-session-id` cũ sau backend reload hoặc reconnect sai cách, server có thể trả `404 Session not found`
- Cách khôi phục chuẩn là reconnect và chạy `initialize` lại để lấy session mới

## 5) Auth semantics
- Path luôn chứa `project_id`
- Tool methods yêu cầu bearer PAT gắn đúng project
- `initialize` là lifecycle handshake; phần auth enforcement quan trọng nằm ở tool-capable request path sau handshake

## 6) Capabilities
Current release chỉ coi **Tools** là capability public:
- `tools/list`
- `tools/call`

Không cam kết public support cho:
- Resources
- Prompts
- custom server-push workflows

## 7) Error strategy
- Tool result luôn dùng MCP text payload chứa JSON envelope chuẩn
- Khi lỗi, payload giữ `ok=false` và `error.code/message/details`
- Transport-level HTTP status vẫn có thể phản ánh lỗi auth/payload/origin/session khi FastMCP/FastAPI surface cho phép
