# 05 — Data Model (Temporal / Bi-temporal / Provenance)

## 1) Metadata DB (Postgres)
Tables (minimal):
- `users`
- `projects` (id, name, owner_id, plan, retention_days, created_at, isolation_mode)
- `mcp_tokens` (token_hash, prefix, project_id, scopes, revoked_at, last_used_at)
- `usage_events` (project_id, token_id, tool, provider, model, in_tokens, out_tokens, vibe_tokens, ts)
- `usage_rollups_daily/monthly`
- `audit_logs` (project_id, token_id, action, args_hash, ts, status)
- `exports` (export_id, project_id, status, object_url, expires_at)
- `webhooks` (optional)

## 2) Raw episode storage
- MVP: store in Postgres (content column)
- Scale: store content in object storage (S3/R2), Postgres giữ pointer + metadata

Episode fields:
- `episode_id`
- `project_id`
- `reference_time` (event time; optional)
- `ingested_at` (transaction time; server set)
- `content` / `object_ref`
- `metadata` JSON

## 3) Graph DB model (Neo4j per-project database)
Core objects:
- Entities (nodes)
- Facts (nodes)
- Provenance links fact ↔ episode(s)


### Canonical schema (v0.1 — cố định)
Facts là **nodes** (label `:Fact`), không phải edge.

- `(:Episode {episode_id, project_id, reference_time, ingested_at, content_ref, metadata_json})`
- `(:Entity {entity_id, type, name, aliases})`
- `(:Fact {fact_id, text, valid_at, invalid_at, ingested_at, confidence})`

Relationships:
- `(Episode)-[:MENTIONS]->(Entity)`
- `(Episode)-[:SUPPORTS]->(Fact)`
- `(Fact)-[:ABOUT]->(Entity)`

Temporal update rule (bắt buộc):
- Update = set `old_fact.invalid_at = effective_time` + create `new_fact.valid_at = effective_time`
- Không overwrite history.


Temporal semantics:
- `valid_at` / `invalid_at` trên facts
- Update = invalidate old at `effective_time` + create new

## 4) Query semantics
- `reference_time_range`: lọc theo lúc sự kiện xảy ra
- `valid_at=T`: facts đúng tại thời điểm T
- `as_of_ingest=T`: knowledge ingested đến T

## 5) IDs
- Stable IDs: `episode_id`, `fact_id`, `entity_id`
- Khi export/import phải preserve IDs (hoặc có strategy remap)


## 6) Storage strategy (chốt cứng v0.1)

### 6.1 Raw episode storage rule
- Nếu `len(content) <= 64KB`: lưu **inline** trong Postgres.
- Nếu `len(content) > 64KB`: lưu vào object storage (S3/R2) theo key:
  - `projects/{project_id}/episodes/{episode_id}.txt`
  - Postgres chỉ giữ `content_ref`.

### 6.2 Migration rule (khi scale)
- Background job `migrate_inline_to_object`:
  - move inline content → object storage
  - set `content_ref`, clear inline content
- Trigger:
  - khi DB size vượt ngưỡng (ví dụ 20GB) hoặc theo retention policy.

### 6.3 Retention & purge
- Retention job chạy theo `retention_days`:
  - delete Postgres rows + delete object keys theo prefix `projects/{project_id}/...`
- Purge project:
  - drop Neo4j database
  - delete all object keys của project
  - delete exports + scrub logs content (giữ hashes)

