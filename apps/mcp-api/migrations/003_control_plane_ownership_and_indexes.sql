create index if not exists idx_projects_owner_created
on projects (owner_id, created_at desc, id desc);

create index if not exists idx_mcp_tokens_project_created
on mcp_tokens (project_id, created_at desc, token_id desc);
