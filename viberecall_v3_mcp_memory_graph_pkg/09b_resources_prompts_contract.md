---
title: Resources and Prompts Contract
status: normative
version: 3.0
---
# 09b — Resources and Prompts Contract

## 1. Why these are optional
MCP spec cho phép resources và prompts, nhưng client support không đồng đều.
Vì vậy:
- core product MUST work with tools only
- resources/prompts SHOULD enrich experience where clients support them

## 2. Resources capability
Nếu bật, server SHOULD support:
- `resources/list`
- `resources/read`
- optional `listChanged`
- no mandatory subscription support in v1

## 3. Recommended resource URIs
- `memory://project/{project_id}/entity/{entity_id}`
- `memory://project/{project_id}/fact/{fact_version_id}`
- `memory://project/{project_id}/fact-group/{fact_group_id}`
- `memory://project/{project_id}/episode/{episode_id}`
- `memory://project/{project_id}/context-pack/{context_pack_id}`
- `memory://project/{project_id}/subgraph/{entity_id}?depth=1`
- `memory://project/{project_id}/index/latest`
- `memory://project/{project_id}/index/run/{index_run_id}`

## 4. Resource read semantics
Resource payload SHOULD be concise and structured.
Không dùng resources như blob dump vô hạn.
Nếu content lớn, resource nên trả:
- summary
- metadata
- links/ids để fetch tiếp qua privileged channel nếu cần

## 5. Entity resource
SHOULD include:
- canonical metadata
- aliases
- top relations
- current fact summaries
- provenance highlights

## 6. Subgraph resource
SHOULD be bounded:
- one anchor
- max depth small
- node/edge cap
- trust/confidence labels

## 7. Prompts capability
Prompts là user-invoked templates. Nếu bật, nên có:
- `memory.capture_handoff`
- `memory.fetch_context_for_task`
- `memory.explain_entity`
- `memory.review_conflicts`
- `memory.prepare_refactor_context`

## 8. Prompt design rules
- prompts MUST not bypass authz
- prompt output should naturally instruct client/model to use tools
- prompt should remain deterministic enough for UX
- prompt definitions must not contain secrets

## 9. Example prompt purposes
### `memory.capture_handoff`
Yêu cầu model tóm tắt current task into structured episode candidate.

### `memory.fetch_context_for_task`
Yêu cầu model dùng `get_context_pack`, có thể follow-up `get_neighbors`.

### `memory.review_conflicts`
Yêu cầu model inspect conflicting facts before correction.

## 10. Compatibility rule
Any valuable capability provided through a prompt SHOULD also be achievable via direct tool calling, vì không phải client nào cũng surface prompts như slash commands.

## 11. Tool-resource interplay
Tool results MAY include `resource_link` items.
Ví dụ:
- `search_memory` returns a resource link to a generated subgraph
- `get_context_pack` returns a resource link to cached pack summary

## 12. Caching
Generated resources like context packs MAY be cached briefly, but cache invalidation must respect projection watermarks and token/project isolation.
