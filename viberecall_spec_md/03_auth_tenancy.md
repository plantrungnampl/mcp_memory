# 03 — Auth & Tenancy (MCP-first)

## 1) Nguyên tắc
- Dashboard dùng Supabase JWT (web session).
- IDE/MCP **không dùng JWT**. IDE chỉ gửi **PAT**:
  - `Authorization: Bearer vr_mcp_sk_...`

## 2) Token model (PAT)
Token record:
- `token_id`
- `token_hash` (không lưu plaintext)
- `prefix` (để hiển thị)
- `project_id`
- `scopes[]`
- `plan`
- `created_at`, `last_used_at`, `revoked_at`, `expires_at` (optional)

## 3) Binding với project_id trong URL
Path: `/p/{project_id}/mcp`
- Parse `project_id` từ path.
- Verify token → token phải map đúng `project_id`.
- Nếu token valid nhưng project mismatch → 403.

## 4) Scopes (tối thiểu)
- `memory:read`, `memory:write`
- `facts:read`, `facts:write`
- `timeline:read`
- `admin:export`, `admin:purge`

## 5) Rate limit & idempotency
- Rate limit per `token_id` + per `project_id` (Redis token bucket).
- Idempotency:
  - Header: `Idempotency-Key` (write endpoints / save/update/export)
  - TTL: 24h
  - same key + different payload → 409

## 6) Multi-tenant isolation
Hard isolation:
- `graph_name = vr_{project_id}` (sanitize)
- Mọi Graphiti calls phải bind theo graph_name tenant.
- Không nhận group_id từ client.

## 7) Rotation & revoke
- Token chỉ show plaintext **1 lần** khi tạo.
- Rotate = tạo token mới + revoke token cũ (grace period optional).


## 8) Token lifecycle policy (chốt cứng v0.1)

- **Default expiration**: tokens **không hết hạn** (expires_at = null) trừ khi user set khi tạo.
- **Rotate grace period**: 15 phút (token cũ vẫn valid để IDE reconnect).
- **Emergency revoke propagation**:
  - Gateway check Redis **revocation set** trước (TTL 24h) để revoke gần-real-time.
  - Cache token status tối đa 30s; revoke sẽ invalidate cache qua Redis pubsub (nếu có), nếu không thì worst-case 30s.
- **Audit**:
  - mọi tool call ghi `token_id`, `request_id`, `tool_name`, `args_hash`, `status`.

