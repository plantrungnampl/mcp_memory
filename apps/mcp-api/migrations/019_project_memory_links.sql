create table if not exists project_memory_links (
    project_id text not null references projects(id) on delete cascade,
    linked_project_id text not null references projects(id) on delete cascade,
    created_at timestamptz not null default now(),
    constraint project_memory_links_distinct check (project_id < linked_project_id),
    primary key (project_id, linked_project_id)
);

create index if not exists idx_project_memory_links_linked
on project_memory_links (linked_project_id, project_id);
