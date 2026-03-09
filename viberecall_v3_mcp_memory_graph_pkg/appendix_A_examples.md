---
title: Examples
status: informative
version: 3.0
---
# Appendix A — Examples

## 1. Save episode example
Tool call:
```json
{
  "name": "viberecall_save_episode",
  "arguments": {
    "episode_kind": "ARCHITECTURE_NOTE",
    "source_kind": "agent_note",
    "content": "Auth service depends on Redis for session lookup; token revocation must revalidate per request.",
    "metadata": {
      "task_id": "ENG-4521"
    }
  }
}
```

Result (shape):
```json
{
  "accepted": true,
  "episode_id": "ep_01...",
  "operation_id": "op_01...",
  "observation_doc_id": "doc_01...",
  "ingest_state": "PENDING"
}
```

## 2. Context pack example
```json
{
  "name": "viberecall_get_context_pack",
  "arguments": {
    "task": "Refactor session invalidation flow in auth service",
    "repo_scope": "services/auth",
    "budget_hint": "medium"
  }
}
```

## 3. Fact correction example
```json
{
  "name": "viberecall_update_fact",
  "arguments": {
    "fact_group_id": "fg_01...",
    "expected_current_version_id": "fv_old",
    "statement": "Auth service depends on Redis and Postgres for session invalidation metadata.",
    "subject_entity_id": "ent_auth_service",
    "relation_type_id": "depends_on",
    "object_entity_id": "ent_postgres"
  }
}
```

## 4. Codex config sketch
```toml
[mcp_servers.viberecall]
url = "https://memory.example.com/p/proj_123/mcp"
bearer_token_env_var = "VIBERECALL_TOKEN"
tool_timeout_sec = 45

[mcp_servers.viberecall_bridge]
command = "vr-bridge"
args = ["serve-mcp"]
enabled = true
```

## 5. Claude Code config sketch
```bash
claude mcp add --transport http viberecall https://memory.example.com/p/proj_123/mcp       --header "Authorization: Bearer $VIBERECALL_TOKEN"

claude mcp add viberecall-bridge -- vr-bridge serve-mcp
```

## 6. Resource URI examples
- `memory://project/proj_123/entity/ent_auth_service`
- `memory://project/proj_123/fact/fv_abc`
- `memory://project/proj_123/subgraph/ent_auth_service?depth=1`
