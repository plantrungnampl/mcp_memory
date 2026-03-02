create table if not exists exports (
  export_id text primary key,
  project_id text not null references projects(id) on delete cascade,
  status text not null,
  format text not null default 'json_v1',
  object_key text null,
  object_url text null,
  expires_at timestamptz null,
  error text null,
  requested_by text null,
  requested_at timestamptz not null default now(),
  completed_at timestamptz null,
  job_id text null
);

create index if not exists idx_exports_project_requested
  on exports (project_id, requested_at desc, export_id desc);

create index if not exists idx_exports_project_status
  on exports (project_id, status, requested_at desc);
