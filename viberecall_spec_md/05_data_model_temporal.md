# 05 — Data Model & Temporal Semantics

## 1) Postgres là nguồn dữ liệu quan hệ chuẩn
Các nhóm bảng chính:
- `projects`
- `mcp_tokens`
- `episodes`
- `usage_events`
- `audit_logs`
- `exports`
- `webhooks`
- `operations`
- `outbox_events`
- `working_memory`
- `code_index_runs`
- `code_index_files`
- `code_index_entities`
- `code_index_chunks`
- `entities`
- `entity_aliases`
- `entity_redirects`
- `entity_resolution_events`
- `unresolved_mentions`
- `relation_types`
- `fact_groups`
- `fact_versions`
- `provenance_links`
- `memory_search_docs`
- `projection_watermarks`

`projects.isolation_mode` hiện dùng default `falkordb_graph`.

## 2) Episode storage
Episode lưu:
- `episode_id`
- `project_id`
- `reference_time`
- `ingested_at`
- `content`
- `content_ref`
- `metadata`
- salience/read-through fields trong canonical layer

Rule hiện tại:
- content nhỏ hơn hoặc bằng inline threshold -> lưu inline trong Postgres
- content lớn hơn threshold -> ghi vào object storage, Postgres giữ `content_ref`

## 3) Canonical memory model
Contract logic giữ một graph/memory model ổn định:
- `Episode`
- `Fact`
- `Entity`

Canonical relational support:
- `fact_groups` nhóm identity của fact
- `fact_versions` giữ temporal history của fact
- `provenance_links` nối fact/entity/episode evidence
- `memory_search_docs` materialize canonical search surface

Relationships canonical:
- `(Episode)-[:MENTIONS]->(Entity)`
- `(Episode)-[:SUPPORTS]->(Fact)`
- `(Fact)-[:ABOUT]->(Entity)`

Trong Graph Playground v1, UI graph còn materialize quan hệ `CO_OCCURS` từ fact/entity evidence để phục vụ visualization.

## 4) Entity resolution model
Entity resolution foundation hiện dùng ba nhóm bảng:
- `entity_resolution_events`
  - audit trail canonical cho `MERGE` và `SPLIT`
- `entity_redirects`
  - source entity đã redirect sang canonical target nào
- `unresolved_mentions`
  - backlog row cho mention chưa resolve dứt điểm

`unresolved_mentions` semantics:
- identity dedupe theo `project_id + normalized mention_text + observed_kind + repo_scope`
- chỉ một row `OPEN` cho mỗi identity
- `viberecall_resolve_reference` sẽ create/reuse row `OPEN` khi `AMBIGUOUS | NO_MATCH`
- clean resolution sau đó sẽ chuyển row đang `OPEN` sang `RESOLVED`

Merge/split semantics:
- `merge_entities` tạo resolution event + redirect rows + alias/fact/provenance rebinding
- `split_entity` tạo resolution event + explicit alias/fact reassignment tới target entities

## 5) Salience model
Canonical salience hiện là first-class row state:
- facts, entities, episodes đều có `salience_score` và `salience_class`
- manual overrides được giữ trong metadata
- `PIN`, `UNPIN`, `DEMOTE` là canonical actions qua `viberecall_pin_memory`

Search semantics:
- `search_memory` boost theo salience nhưng vẫn ưu tiên exact lexical match
- `search_entities` có thể boost/filter theo entity salience
- `get_context_pack` ưu tiên evidence có salience cao hơn

## 6) Temporal semantics
- `reference_time`: khi sự kiện thực sự xảy ra
- `ingested_at`: khi server ghi nhận vào hệ thống
- `valid_at` / `invalid_at`: lifespan của fact trong knowledge model
- `as_of_system_time`: snapshot read cho một số graph-read surfaces

Update fact luôn theo rule:
- set `old_fact.invalid_at = effective_time`
- create `new_fact.valid_at = effective_time`
- không overwrite lịch sử

## 7) Query semantics
- `reference_time_from/to`: lọc theo event time
- `valid_at`: knowledge đúng tại thời điểm đó
- `as_of_ingest`: chỉ nhìn thấy knowledge đã được ingest trước thời điểm đó
- `search_memory` có thể trả cả `fact` và `episode`
- `get_neighbors` hiện intentionally bounded ở `depth=1`
- `find_paths` dùng bounded recursive SQL, default `max_depth=2`, hard max `3`

## 8) Code index snapshot model
Code indexing không còn là file-state cục bộ. Nguồn dữ liệu chuẩn là:
- `code_index_runs`: lifecycle của mỗi index run
- `code_index_files`: file rows đã materialize
- `code_index_entities`: File / Module / Symbol / Import entities
- `code_index_chunks`: snippets phục vụ context retrieval

Reading policy:
- `search_entities` canonical đọc từ memory tables, không còn là code-index-only surface
- `resolve_reference` và `get_context_pack` có thể augment bằng latest `READY` index khi phù hợp
- active run (`QUEUED` / `RUNNING`) không thay thế latest ready cho read-path

## 9) Operations / async semantics
- `operations` là canonical async-operation state
- `outbox_events` là durable dispatch queue cho reprojection / async follow-up work
- `get_operation` là read surface để polling progress/result

## 10) IDs và provenance
- `episode_id`, `fact_group_id`, `fact_version_id`, `entity_id`, `index_run_id`, `operation_id`, `export_id` đều là stable identifiers
- facts giữ provenance để truy lại episode source
- delete episode path phải cleanup Postgres + object storage + graph state một cách nhất quán

## 11) Purge / retention semantics
- retention chạy như maintenance job
- purge project xóa graph state, episodes, exports, usage/webhook artifacts liên quan
- logs có thể bị scrub ở mức sensitive content thay vì drop toàn bộ mọi audit evidence
