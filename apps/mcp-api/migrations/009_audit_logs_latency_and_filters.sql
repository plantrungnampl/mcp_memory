alter table audit_logs
  add column if not exists latency_ms double precision null;

create index if not exists idx_audit_logs_project_status_created
  on audit_logs (project_id, status, created_at desc);

create index if not exists idx_audit_logs_project_tool_created
  on audit_logs (project_id, tool_name, created_at desc);
