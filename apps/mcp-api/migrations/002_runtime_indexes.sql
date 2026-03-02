alter table episodes
  add column if not exists enrichment_error text null;

create index if not exists idx_episodes_project_timeline
  on episodes (project_id, coalesce(reference_time, ingested_at) desc, episode_id desc);

create index if not exists idx_episodes_project_recent_pending
  on episodes (project_id, ingested_at desc)
  where enrichment_status <> 'complete';

create index if not exists idx_usage_events_project_ts
  on usage_events (project_id, ts desc);

create index if not exists idx_audit_logs_project_created
  on audit_logs (project_id, created_at desc);
