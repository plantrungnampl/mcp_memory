create table if not exists code_index_runs (
  index_id text primary key,
  project_id text not null references projects(id) on delete cascade,
  job_id text null,
  repo_path text not null,
  mode text not null check (mode in ('snapshot', 'diff')),
  effective_mode text null check (effective_mode in ('snapshot', 'diff')),
  base_ref text null,
  head_ref text null,
  max_files integer not null default 5000,
  status text not null check (status in ('QUEUED', 'RUNNING', 'READY', 'FAILED')),
  phase text not null default 'queued',
  processed_files integer not null default 0,
  total_files integer not null default 0,
  scanned_files integer not null default 0,
  changed_files integer not null default 0,
  file_count integer not null default 0,
  symbol_count integer not null default 0,
  entity_count integer not null default 0,
  relationship_count integer not null default 0,
  chunk_count integer not null default 0,
  top_modules_json jsonb not null default '[]'::jsonb,
  top_files_json jsonb not null default '[]'::jsonb,
  error text null,
  requested_by_token_id text null,
  created_at timestamptz not null default now(),
  started_at timestamptz null,
  completed_at timestamptz null
);

create index if not exists idx_code_index_runs_project_created
  on code_index_runs (project_id, created_at desc, index_id desc);

create index if not exists idx_code_index_runs_project_ready
  on code_index_runs (project_id, completed_at desc, index_id desc)
  where status = 'READY';

create unique index if not exists uniq_code_index_runs_project_active
  on code_index_runs (project_id)
  where status in ('QUEUED', 'RUNNING');

create table if not exists code_index_files (
  index_id text not null references code_index_runs(index_id) on delete cascade,
  file_path text not null,
  language text not null,
  module_name text not null,
  sha1 text not null,
  row_json jsonb not null,
  primary key (index_id, file_path)
);

create table if not exists code_index_entities (
  index_id text not null references code_index_runs(index_id) on delete cascade,
  entity_id text not null,
  entity_type text not null,
  name text not null,
  file_path text null,
  language text null,
  kind text null,
  line_start integer null,
  line_end integer null,
  search_text text not null,
  search_tokens text[] not null default '{}'::text[],
  primary key (index_id, entity_id)
);

create index if not exists idx_code_index_entities_index_type
  on code_index_entities (index_id, entity_type, name);

create index if not exists idx_code_index_entities_tokens
  on code_index_entities using gin (search_tokens);

create table if not exists code_index_chunks (
  index_id text not null references code_index_runs(index_id) on delete cascade,
  chunk_id text not null,
  entity_id text not null,
  file_path text null,
  language text null,
  line_start integer null,
  line_end integer null,
  snippet text not null,
  tokens text[] not null default '{}'::text[],
  primary key (index_id, chunk_id)
);

create index if not exists idx_code_index_chunks_index_entity
  on code_index_chunks (index_id, entity_id);

create index if not exists idx_code_index_chunks_tokens
  on code_index_chunks using gin (tokens);
