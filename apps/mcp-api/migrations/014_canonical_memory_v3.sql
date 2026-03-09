create table if not exists entities (
  entity_id text primary key,
  project_id text not null references projects(id) on delete cascade,
  entity_kind text not null,
  canonical_name text not null,
  display_name text not null,
  state text not null default 'ACTIVE',
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_entities_project_kind_name
  on entities (project_id, entity_kind, canonical_name);

create table if not exists entity_aliases (
  alias_id bigserial primary key,
  project_id text not null references projects(id) on delete cascade,
  entity_id text not null references entities(entity_id) on delete cascade,
  alias_type text not null,
  alias_value text not null,
  confidence numeric null,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create unique index if not exists uniq_entity_aliases_project_value
  on entity_aliases (project_id, alias_type, alias_value)
  where active = true;

create table if not exists relation_types (
  relation_type_id text primary key,
  name text not null unique,
  inverse_name text not null,
  relation_class text not null,
  is_transitive boolean not null default false,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists fact_groups (
  fact_group_id text primary key,
  project_id text not null references projects(id) on delete cascade,
  current_fact_version_id text null,
  natural_key_hash text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_fact_groups_project_updated
  on fact_groups (project_id, updated_at desc, fact_group_id desc);

create table if not exists fact_versions (
  fact_version_id text primary key,
  fact_group_id text not null references fact_groups(fact_group_id) on delete cascade,
  project_id text not null references projects(id) on delete cascade,
  fact_shape text not null,
  subject_entity_id text not null references entities(entity_id) on delete restrict,
  relation_type_id text not null references relation_types(relation_type_id) on delete restrict,
  object_entity_id text null references entities(entity_id) on delete restrict,
  value_json jsonb null,
  statement text not null,
  normalized_statement text not null,
  valid_from timestamptz null,
  valid_to timestamptz null,
  recorded_at timestamptz not null default now(),
  superseded_at timestamptz null,
  status text not null,
  confidence numeric null,
  salience_score numeric null,
  trust_class text not null default 'observed',
  created_from_episode_id text null references episodes(episode_id) on delete set null,
  replaces_fact_version_id text null references fact_versions(fact_version_id) on delete set null,
  metadata_json jsonb not null default '{}'::jsonb
);

create unique index if not exists uniq_fact_versions_current
  on fact_versions (fact_group_id)
  where status = 'CURRENT' and superseded_at is null;

create index if not exists idx_fact_versions_project_recorded
  on fact_versions (project_id, recorded_at desc, fact_version_id desc);

create table if not exists provenance_links (
  provenance_id bigserial primary key,
  project_id text not null references projects(id) on delete cascade,
  source_kind text not null,
  source_id text not null,
  target_kind text not null,
  target_id text not null,
  role text not null,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_provenance_links_project_target
  on provenance_links (project_id, target_kind, target_id, created_at desc);

create table if not exists memory_search_docs (
  doc_id text primary key,
  project_id text not null references projects(id) on delete cascade,
  doc_kind text not null,
  source_id text not null,
  title text not null,
  body text not null,
  filters_json jsonb not null default '{}'::jsonb,
  rank_features_json jsonb not null default '{}'::jsonb,
  tsv tsvector generated always as (
    to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(body, ''))
  ) stored,
  visible_from_watermark bigint not null default 0,
  hidden_at_watermark bigint null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_memory_search_docs_project_visible
  on memory_search_docs (project_id, hidden_at_watermark, updated_at desc);

create index if not exists idx_memory_search_docs_tsv
  on memory_search_docs using gin (tsv);

create table if not exists projection_watermarks (
  project_id text not null references projects(id) on delete cascade,
  projection_name text not null,
  watermark bigint not null default 0,
  updated_at timestamptz not null default now(),
  primary key (project_id, projection_name)
);
