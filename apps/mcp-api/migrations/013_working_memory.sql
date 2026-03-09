create table if not exists working_memory (
  project_id text not null references projects(id) on delete cascade,
  task_id text not null,
  session_id text not null,
  state_json jsonb not null default '{}'::jsonb,
  checkpoint_note text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  expires_at timestamptz null,
  primary key (project_id, task_id, session_id)
);

create index if not exists idx_working_memory_project_updated
  on working_memory (project_id, updated_at desc);

create index if not exists idx_working_memory_expires
  on working_memory (expires_at)
  where expires_at is not null;
