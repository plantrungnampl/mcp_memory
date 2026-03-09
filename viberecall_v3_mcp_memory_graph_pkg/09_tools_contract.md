---
title: Public Tools Contract
status: normative
version: 3.0
---
# 09 — Public Tools Contract

## 1. Tool design principles
1. Tool names MUST be stable.
2. Tool outputs SHOULD have `structuredContent`.
3. Descriptions must be concise and specific for tool selection by models.
4. Large outputs must return ids / resource links rather than full blobs.
5. Tools listed to a token MUST already respect scope restrictions.

## 2. Core tool set
| Tool | Purpose | Sync/Async | Scope |
|---|---|---|---|
| `viberecall_save_episode` | store raw observation | async enrich | `memory:write` |
| `viberecall_search_memory` | grouped retrieval | sync | `memory:read` |
| `viberecall_get_context_pack` | task-oriented retrieval | sync | `memory:read` |
| `viberecall_get_operation` | poll async status | sync | `ops:read` or underlying scope |
| `viberecall_get_fact` | fetch fact lineage | sync | `memory:read` |
| `viberecall_update_fact` | transactional correction | sync | `facts:write` |
| `viberecall_search_entities` | find entities | sync | `entities:read` |
| `viberecall_get_neighbors` | bounded neighborhood query | sync | `graph:read` |
| `viberecall_find_paths` | bounded path search | sync | `graph:read` |
| `viberecall_explain_fact` | provenance/lineage | sync | `memory:read` |
| `viberecall_pin_memory` | pin/demote salience | sync | `facts:write` |
| `viberecall_index_repo` | start index run | async | `codeindex:write` |
| `viberecall_get_index_status` | inspect latest/operation | sync | `codeindex:read` |

## 3. Privileged tools
Chỉ lộ khi token có scope tương ứng:
- `viberecall_merge_entities`
- `viberecall_split_entity`
- `viberecall_delete_episode`
- `viberecall_export_project`
- `viberecall_get_status`

## 4. Detailed semantics

### 4.1 `viberecall_save_episode`
Input:
- `content`
- `episode_kind`
- `reference_time` optional
- `source_kind`
- `metadata` optional
- `idempotency_key` optional

Response:
- `accepted: true`
- `episode_id`
- `operation_id`
- `observation_doc_id`
- `ingest_state = PENDING`

Notes:
- synchronous guarantee chỉ là canonical raw save committed
- derived facts/entities come later

### 4.2 `viberecall_search_memory`
Input:
- `query`
- filters (`entity_kinds`, `relation_types`, `current_only`, `repo_scope`, `valid_at`, `as_of_system_time`, `salience_classes`, `trust_classes`)
- `cursor`
- `snapshot_token`
- `limit`

Response groups:
- `facts[]`
- `entities[]`
- `episodes[]`
- `summaries[]`
- `next_cursor`
- `snapshot_token`

### 4.3 `viberecall_get_context_pack`
Input:
- `task`
- `repo_scope` optional
- `budget_hint`
- `include_recent_episodes` boolean
- `include_graph_expansion` boolean

Response:
- `current_facts[]`
- `key_entities[]`
- `recent_observations[]`
- `open_conflicts[]`
- `suggested_followups[]`
- `snapshot_token`

### 4.4 `viberecall_get_operation`
Input:
- `operation_id`

Response:
- `status`
- `operation_type`
- `created_at`
- `updated_at`
- `result`
- `retryable`
- `current_step` optional

### 4.5 `viberecall_get_fact`
Input:
- one of `fact_version_id` or `fact_group_id`
- optional temporal selector

Response:
- current version
- lineage summary
- supporting provenance
- related entities

### 4.6 `viberecall_update_fact`
Input:
- `fact_group_id`
- `expected_current_version_id`
- replacement fields (`statement`, `subject_entity_id`, `relation_type_id`, `object_entity_id` or `value_json`, temporal fields, metadata)

Response:
- `old_fact_version_id`
- `new_fact_version_id`
- `fact_group_id`
- `committed_at`

Semantics:
- transactional CAS
- reject if expected current version mismatch

### 4.7 `viberecall_search_entities`
Input:
- `query`
- `entity_kinds[]`
- `repo_scope`
- `limit`

Response:
- `entities[]` with aliases, salience, summary snippets

### 4.8 `viberecall_get_neighbors`
Input:
- `entity_id`
- `direction`
- `relation_types[]`
- `depth`
- temporal selectors
- `limit`

Response:
- `anchor`
- `neighbors[]`
- `edges[]`
- `truncated`

### 4.9 `viberecall_find_paths`
Input:
- `src_entity_id`
- `dst_entity_id`
- `relation_types[]`
- `max_depth`
- temporal selectors
- `limit_paths`

Response:
- `paths[]`
- `truncated`
- `search_metadata`

### 4.10 `viberecall_explain_fact`
Input:
- `fact_version_id`

Response:
- `fact`
- `lineage`
- `supporting_episodes`
- `extraction_details`
- `confidence_breakdown`

### 4.11 `viberecall_pin_memory`
Input:
- `target_kind = FACT | ENTITY | EPISODE`
- `target_id`
- `pin_action = PIN | UNPIN | DEMOTE`
- `reason` optional

Response:
- updated salience state

### 4.12 `viberecall_index_repo`
Input:
- `repo_source`
  - `type = git | workspace_bundle`
  - `git`: `remote_url`, `ref`, `credential_ref?`
  - `workspace_bundle`: `bundle_ref`, `base_commit?`, `repo_name?`
- `mode = FULL_SNAPSHOT`
- `idempotency_key` optional

Response:
- `accepted: true`
- `index_run_id`
- `operation_id`

### 4.13 `viberecall_get_index_status`
Input:
- optional `index_run_id`
- else latest for project

Response:
- `latest_ready_snapshot`
- `current_run`
- `status`
- `stats`

## 5. Privileged tool semantics
### `viberecall_merge_entities`
Merge source entities into canonical target; must preserve redirect/audit.

### `viberecall_split_entity`
Split a wrongly merged entity; high-risk privileged tool.

### `viberecall_delete_episode`
Mark deletion saga; does not claim synchronous hard delete across all stores.

### `viberecall_export_project`
Start export build operation.

### `viberecall_get_status`
Limited operational status; owner/operator only.

## 6. Output schema policy
Mỗi tool SHOULD define `outputSchema`.
Minimal policy:
- ids are explicit strings
- timestamps ISO-8601 UTC
- enums documented
- booleans for `retryable`, `truncated`, `accepted`

## 7. Tool count discipline
Đừng expose full privileged toolset cho everyday coding agent tokens.
Tool discovery SHOULD be minimized per token to reduce model confusion.

## 8. Resource links
Tools MAY return resource links for:
- entity profiles
- subgraphs
- context packs
- latest index manifest

Nhưng core semantics không phụ thuộc client phải read resource.
