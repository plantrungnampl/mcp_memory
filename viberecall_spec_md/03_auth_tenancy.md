# 03 — Auth & Tenancy

## 1) Trust boundaries

### Browser -> web app
- Người dùng đăng nhập bằng **Supabase auth**.
- Web app dùng server-side auth checks cho protected routes.

### Web -> control-plane API
- Không forward raw user identity qua header thường.
- Web ký short-lived assertion và gửi:
  - `X-Control-Plane-Assertion`
  - `X-Request-Id`
- Backend verify signature, issuer, audience, timestamps.

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
- `project_id` lấy từ path `/p/{project_id}/mcp`.
- Token hợp lệ nhưng khác `project_id` -> `403`.
- Runtime graph name/prefix được derive từ project, không tin tenant input từ client.

## 4) Scope model hiện tại
Canonical scopes hiện hành:
- `memory:read`
- `memory:write`
- `facts:write`
- `entities:read`
- `graph:read`
- `index:read`
- `index:run`
- `resolution:write`
- `ops:read`
- `delete:write`

Legacy aliases vẫn được chấp nhận cho compatibility:
- `memory:read` có thể satisfy một số read surfaces như `entities:read`, `graph:read`, `index:read`, `ops:read`
- `memory:write` có thể satisfy một số write surfaces như `index:run`, `delete:write`
- `codeindex:read` và `codeindex:write` vẫn được map vào index scopes hiện hành

Control-plane maintenance/export không dùng MCP PAT scopes; chúng là owner-scoped web/control-plane actions.

## 5) Runtime access policy hiện tại
- Bất kỳ token hợp lệ nào cũng có thể thấy **plan-wide tool surface**, nhưng `tools/list` và `tools/call` vẫn bị lọc/enforce theo token scope.
- `plan` vẫn được lưu làm metadata, nhưng hiện không còn là meaningful gating surface vì `free`, `pro`, và `team` cùng allow cùng tool catalog.
- Quota hiện dùng cho metering/analytics, không hard-block tool execution.
- Scope validation, rate limiting, payload cap, idempotency, auth, expiry, revoke, và project binding vẫn được enforce.

## 6) Rate limit & idempotency
- Rate limit per token và per project.
- Write paths hỗ trợ `Idempotency-Key` hoặc `idempotency_key` tùy tool surface.
- Reuse cùng idempotency key nhưng payload khác -> `409 CONFLICT`.

## 7) Revocation / rotation
- `revoked_at <= now` -> token không còn hợp lệ.
- `revoked_at > now` có thể được dùng như grace-period valid token trong lifecycle hiện tại.
- Rotate tạo token mới, token cũ bị revoke theo semantics ở DB.

## 8) Origin / payload protections
- MCP runtime có thể enforce `Origin` allowlist khi được cấu hình.
- Request payload bị giới hạn kích thước.
- Missing / invalid bearer token -> `401`.
- Missing control-plane assertion ở backend route từ web -> `401`.
