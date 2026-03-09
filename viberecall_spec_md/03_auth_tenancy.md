# 03 — Auth & Tenancy

## 1) Trust boundaries

### Browser -> web app
- Người dùng đăng nhập bằng **Supabase auth**
- Web app dùng server-side auth checks cho protected routes

### Web -> control-plane API
- Không forward raw user identity qua header thường
- Web ký short-lived assertion và gửi:
  - `X-Control-Plane-Assertion`
  - `X-Request-Id`
- Backend verify signature, issuer, audience, timestamps

### IDE / MCP client -> MCP endpoint
- IDE chỉ dùng bearer PAT:
  - `Authorization: Bearer vr_mcp_sk_...`

## 2) MCP token model
Token record lưu:
- `token_id`
- `token_hash`
- `prefix`
- `project_id`
- `scopes[]`
- `plan`
- `created_at`, `last_used_at`, `revoked_at`, `expires_at`

Plaintext token chỉ được hiển thị một lần khi tạo hoặc rotate.

## 3) Project binding
- `project_id` lấy từ path `/p/{project_id}/mcp`
- Token hợp lệ nhưng khác `project_id` -> `403`
- Runtime graph name/prefix được derive từ project, không tin tenant input từ client

## 4) Scope model hiện tại
Default MCP scopes hiện hành:
- `memory:read`
- `memory:write`
- `facts:read`
- `facts:write`
- `timeline:read`

Control-plane maintenance/export không dùng MCP PAT scopes; chúng là owner-scoped web/control-plane actions.

## 5) Runtime access policy hiện tại
- Bất kỳ token hợp lệ nào cũng thấy toàn bộ **11 public MCP tools**
- `plan` vẫn được lưu làm metadata nhưng không còn là tool-gating surface ở runtime
- Quota hiện dùng cho metering/analytics, không block tool execution
- Rate limit, payload cap, idempotency, auth, expiry, revoke, project binding vẫn được enforce

## 6) Rate limit & idempotency
- Rate limit per token và per project
- Write paths hỗ trợ `Idempotency-Key`
- Reuse cùng idempotency key nhưng payload khác -> `409 CONFLICT`

## 7) Revocation / rotation
- `revoked_at <= now` -> token không còn hợp lệ
- `revoked_at > now` có thể được dùng như grace-period valid token trong lifecycle hiện tại
- Rotate tạo token mới, token cũ bị revoke theo semantics ở DB

## 8) Origin / payload protections
- MCP runtime có thể enforce `Origin` allowlist khi được cấu hình
- Request payload bị giới hạn kích thước
- Missing / invalid bearer token -> `401`
- Missing control-plane assertion ở backend route từ web -> `401`
