create index if not exists idx_audit_logs_project_id_desc
  on audit_logs (project_id, id desc);
