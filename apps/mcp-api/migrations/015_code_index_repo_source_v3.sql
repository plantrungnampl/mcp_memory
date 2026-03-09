alter table code_index_runs
  add column if not exists repo_source_type text null,
  add column if not exists repo_source_ref text null,
  add column if not exists source_ref_value text null,
  add column if not exists repo_name text null,
  add column if not exists base_commit text null,
  add column if not exists credential_ref text null;

update code_index_runs
set repo_source_type = case
      when repo_path like 'bundle://%' then 'workspace_bundle'
      else 'legacy_path'
    end,
    repo_source_ref = repo_path
where repo_source_type is null
   or repo_source_ref is null;

create index if not exists idx_code_index_runs_project_ready_v3
  on code_index_runs (project_id, completed_at desc, index_id desc)
  where status = 'READY';
