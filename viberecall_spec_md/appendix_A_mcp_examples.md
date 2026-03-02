# Appendix A — MCP Message Examples (high-level)

> Ví dụ minh hoạ; payload exact sẽ phụ thuộc MCP SDK mà client dùng.

## A1) Initialize
Client → server: `initialize`
- gửi clientInfo + supported versions
Server → client: InitializeResult
- serverInfo
- capabilities: tools/resources/prompts (tùy bật)

Client → server: `notifications/initialized`

## A2) List tools
Client → `tools/list`
Server → list tools + inputSchema

## A3) Call tool: viberecall_save
Client → `tools/call`:
- name: viberecall_save
- arguments: content/reference_time/metadata

Server → tool result:
- content: [{type:"text", text:"{...json...}"}]
- isError: false

## A4) Call tool: viberecall_search
Client → `tools/call` (search query + filters)
Server → results + next_cursor

## A5) Plan change → tools/list_changed
Nếu user upgrade plan, server gửi notification:
- client refresh `tools/list` để thấy tool mới/limits mới
