# Appendix A — MCP Message Examples

> Ví dụ mức high-level; payload exact phụ thuộc MCP SDK.

## A1) Initialize
Client:
- `initialize`

Server:
- `protocolVersion = 2025-06-18`
- `serverInfo = viberecall-mcp`
- `capabilities.tools.listChanged = true`

## A2) List tools
Client:
- `tools/list`

Server:
- trả catalog public `viberecall_*` tools phù hợp token scope; current runtime surface đầy đủ là 25 tools với `inputSchema`

## A3) Call `viberecall_save`
Client:
- `tools/call`
- `name = viberecall_save`
- `arguments = { content, reference_time?, metadata?, idempotency_key? }`

Server:
- text payload chứa output envelope
- `result.status = "ACCEPTED"`

## A4) Call `viberecall_index_repo`
Client:
- `tools/call`
- `name = viberecall_index_repo`
- `arguments = { repo_source, mode = "FULL_SNAPSHOT", max_files?, idempotency_key? }`
- `repo_source.type = "git" | "workspace_bundle"`

Server:
- `result.status = "ACCEPTED"`
- `result.index_run_id`
- `result.operation_id`
- `result.job_id`

## A5) Stale session recovery
Nếu client gặp `404 Session not found`:
- reconnect
- chạy `initialize` lại
- lấy session mới trước khi gọi `tools/list` hoặc `tools/call`
