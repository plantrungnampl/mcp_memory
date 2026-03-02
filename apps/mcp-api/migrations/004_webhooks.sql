create table if not exists webhooks (
  id bigserial primary key,
  provider text not null,
  event_id text not null,
  project_id text null references projects(id) on delete set null,
  event_type text not null,
  payload_hash text not null,
  status text not null,
  error text null,
  received_at timestamptz not null default now(),
  processed_at timestamptz null
);

create unique index if not exists idx_webhooks_provider_event
  on webhooks (provider, event_id);

create index if not exists idx_webhooks_status_received
  on webhooks (status, received_at desc);
