---
title: MCP Runtime Protocol
status: normative
version: 3.0
---
# 03 — MCP Runtime Protocol

## 1. Transport strategy
### Primary transport
VibeRecall core server MUST support **Streamable HTTP** cho remote clients.

### Secondary transport
`stdio` MAY được dùng cho **local workspace bridge** hoặc local dev harness; core hosted memory service không bắt buộc cung cấp stdio.

### Explicit anti-goal
Thiết kế không phụ thuộc vào SSE transport. Nếu framework tự support SSE, đó chỉ là compatibility layer chứ không phải primary path.

## 2. Endpoint model
Recommended endpoint shape:
- `/mcp/projects/{project_slug}`
- hoặc `/p/{project_id}/mcp`

Mỗi endpoint vẫn phải enforce project binding từ token, không chỉ từ URL.

## 3. Capability model
### Required
- `tools`

### Optional
- `resources`
- `prompts`

Core product correctness MUST NOT depend on optional capabilities, vì một số MCP clients/connectors chỉ dùng tool calls.

## 4. Tool discovery and scoping
`tools/list` MUST chỉ trả về tools mà token hiện tại được phép dùng.

Điều này phục vụ 3 mục tiêu:
1. least privilege
2. giảm tool overload cho model
3. tránh lộ admin/destructive surface

## 5. Structured tool outputs
Mọi public tool SHOULD:
- publish `inputSchema`
- publish `outputSchema`
- return `structuredContent` đúng schema
- đồng thời return text serialization để tương thích backward

## 6. Error model
Có 2 lớp lỗi:
- **JSON-RPC / protocol errors** cho invalid method, invalid arguments, auth handshake failure
- **tool execution errors** trong result với `isError=true`

Rule:
- business error dự đoán được phải là tool execution error có code cụ thể
- chỉ dùng generic internal protocol error cho lỗi server-level thật sự

## 7. Session model
Runtime SHOULD cố gắng stateless nhất có thể.
Nếu framework/client buộc session state, session metadata phải nằm ở Redis hoặc equivalent shared store, không nằm process-local.

Session state tối thiểu:
- project binding
- token fingerprint
- negotiated capabilities
- expiry
- revocation generation number

## 8. Revocation semantics
- token revoke phải có hiệu lực ngay cho request mới
- session reuse sau revoke phải bị chặn bằng revalidation hoặc generation check
- không dựa vào “session đã initialize trước đó nên cứ cho chạy”

## 9. Snapshot and pagination semantics
Các APIs trả list phải hỗ trợ cursor/pagination.
Nếu list chịu ảnh hưởng projection churn, server MUST trả `snapshot_token` hoặc watermark equivalent để pin semantic view.

## 10. Notifications
Nếu list tools/resources/prompts thay đổi do feature flags hoặc scope change, server MAY phát `list_changed` notifications nếu transport/framework cho phép.
Nhưng client correctness không được phụ thuộc notification; client luôn có thể re-list.

## 11. Request correlation
Mỗi request MUST có:
- `request_id`
- `project_id`
- `token_id or fingerprint`
- optional `operation_id`
- trace context nếu có

## 12. Content size policy
Tool result MUST có hard cap.
Nếu output lớn:
- trả summary trong text + structuredContent
- trả thêm resource link hoặc stable ids để fetch tiếp
- không đổ thẳng blob khổng lồ vào context

## 13. Versioning
Tool names SHOULD ổn định.
Breaking schema changes phải theo 1 trong 2 cách:
- new tool name
- same tool name nhưng guarded by explicit server protocol version and compatible fields

## 14. Client feature mismatch policy
Vì client support khác nhau:
- tools = mandatory and sufficient
- resources/prompts = optional enhancements
- roots/sampling/other client features MUST NOT là nền tảng correctness của v1
