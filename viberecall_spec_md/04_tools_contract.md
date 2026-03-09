# 04 — Tools Contract

## 1) Public MCP tools hiện tại
1. `viberecall_save`
2. `viberecall_search`
3. `viberecall_get_facts`
4. `viberecall_update_fact`
5. `viberecall_timeline`
6. `viberecall_get_status`
7. `viberecall_delete_episode`
8. `viberecall_index_repo`
9. `viberecall_index_status`
10. `viberecall_search_entities`
11. `viberecall_get_context_pack`

> Export, retention, purge, token lifecycle, và billing overview là control-plane HTTP workflows, không phải public MCP tools.

## 2) Output conventions
- Output luôn là text payload chứa JSON
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

## 3) Core memory tools

### 3.1 `viberecall_save`
Purpose:
- lưu episode với fast acknowledgement, sau đó enqueue ingest job

Input:
- `content` required
- `reference_time?`
- `metadata?`
- `idempotency_key?`

Result:
- `status = "ACCEPTED"`
- `episode_id`
- `ingested_at`
- `enrichment.mode = "ASYNC"`
- `enrichment.job_id`

### 3.2 `viberecall_search`
Purpose:
- search facts và merge recent raw episodes chưa enrich

Input:
- `query`
- `limit`
- `filters.reference_time_from/to`
- `filters.valid_at`
- `filters.as_of_ingest`
- `filters.tags`
- `filters.files`
- `filters.entity_types`
- `sort`
- `cursor`

Result:
- `results[]`
  - `kind = "fact"` với `fact`, `entities`, `provenance`, `score`
  - `kind = "episode"` với `episode`, `score`
- `next_cursor`

### 3.3 `viberecall_get_facts`
Purpose:
- list facts có filter + pagination

Input:
- `filters.entity_type?`
- `filters.tag?`
- `filters.valid_at?`
- `limit`
- `cursor`

Result:
- `facts[]`
- `next_cursor`

### 3.4 `viberecall_update_fact`
Purpose:
- apply temporal update mà không overwrite history

Input:
- `fact_id`
- `new_text`
- `effective_time`
- `reason?`

Result:
- `old_fact`
- `new_fact`
- `job_id`

### 3.5 `viberecall_timeline`
Purpose:
- list timeline episodes của project

Input:
- `from?`
- `to?`
- `limit`
- `cursor`

Result:
- `episodes[]`
- `next_cursor`

## 4) Runtime / maintenance memory tools

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

### 4.2 `viberecall_delete_episode`
Purpose:
- xóa một episode và cleanup artifacts liên quan

Input:
- `episode_id`

Result:
- `episode_id`
- `status = "DELETED" | "NOT_FOUND"`
- `deleted.postgres`
- `deleted.object_storage`
- `deleted.graph`

## 5) Code index & context tools

### 5.1 `viberecall_index_repo`
Purpose:
- queue một repo indexing run cho project

Input:
- `repo_path`
- `mode = "snapshot" | "diff"`
- `base_ref?`
- `head_ref?`
- `max_files?`

Result:
- `status = "ACCEPTED"`
- `index_id`
- `job_id`
- `project_id`
- `repo_path`
- `mode`
- `base_ref`
- `head_ref`
- `queued_at`

### 5.2 `viberecall_index_status`
Purpose:
- báo trạng thái indexing hiện tại

Result shape:
- `status = "EMPTY" | "QUEUED" | "RUNNING" | "FAILED" | "READY"`
- `project_id`
- `current`
- `latest_ready`

`current` có thể gồm:
- `index_id`
- `job_id`
- `repo_path`
- `mode`
- `effective_mode`
- `phase`
- `processed_files`
- `total_files`
- `scanned_files`
- `changed_files`
- `queued_at`
- `started_at`
- `completed_at`
- `error`
- `stats`

### 5.3 `viberecall_search_entities`
Purpose:
- search entities từ latest READY code index snapshot

Input:
- `query`
- `entity_types?`
- `limit?`

Result:
- `status = "READY" | "EMPTY"`
- `entities[]`
- `total`
- `indexed_at`

### 5.4 `viberecall_get_context_pack`
Purpose:
- tạo structured context pack cho agent workflows

Input:
- `query`
- `limit?`

Result:
- `status = "READY" | "EMPTY"`
- `query`
- `architecture_map`
- `relevant_symbols`
- `citations`
- `gaps`
- `facts_timeline`

`architecture_map` gồm:
- `indexed_at`
- `repo_path`
- `summary.file_count`
- `summary.symbol_count`
- `summary.entity_count`
- `summary.relationship_count`
- `summary.chunk_count`
- `top_modules`
- `top_files`

## 6) Compatibility policy
- Prefix `viberecall_*` là public contract ổn định
- Mở rộng tool surface theo kiểu backward-compatible
- Không hứa public compatibility cho internal control-plane routes hoặc DB row shape
