---
title: Data Model and Source of Truth
status: normative
version: 3.0
---
# 05 — Data Model and Source of Truth

## 1. Core principle
**Postgres là source of truth duy nhất** cho domain semantics của memory graph.

Graph backend, caches, search projections, embeddings, summaries đều là **derived state**.

## 2. Canonical object classes
- `projects`
- `tokens`
- `episodes`
- `entities`
- `entity_aliases`
- `relation_types`
- `fact_groups`
- `fact_versions`
- `provenance_links`
- `episode_mentions`
- `operations`
- `outbox_events`
- `memory_search_docs`
- `usage_events`
- `audit_logs`
- `code_index_*`
- `projection_watermarks`

## 3. Episodes
Episode = raw observation bất biến về mặt nội dung người dùng đã submit.
Fields quan trọng:
- `episode_id`
- `project_id`
- `episode_kind`
- `recorded_at`
- `reference_time`
- `source_kind`
- `content_inline`
- `content_ref`
- `content_sha256`
- `metadata_json`
- `visibility_state`
- `ingest_state`
- `trust_class`

Ví dụ `episode_kind`:
- `TASK_NOTE`
- `DEBUG_LOG`
- `INCIDENT_NOTE`
- `ARCHITECTURE_NOTE`
- `CODE_DIFF_SUMMARY`
- `TICKET_SUMMARY`
- `TEST_FAILURE`
- `USER_PREFERENCE`

## 4. Entities
Entity là identity canonical.
Mỗi row có:
- `entity_id`
- `project_id`
- `entity_kind`
- `canonical_name`
- `display_name`
- `state`
- `metadata_json`
- `created_at`
- `updated_at`

`entity_kind` ban đầu SHOULD bao gồm:
- `REPO`
- `DIRECTORY`
- `FILE`
- `MODULE`
- `PACKAGE`
- `CLASS`
- `INTERFACE`
- `FUNCTION`
- `METHOD`
- `SERVICE`
- `DATABASE`
- `QUEUE`
- `API`
- `FEATURE_FLAG`
- `ENVIRONMENT`
- `TICKET`
- `PR`
- `COMMIT`
- `INCIDENT`
- `TEST_CASE`
- `ERROR_SIGNATURE`
- `PERSON`
- `TEAM`
- `DECISION`
- `TASK`

## 5. Entity aliases
Không dùng path/name làm primary identity.
`entity_aliases` giữ:
- textual aliases
- old file paths
- old symbol FQNs
- git hashes or external ids
- source and confidence

## 6. Relation types
`relation_types` là catalog được kiểm soát, không free-form uncontrolled.
Mỗi relation type có:
- `relation_type_id`
- `name`
- `inverse_name`
- `subject_kind_constraints`
- `object_kind_constraints`
- `is_transitive`
- `source_class`
- `status`

## 7. Fact groups và fact versions
Logical identity nằm ở `fact_groups`.
Version history nằm ở `fact_versions`.

Mỗi `fact_version` SHOULD có:
- `fact_version_id`
- `fact_group_id`
- `project_id`
- `fact_shape` = `EDGE | ATTRIBUTE | SUMMARY`
- `subject_entity_id`
- `relation_type_id`
- `object_entity_id` nullable
- `value_json` nullable
- `statement`
- `normalized_statement`
- `valid_from`
- `valid_to`
- `recorded_at`
- `superseded_at`
- `status`
- `confidence`
- `salience_score`
- `trust_class`
- `created_from_episode_id`
- `replaces_fact_version_id`
- `metadata_json`

### Interpretation
- EDGE: `subject --relation--> object`
- ATTRIBUTE: `subject --relation--> value_json`
- SUMMARY: synthetic roll-up fact with explicit provenance to multiple sources

## 8. Provenance model
`provenance_links` phải nối được:
- fact -> source episode(s)
- fact -> generating operation
- fact -> extraction pipeline version
- entity resolution decisions

Query “why does system believe this?” phải đi qua provenance links được.

## 9. Search projections
`memory_search_docs` là canonical read projection cho search-like flows.
`doc_kind` nên gồm:
- `EPISODE_OBSERVATION`
- `FACT_VERSION`
- `ENTITY_PROFILE`
- `SUMMARY`

Mỗi doc có:
- `source_id`
- `project_id`
- `doc_kind`
- `title`
- `body`
- `filters_json`
- `rank_features_json`
- `tsv`
- optional vector columns
- `visible_from_watermark`
- `hidden_at_watermark`

## 10. Temporal semantics
Hệ thống phải hỗ trợ:
- **valid time**: fact đúng trong thế giới khi nào
- **record time**: hệ thống biết fact này từ lúc nào

Query semantics:
- “current” = `status = CURRENT and superseded_at is null`
- “as of system time T” dùng recorded/superseded boundaries
- “valid at T” dùng valid_from/valid_to boundaries

## 11. Code index canonical model
Canonical tables:
- `code_index_runs`
- `code_index_snapshots`
- `code_index_snapshot_heads`
- `code_index_files`
- `code_index_symbols`
- `code_index_edges`
- `code_index_chunks`

Read path chỉ đọc snapshot đang là latest `READY`.

## 12. Optional graph projection
Nếu có graph backend:
- nodes mirror `entities` and `fact_versions` as projection artifacts
- edges derived from current/candidate fact versions and code index edges
- projection failures không làm mất canonical truth

## 13. Hard invariants
1. Không có fact canonical nào chỉ nằm trong graph projection.
2. Không có 2 current fact versions trong cùng fact group.
3. Không có entity redirect loop.
4. Không có search doc visible mà source object đã hard-delete vô cớ.
5. Project isolation phải được enforce bằng FK + predicates + tests.
