---
title: Codex Rules Template
sidebar_position: 2
---

Use this as a starting point for `AGENTS.md` or an equivalent Codex instruction file. Replace placeholders such as `<project_id>` and `https://api.<your-domain>` with your own values outside the prompt itself.

## Copy-paste template

```text
Use VibeRecall as the project memory source for this repository.

Connection rules:
- Connect to https://api.<your-domain>/p/<project_id>/mcp with bearer token $VIBERECALL_TOKEN.
- Treat tools as the required integration surface.
- Do not assume prompts or resources are available.
- Start each meaningful task by calling viberecall_get_status to verify the active project and runtime health.

Default tool behavior:
- After viberecall_get_status succeeds, start meaningful tasks with viberecall_get_context_pack.
- Inspect context_mode, index_status, and index_hint before assuming code context is available.
- Use viberecall_search_entities only when the task is entity-centric.
- Use viberecall_get_neighbors only after the relevant entity is known.
- Save meaningful discoveries with viberecall_save_episode.
- Check viberecall_get_index_status before requesting viberecall_index_repo.

Safety rules:
- Do not spam repeated broad searches without changing scope or query.
- Do not assume the hosted MCP server can read the local repository path.
- For local dirty-worktree indexing, use a Git source or workspace bundle flow.
- Do not call viberecall_index_repo unless the workflow is explicitly trusted and get_context_pack still indicates code context is stale or missing.
- Do not use merge or split entity tools unless the task is explicitly operator-approved.
- Reconnect the MCP server if a session becomes stale.
- Stop and ask the human if the active project, environment, token scope, or trust boundary is unclear.
- Stop and ask the human if the task appears to require privileged maintenance tools that are not already explicitly approved.

When correcting stale knowledge:
- Inspect lineage with viberecall_explain_fact before using viberecall_update_fact.
- Do not use viberecall_update_fact unless fact correction is part of an explicitly trusted workflow.

Preferred daily-driver tools:
- viberecall_get_status
- viberecall_get_context_pack
- viberecall_search_memory
- viberecall_get_fact
- viberecall_get_facts
- viberecall_search_entities
- viberecall_get_neighbors
- viberecall_explain_fact
- viberecall_save_episode
- viberecall_get_index_status
```

## When to extend this template

Add more rules only if your team has a clear reason, such as:

- allowing code indexing in normal developer workflows
- persisting working memory for long-running tasks
- enabling privileged maintenance tools for operators

Recommended additions for stricter teams:

- define exactly who is allowed to trigger `viberecall_index_repo`
- define exactly who is allowed to call `viberecall_update_fact`
- define what counts as a meaningful observation in this repository

Do not expand the rule set just because the platform exposes more tools.

## Related reading

- [Codex Guide](/agent-guides/codex)
- [Installation Profiles](/agent-guides/installation-profiles)
- [Failure Recovery](/playbooks/failure-recovery)
