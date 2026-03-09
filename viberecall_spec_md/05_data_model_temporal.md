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
- `code_index_runs`
- `code_index_files`
- `code_index_entities`
- `code_index_chunks`

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
- enrichment status / summary fields trong persistence layer

Rule hiện tại:
- content nhỏ hơn hoặc bằng inline threshold -> lưu inline trong Postgres
- content lớn hơn threshold -> ghi vào object storage, Postgres giữ `content_ref`

## 3) Canonical graph model
Mặc dù runtime có nhiều adapter, contract logic giữ một graph model ổn định:
- `Episode`
- `Fact`
- `Entity`

Relationships canonical:
- `(Episode)-[:MENTIONS]->(Entity)`
- `(Episode)-[:SUPPORTS]->(Fact)`
- `(Fact)-[:ABOUT]->(Entity)`

Trong Graph Playground v1, UI graph còn materialize quan hệ `CO_OCCURS` từ fact/entity evidence để phục vụ visualization.

## 4) Temporal semantics
- `reference_time`: khi sự kiện thực sự xảy ra
- `ingested_at`: khi server ghi nhận vào hệ thống
- `valid_at` / `invalid_at`: lifespan của fact trong knowledge model

Update fact luôn theo rule:
- set `old_fact.invalid_at = effective_time`
- create `new_fact.valid_at = effective_time`
- không overwrite lịch sử

## 5) Query semantics
- `reference_time_from/to`: lọc theo event time
- `valid_at`: knowledge đúng tại thời điểm đó
- `as_of_ingest`: chỉ nhìn thấy knowledge đã được ingest trước thời điểm đó
- search có thể trả cả `fact` và `recent raw episode`

## 6) Code index snapshot model
Code indexing hiện không còn là file-state cục bộ. Nguồn dữ liệu chuẩn là:
- `code_index_runs`: lifecycle của mỗi index run
- `code_index_files`: file rows đã materialize
- `code_index_entities`: File / Module / Symbol / Import entities
- `code_index_chunks`: snippets phục vụ context retrieval

Reading policy:
- `search_entities` và `get_context_pack` chỉ đọc từ latest `READY` snapshot
- active run (`QUEUED` / `RUNNING`) không thay thế latest ready cho read-path

## 7) IDs và provenance
- `episode_id`, `fact_id`, `entity_id`, `index_id`, `export_id` đều là stable identifiers
- facts giữ provenance để truy lại episode source
- delete episode path phải cleanup Postgres + object storage + graph state một cách nhất quán

## 8) Purge / retention semantics
- retention chạy như maintenance job
- purge project xóa graph state, episodes, exports, usage/webhook artifacts liên quan
- logs có thể bị scrub ở mức sensitive content thay vì drop toàn bộ mọi audit evidence
