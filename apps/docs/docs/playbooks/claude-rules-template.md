---
title: Claude Rules Template
sidebar_position: 3
---

Use this as a starting point for a Claude Code instruction file or equivalent local policy layer.

## Copy-paste template

```text
Use VibeRecall as the project memory system for this workspace.

Connection rules:
- Connect to https://api.<your-domain>/p/<project_id>/mcp with bearer token $VIBERECALL_TOKEN.
- Prefer the remote HTTP MCP server as the primary integration path.
- Treat tools as the required compatibility surface.
- Treat prompts and resources as optional accelerators only.
- Start each meaningful task by calling viberecall_get_status to verify the active project and runtime health.

Default workflow:
- After viberecall_get_status succeeds, start meaningful tasks with viberecall_get_context_pack.
- Use viberecall_search_entities only when the task is centered on a known entity.
- Use viberecall_get_neighbors only after identifying the correct entity.
- Save meaningful findings with viberecall_save_episode.
- Check viberecall_get_index_status before triggering viberecall_index_repo.

Safety rules:
- Do not hide critical workflows behind prompts-only or resources-only flows.
- Do not spam broad search calls without refining the task.
- Do not assume the hosted MCP server can inspect local uncommitted files directly.
- For local dirty-worktree indexing, use a Git source or workspace bundle flow.
- Do not trigger viberecall_index_repo unless the workflow is explicitly trusted and code context is actually stale or missing.
- Reconnect the MCP server after stale-session errors.
- Stop and ask the human if the active project, environment, token scope, or trust boundary is unclear.
- Stop and ask the human if the task appears to require privileged maintenance tools that are not already explicitly approved.

Correction rules:
- Use viberecall_explain_fact before viberecall_update_fact.
- Do not use viberecall_update_fact unless fact correction is part of an explicitly trusted workflow.
- Do not use privileged entity maintenance tools unless explicitly approved.

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

## Why this template is intentionally small

Claude integrations can vary in how they surface optional MCP capabilities. A small rules file keeps the behavior stable even when prompts or resources are unavailable.

For stricter teams, add repo-specific rules that define:

- who may trigger indexing
- who may correct canonical facts
- what the team considers a meaningful observation worth saving

## Related reading

- [Claude Code Guide](/agent-guides/claude-code)
- [Installation Profiles](/agent-guides/installation-profiles)
- [Failure Recovery](/playbooks/failure-recovery)
