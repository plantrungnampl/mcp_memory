---
title: Authentication and Authorization Policy
status: normative
version: 3.0
---
# 04 — Authentication and Authorization Policy

## 1. Identity model
Có 3 principal classes:
1. **Owner principal** — con người quản lý project
2. **Agent token principal** — token cho Codex/Claude/CI agents
3. **Operator principal** — internal admin/support

## 2. Token types
### Owner PAT
- full control hoặc near-full control
- không nên dùng cho automated agents trừ khi internal-only

### Agent token
- scope hẹp, TTL giới hạn
- dành cho coding agents
- mặc định không có destructive/admin scopes

### CI token
- tối ưu cho indexing / read / save automation
- có thể được gắn source restrictions

## 3. Scope model
Recommended scopes:
- `memory:read`
- `memory:write`
- `memory:delete`
- `facts:write`
- `entities:read`
- `graph:read`
- `resolution:write`
- `codeindex:read`
- `codeindex:write`
- `export:read`
- `ops:read`
- `status:read`

## 4. Tool-to-scope matrix
| Tool | Required scope |
|---|---|
| `viberecall_search_memory` | `memory:read` |
| `viberecall_get_context_pack` | `memory:read` |
| `viberecall_get_fact` | `memory:read` |
| `viberecall_search_entities` | `entities:read` or `memory:read` |
| `viberecall_get_neighbors` | `graph:read` |
| `viberecall_find_paths` | `graph:read` |
| `viberecall_explain_fact` | `memory:read` |
| `viberecall_save_episode` | `memory:write` |
| `viberecall_update_fact` | `facts:write` |
| `viberecall_pin_memory` | `facts:write` |
| `viberecall_index_repo` | `codeindex:write` |
| `viberecall_get_index_status` | `codeindex:read` |
| `viberecall_get_operation` | scope of underlying operation or `ops:read` |
| `viberecall_merge_entities` | `resolution:write` |
| `viberecall_split_entity` | `resolution:write` |
| `viberecall_delete_episode` | `memory:delete` |
| `viberecall_export_project` | `export:read` |
| `viberecall_get_status` | `status:read` |

## 5. Project isolation
Token MUST be bound to exactly one project in v1.
Không có multi-project token trong GA đầu.
Mọi query phải có predicate `project_id = token.project_id`.

## 6. Runtime enforcement
Authz check MUST chạy ở:
- tool discovery
- mỗi tool invocation
- resource read
- prompt get
- operation polling

## 7. Quotas and budgets
Authz chưa đủ. Runtime còn phải enforce:
- requests/min/token
- requests/min/project
- concurrent writes/token
- concurrent index runs/project
- bytes uploaded/day/project
- worker budget/month/project

Budget vượt hard cap => từ chối tool call có error deterministic.

## 8. Token lifecycle
- plaintext hiển thị đúng 1 lần
- store hashed
- support rotate
- support expiry
- support immediate revoke
- support labels (`codex-dev`, `claude-prod`, `ci-indexer`)

## 9. Trusted vs untrusted content
Authn/authz không bảo đảm content an toàn.
Memory content từ tool output, issue tracker, logs, code comments đều có thể mang prompt injection.
Mỗi stored item SHOULD có trust metadata:
- `USER_ASSERTED`
- `CODE_DERIVED`
- `TOOL_DERIVED`
- `EXTERNAL_UNTRUSTED`

Retrieval layer và context pack phải dùng trust metadata để giảm rủi ro.

## 10. Confirmation and sensitive operations
Với các tool write/delete/admin:
- server SHOULD mark sensitivity trong description/output metadata
- client MAY xin user confirmation
- nhưng server không được giả định client sẽ confirm; server tự enforce scope/budget/policy

## 11. Emergency controls
MUST có:
- project kill switch
- token kill switch
- indexing disable flag
- graph projection disable flag
- write freeze mode cho incident response

## 12. Audit requirements
Mọi token issuance, revoke, destructive action, merge/split entity, export, budget override phải có audit log immutable-enough.
