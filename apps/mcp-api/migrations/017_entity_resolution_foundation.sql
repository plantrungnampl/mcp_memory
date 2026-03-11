alter table operations
  drop constraint if exists operations_status_check;

update operations
set status = 'PENDING'
where status = 'ACCEPTED';

update operations
set status = 'FAILED_TERMINAL'
where status = 'FAILED';

alter table operations
  add constraint operations_status_check
  check (status in ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED_RETRYABLE', 'FAILED_TERMINAL'));

create table if not exists entity_resolution_events (
  resolution_event_id text primary key,
  project_id text not null references projects(id) on delete cascade,
  operation_id text null references operations(operation_id) on delete set null,
  event_kind text not null check (event_kind in ('MERGE', 'SPLIT')),
  reason text null,
  canonical_target_entity_id text null references entities(entity_id) on delete set null,
  payload_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_entity_resolution_events_project_created
  on entity_resolution_events (project_id, created_at desc, resolution_event_id desc);

create table if not exists entity_redirects (
  source_entity_id text primary key references entities(entity_id) on delete cascade,
  project_id text not null references projects(id) on delete cascade,
  target_entity_id text not null references entities(entity_id) on delete restrict,
  resolution_event_id text null references entity_resolution_events(resolution_event_id) on delete set null,
  created_at timestamptz not null default now(),
  check (source_entity_id <> target_entity_id)
);

create index if not exists idx_entity_redirects_project_target
  on entity_redirects (project_id, target_entity_id, created_at desc);

create table if not exists unresolved_mentions (
  mention_id text primary key,
  project_id text not null references projects(id) on delete cascade,
  mention_text text not null,
  observed_kind text null,
  repo_scope text null,
  context_json jsonb not null default '{}'::jsonb,
  status text not null default 'OPEN' check (status in ('OPEN', 'RESOLVED', 'DISMISSED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_unresolved_mentions_project_created
  on unresolved_mentions (project_id, created_at desc, mention_id desc);
