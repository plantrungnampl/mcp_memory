create table if not exists projects (
  id text primary key,
  name text not null,
  owner_id text null,
  plan text not null default 'free',
  retention_days integer not null default 30,
  isolation_mode text not null default 'falkordb_graph',
  created_at timestamptz not null default now()
);

create table if not exists mcp_tokens (
  token_id text primary key,
  prefix text not null,
  token_hash text not null unique,
  project_id text not null references projects(id) on delete cascade,
  scopes text[] not null,
  plan text not null,
  created_at timestamptz not null default now(),
  last_used_at timestamptz null,
  revoked_at timestamptz null,
  expires_at timestamptz null
);

create table if not exists audit_logs (
  id bigserial primary key,
  request_id text not null,
  project_id text null,
  token_id text null,
  tool_name text null,
  action text not null,
  args_hash text null,
  status text not null,
  latency_ms double precision null,
  created_at timestamptz not null default now()
);

create table if not exists episodes (
  episode_id text primary key,
  project_id text not null references projects(id) on delete cascade,
  reference_time timestamptz null,
  ingested_at timestamptz not null default now(),
  enrichment_status text not null default 'pending',
  enrichment_error text null,
  job_id text null,
  content_ref text null,
  summary text null,
  content text not null,
  metadata_json jsonb not null default '{}'::jsonb
);

create table if not exists usage_events (
  id bigserial primary key,
  project_id text not null references projects(id) on delete cascade,
  token_id text null,
  tool text not null,
  provider text null,
  model text null,
  in_tokens integer not null default 0,
  out_tokens integer not null default 0,
  vibe_tokens integer not null default 0,
  ts timestamptz not null default now()
);
