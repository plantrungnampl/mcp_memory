create table if not exists operations (
  operation_id text primary key,
  project_id text not null references projects(id) on delete cascade,
  token_id text null,
  request_id text not null,
  kind text not null,
  status text not null check (status in ('ACCEPTED', 'RUNNING', 'SUCCEEDED', 'FAILED')),
  resource_type text null,
  resource_id text null,
  job_id text null,
  metadata_json jsonb not null default '{}'::jsonb,
  result_json jsonb null,
  error_json jsonb null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz null
);

create index if not exists idx_operations_project_created
  on operations (project_id, created_at desc, operation_id desc);

create index if not exists idx_operations_project_status
  on operations (project_id, status, created_at desc);

create table if not exists outbox_events (
  event_id text primary key,
  operation_id text not null references operations(operation_id) on delete cascade,
  project_id text not null references projects(id) on delete cascade,
  event_type text not null,
  payload_json jsonb not null,
  status text not null default 'PENDING' check (status in ('PENDING', 'FAILED', 'DISPATCHED')),
  attempts integer not null default 0,
  last_error text null,
  created_at timestamptz not null default now(),
  available_at timestamptz not null default now(),
  dispatched_at timestamptz null
);

create index if not exists idx_outbox_events_dispatch
  on outbox_events (status, available_at, created_at);

create table if not exists index_bundles (
  bundle_id text primary key,
  project_id text not null references projects(id) on delete cascade,
  object_key text not null,
  filename text not null,
  byte_size bigint not null,
  sha256 text not null,
  uploaded_by_user_id text null,
  created_at timestamptz not null default now(),
  expires_at timestamptz null
);

create index if not exists idx_index_bundles_project_created
  on index_bundles (project_id, created_at desc, bundle_id desc);
