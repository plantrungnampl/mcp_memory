---
title: Agent Integration for Codex CLI and Claude Code
status: normative
version: 3.0
---
# 16 — Agent Integration for Codex CLI and Claude Code

## 1. Client reality that shaped this design
Thiết kế này cố ý tối ưu cho các coding-agent MCP clients phổ biến hiện nay:

- Codex có thể dùng MCP servers qua **Streamable HTTP** hoặc **stdio**, và CLI + IDE extension dùng chung config.
- Claude Code ưu tiên **remote HTTP** cho cloud MCP servers; SSE là legacy/deprecated path.
- Claude Code có thể dùng **tools**, **resources**, **prompts**, nhưng không phải mọi Anthropic integration path đều support đủ feature set.
- Claude API MCP connector hiện có thể dùng **remote MCP tools** qua HTTP, nhưng không nên coi resources/prompts là guaranteed surface cho mọi deployment.

Kết luận thiết kế:
1. **Core path phải tool-first**.
2. **Remote HTTP là primary transport**.
3. **Local stdio bridge là companion hữu ích cho CLI-based agents**, nhưng không phải prerequisite để core memory hoạt động.

## 2. Two-server mental model
Recommended default setup:

### A. `viberecall-core`
Remote HTTP MCP server.
Cung cấp:
- memory write/read tools
- fact correction
- graph queries
- index orchestration
- optional resources/prompts

### B. `viberecall-bridge`
Optional local stdio helper.
Cung cấp:
- workspace snapshot/bundle helper
- local dirty worktree packaging
- optional helper resources about local workspace

Agent có thể cài cả hai servers cùng lúc.
Nếu không có bridge, core server vẫn dùng được cho memory/query với repo sources kiểu `git` hoặc bundle đã upload trước.

## 3. Why remote HTTP first
Remote HTTP giúp:
- cùng một hosted memory service phục vụ nhiều environments
- bearer token auth đơn giản
- Codex CLI/IDE và Claude Code đều cài được
- future owner/control-plane flows nhất quán hơn

Local stdio chỉ nên dùng cho:
- workspace helper
- local dev/testing
- cases cần truy cập local repo chưa push

## 4. Why tools first
Vì client capability khác nhau, server MUST giả định trường hợp xấu nhất là:
- client chỉ discover/call tools
- client không surface resources như UI picker
- client không surface prompts như slash commands
- remote API connector chỉ cho tool invocation

Do đó:
- `search_memory`, `get_context_pack`, `get_neighbors`, `explain_fact`, `index_repo` phải tự đủ dùng
- resources/prompts chỉ là UX accelerator

## 5. Codex-specific integration notes
### Config model
Codex thường dùng:
- global config
- project-scoped config cho trusted projects
- allow/deny tool lists
- bearer token env vars cho HTTP servers

### Practical recommendation
Với Codex:
- expose `viberecall-core` qua HTTP
- optionally expose `viberecall-bridge` qua stdio
- keep tool names short and specific
- rely on token-scoped tool discovery to reduce model confusion

### Good default tool subset for Codex everyday work
- `save_episode`
- `search_memory`
- `get_context_pack`
- `get_fact`
- `search_entities`
- `get_neighbors`
- `explain_fact`
- `get_index_status`

Index write và admin tools chỉ bật khi workflow thực sự cần.

## 6. Claude Code-specific integration notes
### Remote cloud usage
Với Claude Code, HTTP remote MCP server là đường chính đáng tin cậy nhất cho hosted service.

### Optional capabilities
Claude Code có thể tận dụng:
- resources cho entity/subgraph/context views
- prompts cho slash-command-like workflows
- tool search / managed MCP config

Nhưng core memory correctness vẫn phải nằm ở tools.

### Important consequence
Nếu user dùng Claude API path có MCP connector thay vì interactive Claude Code CLI/app, server phải vẫn usable khi chỉ có tool calls.
Vì vậy không được giấu critical functionality vào prompts/resources-only surface.

## 7. Local dirty workspace story
Đây là chỗ nhiều thiết kế sai.
Hosted core server không thấy local repo hiện tại của agent.
Cho nên khi agent đang sửa code local chưa push:
- local bridge hoặc helper đóng gói workspace bundle
- upload bundle
- gọi `index_repo(repo_source={type:"workspace_bundle",...})`

Không có chuyện agent đưa `/Users/alice/repo` cho cloud server rồi hy vọng server đọc được.

## 8. Recommended default agent playbook
### Start of task
1. `viberecall_get_context_pack`
2. if entity-centric task, `viberecall_search_entities`
3. if needed, `viberecall_get_neighbors`

### During investigation
- save meaningful observations via `viberecall_save_episode`
- refresh context only when task shifts materially

### Before large refactor
- check `viberecall_get_index_status`
- refresh or trigger indexing if stale
- inspect dependency neighborhood

### When correcting stale belief
- inspect with `viberecall_explain_fact`
- update with `viberecall_update_fact`

## 9. Installation profiles
### Profile A — read/write memory only
Safe daily driver.

### Profile B — memory + graph read
For deeper reasoning on dependencies and root causes.

### Profile C — memory + indexing
For trusted developer workflows.

### Profile D — admin
Owner/operator only.

## 10. Final rule
Design for the broadest compatibility surface first:
- remote HTTP
- bearer token
- tools
- bounded outputs
- minimal default tool set

Everything else is optional enhancement.
