create unique index if not exists idx_unresolved_mentions_open_identity
  on unresolved_mentions (
    project_id,
    lower(btrim(mention_text)),
    coalesce(lower(btrim(observed_kind)), ''),
    coalesce(lower(btrim(repo_scope)), '')
  )
  where status = 'OPEN';
