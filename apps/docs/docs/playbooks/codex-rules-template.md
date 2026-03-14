---
title: Codex Rules Template
sidebar_position: 2
---

Use this as a starting point for `AGENTS.md` or an equivalent Codex instruction file. Replace placeholders such as `<project_id>` and `https://api.<your-domain>` outside the prompt itself.

## Copy-paste template

```text
Use VibeRecall as the project memory source for this repository.

Connection rules:
- Connect to https://api.<your-domain>/p/<project_id>/mcp with bearer token $VIBERECALL_TOKEN.
- Treat MCP tools as the required integration surface.
- Do not assume prompts or resources are available.
- Start every meaningful task with viberecall_get_status.
- If viberecall_get_status does not confirm the expected project and healthy runtime, stop and ask the human.

Startup rules:
- After viberecall_get_status succeeds, call viberecall_get_context_pack with a short task-shaped query.
- Inspect status, context_mode, index_status, index_hint, and gaps before deciding what to do next.
- Treat context_mode=memory_only as a valid operating state, not an automatic reason to index.
- Treat context_mode=empty as a signal to gather more explicit context, not a license to expand scope silently.

Default daily-driver retrieval rules:
- Prefer viberecall_search_memory and viberecall_get_fact for concrete memory lookups.
- Use viberecall_search_entities only when the task is clearly entity-centric.
- Use viberecall_get_neighbors only after the correct entity is known.
- Use viberecall_find_paths only when the task depends on a bounded relationship path between known entities.
- Do not spam repeated broad searches without changing the query or narrowing the task.

Memory write rules:
- Use viberecall_save_episode only for durable signal: architecture decisions, confirmed debugging findings, or handoff notes worth reusing later.
- Do not save speculative thoughts, repeated progress updates, or every code-reading note.

Indexing rules:
- Check viberecall_get_index_status before requesting viberecall_index_repo.
- Do not call viberecall_index_repo unless the workflow is explicitly trusted and get_context_pack still indicates code context is stale or missing.
- Do not turn indexing into a default first step.
- If the task depends on local unpublished code, do not assume the hosted MCP server can read the local repository path.
- For local unpublished code, use an explicit Git-reachable source, a workspace bundle flow, or a local backend.
- If none of those paths exists, stop and ask the human.

Correction and identity rules:
- Call viberecall_explain_fact before viberecall_update_fact.
- Do not use viberecall_update_fact unless fact correction is part of an explicitly trusted workflow.
- Do not use viberecall_merge_entities or viberecall_split_entity unless the task is explicitly operator-approved.

Trust-boundary rules:
- Stop and ask the human if the active project, environment, token scope, or trust boundary is unclear.
- Stop and ask the human if the task appears to require privileged maintenance tools that are not already explicitly approved.
- Stop and ask the human if the task depends on local unpublished code and no explicit bundle or bridge path exists.

Failure-recovery rules:
- Reconnect the MCP server after stale-session errors such as “404 Session not found”.
- Re-run viberecall_get_status after reconnect before resuming tool calls.
- Do not continue broad writes after auth or scope failures until the human confirms the target and token.

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

## What this template intentionally does not do

It does not:

- grant indexing by default
- grant canonical correction by default
- grant merge/split maintenance by default
- assume local filesystem visibility from a hosted backend
- assume prompts or resources exist in every Codex surface

That omission is intentional. A small, strict policy file produces safer and more repeatable behavior than a large “maybe do this” ruleset.

## Recommended repo-specific additions

Add repo-specific rules only if your team can define them clearly, for example:

- the exact classes of tasks that are trusted to trigger indexing
- who may correct canonical facts
- what counts as a durable observation worth saving
- which project or environment names are allowed for this repo

If you cannot define those precisely, do not add them.

## Related reading

- [Codex Guide](/agent-guides/codex)
- [Local Workspace Bridge](/agent-guides/local-workspace-bridge)
- [MCP Tool Surface](/mcp-reference/tool-surface)
- [Failure Recovery](/playbooks/failure-recovery)
