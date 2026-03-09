---
title: Schema Sketch
status: informative
version: 3.0
---
# Appendix D — Schema Sketch

Đây là schema sketch implementation-oriented, không phải DDL cuối cùng.

## `entities`
```sql
entities(
  entity_id text primary key,
  project_id text not null,
  entity_kind text not null,
  canonical_name text not null,
  display_name text not null,
  state text not null default 'ACTIVE',
  metadata_json jsonb not null default '{}',
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

## `entity_aliases`
```sql
entity_aliases(
  alias_id bigserial primary key,
  project_id text not null,
  entity_id text not null,
  alias_type text not null,
  alias_value text not null,
  confidence numeric null,
  active boolean not null default true,
  created_at timestamptz not null
);
```

## `relation_types`
```sql
relation_types(
  relation_type_id text primary key,
  name text unique not null,
  inverse_name text not null,
  relation_class text not null,
  is_transitive boolean not null default false,
  metadata_json jsonb not null default '{}',
  created_at timestamptz not null
);
```

## `fact_groups`
```sql
fact_groups(
  fact_group_id text primary key,
  project_id text not null,
  current_fact_version_id text null,
  natural_key_hash text null,
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

## `fact_versions`
```sql
fact_versions(
  fact_version_id text primary key,
  fact_group_id text not null,
  project_id text not null,
  fact_shape text not null,
  subject_entity_id text not null,
  relation_type_id text not null,
  object_entity_id text null,
  value_json jsonb null,
  statement text not null,
  normalized_statement text not null,
  valid_from timestamptz null,
  valid_to timestamptz null,
  recorded_at timestamptz not null,
  superseded_at timestamptz null,
  status text not null,
  confidence numeric null,
  salience_score numeric null,
  trust_class text not null,
  created_from_episode_id text null,
  replaces_fact_version_id text null,
  metadata_json jsonb not null default '{}'
);
```

Important constraints:
- partial unique index `(fact_group_id)` where `status='CURRENT' and superseded_at is null`

## `provenance_links`
```sql
provenance_links(
  provenance_id bigserial primary key,
  project_id text not null,
  source_kind text not null,
  source_id text not null,
  target_kind text not null,
  target_id text not null,
  role text not null,
  metadata_json jsonb not null default '{}',
  created_at timestamptz not null
);
```

## `memory_search_docs`
```sql
memory_search_docs(
  doc_id text primary key,
  project_id text not null,
  doc_kind text not null,
  source_id text not null,
  title text not null,
  body text not null,
  filters_json jsonb not null default '{}',
  rank_features_json jsonb not null default '{}',
  tsv tsvector not null,
  visible_from_watermark bigint not null,
  hidden_at_watermark bigint null,
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

## `operations`
```sql
operations(
  operation_id text primary key,
  project_id text not null,
  operation_type text not null,
  lane text not null,
  status text not null,
  resource_type text null,
  resource_id text null,
  request_id text not null,
  idempotency_key text null,
  current_step text null,
  attempt_count integer not null default 0,
  result_json jsonb null,
  error_code text null,
  error_message text null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  completed_at timestamptz null
);
```

## `outbox_events`
```sql
outbox_events(
  outbox_id bigserial primary key,
  project_id text not null,
  operation_id text not null,
  event_type text not null,
  lane text not null,
  payload_json jsonb not null,
  delivery_state text not null,
  attempt_count integer not null default 0,
  next_attempt_at timestamptz not null,
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

## `code_index_runs`
```sql
code_index_runs(
  index_run_id text primary key,
  project_id text not null,
  operation_id text not null,
  repo_source_type text not null,
  repo_source_ref text null,
  mode text not null,
  status text not null,
  created_at timestamptz not null,
  updated_at timestamptz not null
);
```

## `code_index_snapshots`
```sql
code_index_snapshots(
  snapshot_id text primary key,
  project_id text not null,
  index_run_id text not null,
  parser_version text not null,
  schema_version text not null,
  status text not null,
  file_count integer not null,
  symbol_count integer not null,
  edge_count integer not null,
  chunk_count integer not null,
  ready_at timestamptz null,
  created_at timestamptz not null
);
```

## `projection_watermarks`
```sql
projection_watermarks(
  project_id text not null,
  projection_name text not null,
  watermark bigint not null,
  updated_at timestamptz not null,
  primary key(project_id, projection_name)
);
```
