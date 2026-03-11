# 04 — Tools Contract

## 1) Public MCP tools hiện tại
Current runtime exposes **25** public `viberecall_*` tools:

1. `viberecall_save_episode`
2. `viberecall_save`
3. `viberecall_search_memory`
4. `viberecall_search`
5. `viberecall_get_fact`
6. `viberecall_get_facts`
7. `viberecall_update_fact`
8. `viberecall_pin_memory`
9. `viberecall_timeline`
10. `viberecall_get_status`
11. `viberecall_delete_episode`
12. `viberecall_get_operation`
13. `viberecall_index_repo`
14. `viberecall_get_index_status`
15. `viberecall_index_status`
16. `viberecall_search_entities`
17. `viberecall_get_neighbors`
18. `viberecall_find_paths`
19. `viberecall_explain_fact`
20. `viberecall_resolve_reference`
21. `viberecall_merge_entities`
22. `viberecall_split_entity`
23. `viberecall_get_context_pack`
24. `viberecall_working_memory_get`
25. `viberecall_working_memory_patch`

> Export, retention, purge, token lifecycle, billing overview, và graph-control-plane routes vẫn là owner-scoped HTTP workflows, không phải public MCP tools.

## 2) Output conventions
- Output luôn là text payload chứa JSON.
- Envelope chuẩn:

```json
{
  "output_version": "1.0",
  "ok": true,
  "result": {},
  "error": null,
  "request_id": "req_..."
}
```

Khi lỗi:
- `ok = false`
- `result = null`
- `error = { code, message, details }`

## 3) Canonical memory tools

### 3.1 `viberecall_save_episode`
Purpose:
- lưu raw observation canonical, enqueue enrichment async, và trả ACK nhanh

Input:
- `content` required
- `episode_kind?`
- `source_kind?`
- `reference_time?`
- `metadata?`
- `idempotency_key?`

Result:
- `status = "ACCEPTED"`
- `episode_id`
- `enrichment.mode = "ASYNC"`
- `enrichment.job_id`

### 3.2 `viberecall_save`
Purpose:
- legacy wrapper cho `viberecall_save_episode`

### 3.3 `viberecall_search_memory`
Purpose:
- search canonical facts + episodes trên Postgres canonical memory

Input:
- `query`
- `limit`
- `filters.reference_time_from/to`
- `filters.valid_at`
- `filters.as_of_ingest`
- `filters.tags`
- `filters.files`
- `filters.entity_types`
- `filters.salience_classes`
- `sort`
- `cursor`
- `snapshot_token`
- `memory_scope`

Result:
- `results[]`
  - `kind = "fact"` với `fact`, `entities`, `provenance`, `summary`, `score`
  - `kind = "episode"` với `episode`, `score`
- `facts[]`, `entities[]`, `episodes[]`, `summaries[]` khi caller cần grouped surfaces
- `next_cursor`
- `snapshot_token`

### 3.4 `viberecall_search`
Purpose:
- legacy wrapper cho canonical memory search

### 3.5 `viberecall_get_fact`
Purpose:
- lấy một canonical fact theo `fact_version_id` hoặc `fact_group_id`, kèm lineage/provenance

### 3.6 `viberecall_get_facts`
Purpose:
- list canonical facts có filter + pagination

Input:
- `filters.entity_type?`
- `filters.tag?`
- `filters.valid_at?`
- `limit`
- `cursor`

Result:
- `facts[]`
- `next_cursor`

### 3.7 `viberecall_update_fact`
Purpose:
- apply temporal update mà không overwrite history

Input:
- `fact_id | fact_group_id | fact_version_id`
- `statement | new_text`
- `effective_time`
- `reason?`

Result:
- `status = "ACCEPTED"`
- `fact_group_id`
- `previous_version_id`
- `current_version_id`
- `operation_id`

### 3.8 `viberecall_pin_memory`
Purpose:
- manual salience override cho fact, entity, hoặc episode

Input:
- `target_kind = "fact" | "entity" | "episode"`
- `target_id`
- `pin_action = "PIN" | "UNPIN" | "DEMOTE"`
- `reason?`

Result:
- `target_kind`
- `target_id`
- `salience_score`
- `salience_class`
- `manual_override`

### 3.9 `viberecall_timeline`
Purpose:
- list timeline episodes của project

### 3.10 `viberecall_delete_episode`
Purpose:
- xóa một episode và cleanup artifacts canonical/object/graph liên quan

### 3.11 `viberecall_get_operation`
Purpose:
- đọc trạng thái canonical async operation/outbox-backed operation

Result:
- `operation`
- `outbox_events[]`

## 4) Runtime / indexing / context tools

### 4.1 `viberecall_get_status`
Purpose:
- trả trạng thái runtime và dependency checks cho project hiện tại

Result:
- `status`
- `service`
- `project_id`
- `backends.memory_backend`
- `backends.kv_backend`
- `backends.queue_backend`
- `graphiti.enabled`
- `graphiti.bridge_mode`
- `graphiti.detail`

### 4.2 `viberecall_index_repo`
Purpose:
- queue một repo indexing run strict-v3 cho project

Input:
- `repo_source`
  - `type = "git" | "workspace_bundle"`
  - `remote_url?`, `ref?`, `base_commit?`, `repo_name?`, `bundle_ref?`, `credential_ref?`
- `mode = "FULL_SNAPSHOT"`
- `max_files?`
- `idempotency_key?`

Result:
- `status = "ACCEPTED"`
- `index_run_id`
- `operation_id`
- `project_id`

### 4.3 `viberecall_get_index_status`
Purpose:
- báo trạng thái canonical indexing hiện tại

Result:
- `status = "EMPTY" | "QUEUED" | "RUNNING" | "FAILED" | "READY"`
- `project_id`
- `current`
- `latest_ready`

### 4.4 `viberecall_index_status`
Purpose:
- legacy wrapper cho `viberecall_get_index_status`

### 4.5 `viberecall_get_context_pack`
Purpose:
- tạo structured context pack cho agent workflows

Input:
- `query`
- `limit?`
- `memory_scope?`
- `task_id?`
- `session_id?`

Result:
- `status = "READY" | "EMPTY"`
- `query`
- `architecture_map`
- `citations`
- `recent_episodes`
- `facts_timeline`
- `seeds`

## 5) Graph / entity resolution tools

### 5.1 `viberecall_search_entities`
Purpose:
- search canonical entities từ Postgres memory tables, không còn phụ thuộc trực tiếp vào code-index snapshot cũ

Input:
- `query`
- `entity_types?`
- `entity_kinds?`
- `salience_classes?`
- `limit?`
- `repo_scope?`

Result:
- `status = "READY"`
- `entities[]`
- `total`

### 5.2 `viberecall_get_neighbors`
Purpose:
- trả neighborhood depth-1 quanh một canonical entity

### 5.3 `viberecall_find_paths`
Purpose:
- bounded path search giữa hai canonical entities bằng recursive SQL

### 5.4 `viberecall_explain_fact`
Purpose:
- giải thích canonical fact version với lineage, provenance, và supporting episodes

### 5.5 `viberecall_resolve_reference`
Purpose:
- resolve một mention vào canonical entity, có thể augment bằng latest READY code index

Input:
- `mention_text`
- `observed_kind?`
- `repo_scope?`
- `include_code_index?`
- `limit?`

Result:
- `status = "RESOLVED" | "AMBIGUOUS" | "NO_MATCH"`
- `best_match`
- `candidates[]`
- `needs_disambiguation`
- `latest_ready_index`
- `unresolved_mention`

`unresolved_mention` semantics:
- `null` nếu không có backlog row cần trả về
- `{ mention_id, status = "OPEN" }` khi ambiguous/no-match reuse hoặc create một unresolved row
- `{ mention_id, status = "RESOLVED" }` khi một row OPEN trước đó được đóng lại bởi clean resolution

### 5.6 `viberecall_merge_entities`
Purpose:
- privileged canonical merge tạo redirect + resolution event + async projection reconciliation

Input:
- `target_entity_id`
- `source_entity_ids[]`
- `reason?`

Result:
- `status = "ACCEPTED"`
- `operation_id`
- `resolution_event_id`
- `canonical_target_entity_id`

### 5.7 `viberecall_split_entity`
Purpose:
- privileged canonical split với explicit alias/fact rebinding instructions

Input:
- `source_entity_id`
- `partitions[]`
- `reason?`

Result:
- `status = "ACCEPTED"`
- `operation_id`
- `resolution_event_id`
- `target_entity_ids[]`

## 6) Working memory tools

### 6.1 `viberecall_working_memory_get`
Purpose:
- đọc persisted working-memory state cho `session_id + task_id`

### 6.2 `viberecall_working_memory_patch`
Purpose:
- patch persisted working-memory state với checkpoint note và optional expiry

## 7) Compatibility policy
- Prefix `viberecall_*` là public contract ổn định.
- Legacy wrappers (`save`, `search`, `index_status`) vẫn giữ để không phá client cũ.
- Mở rộng tool surface theo kiểu backward-compatible.
- Không hứa public compatibility cho internal control-plane routes, DB row shape, hay private handler module layout.
