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
- Prefer the remote HTTP MCP server as the primary compatibility path.
- Treat tools as the required integration surface.
- Treat prompts and resources as optional accelerators only.
- Start every meaningful task with viberecall_get_status.

Startup rules:
- After viberecall_get_status succeeds, call viberecall_get_context_pack with a concise task-shaped query.
- Inspect status, context_mode, index_status, index_hint, gaps, architecture_overview, architecture_map, related_modules, related_files, relevant_symbols, and citations before making any indexing decision.
- Do not assume missing prompts or resources means the platform is unusable.
- For feature work, large refactors, and other architecture-sensitive changes on an existing codebase, treat project overview as required before implementation.
- For repo-local work, use a hybrid flow: VibeRecall first for bounded context, then direct local repo inspection before editing.

Default retrieval rules:
- Use viberecall_search_memory for concrete memory lookups.
- Use viberecall_get_fact or viberecall_get_facts for fact inspection.
- Use viberecall_search_entities only when the task is centered on a known entity or canonical concept.
- Use viberecall_get_neighbors only after identifying the correct entity.
- Use viberecall_find_paths only when a bounded relationship path matters to the task.
- Do not spam broad retrieval calls without refining the task.

Write rules:
- Use viberecall_save_episode for durable conclusions only.
- Save architecture notes, confirmed debugging findings, and reusable handoff notes.
- Do not save speculative thoughts, repeated status updates, or every interim reading note.

Indexing rules:
- Call viberecall_get_index_status before viberecall_index_repo.
- Do not trigger viberecall_index_repo unless the workflow is explicitly trusted and get_context_pack still indicates stale or missing code context.
- If the task is feature work on an existing codebase and overview is still missing, treat indexing as the next required step inside a trusted workflow rather than optional cleanup.
- Do not assume the hosted MCP server can inspect local uncommitted files directly.
- For local unpublished code, require an explicit Git-reachable source, workspace-bundle flow, or local backend path.
- If no explicit path exists, stop and ask the human.

Correction and maintenance rules:
- Use viberecall_explain_fact before viberecall_update_fact.
- Do not use viberecall_update_fact unless fact correction is explicitly trusted for this workflow.
- Do not use viberecall_merge_entities or viberecall_split_entity unless explicitly approved.

Trust and escalation rules:
- Stop and ask the human if the active project, environment, token scope, or trust boundary is unclear.
- Stop and ask the human if a privileged tool appears necessary but has not been explicitly approved.
- Stop and ask the human if local unpublished code might need to leave the machine.

Failure-recovery rules:
- Reconnect the MCP server after stale-session errors.
- Re-run viberecall_get_status after reconnect before resuming normal retrieval.
- Do not keep writing after auth or scope failures until the target and token are confirmed.

Preferred daily-driver tool set:
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

## Why this template stays strict

Claude integrations can differ in how they expose optional MCP capabilities. A strict tools-first rules file is the safest way to keep behavior stable across those variations.

This template intentionally avoids:

- prompt-only workflows
- resource-only workflows
- default indexing
- default fact correction
- default merge/split maintenance

## Recommended repo-specific additions

Only add repo-specific rules if they are concrete enough to enforce, such as:

- exactly which tasks may trigger indexing
- who may correct canonical facts
- what “meaningful observation” means in your repository
- which environments are allowed for a given repo

## Related reading

- [Claude Code Guide](/agent-guides/claude-code)
- [Local Workspace Bridge](/agent-guides/local-workspace-bridge)
- [MCP Tool Surface](/mcp-reference/tool-surface)
- [Failure Recovery](/playbooks/failure-recovery)
