---
title: Task Playbook
sidebar_position: 4
---

Use this playbook when you want a repeatable operating sequence for coding agents that use the current VibeRecall MCP tool surface.

This page is intentionally procedural. It tells the agent what to do, what not to do, and when to stop.

## 1. Start of task

Use this when:

- a new task begins
- the task direction changes materially
- the agent reconnects after a stale session

Required sequence:

1. Call `viberecall_get_status`.
2. Verify the project and runtime match the task.
3. Call `viberecall_get_context_pack` with a concise task-shaped query.
4. Inspect `status`, `context_mode`, `index_status`, `index_hint`, `gaps`, `architecture_overview`, `architecture_map`, `related_modules`, `related_files`, `relevant_symbols`, and `citations`.
5. If the task is entity-centric, call `viberecall_search_entities`.
6. Only if the correct entity is known, call `viberecall_get_neighbors` or `viberecall_find_paths`.
7. If the task is feature work or another architecture-sensitive change on an existing codebase, do not edit yet; acquire project overview first.

Do not:

- skip `viberecall_get_status`
- begin with broad tool spam
- call graph tools before you know which entity matters

## 2. During investigation

Use this when:

- the agent has a concrete finding
- the current context is missing one specific detail

Required sequence:

1. Keep working from the current task anchor.
2. Call `viberecall_search_memory` only if the missing detail is memory-shaped.
3. If the finding is durable and likely reusable, save it with `viberecall_save_episode`.

Save only:

- architecture conclusions
- confirmed debugging discoveries
- dependency or ownership findings that matter later
- handoff notes worth future retrieval

Do not save:

- repeated progress updates
- speculative theories
- every code-reading note

## 3. Before a new feature, large refactor, or architecture-sensitive change on an existing repo

Use this when:

- the task depends on repository structure
- the task depends on recent code movement
- the current context looks stale or incomplete

Required sequence:

1. Call `viberecall_get_index_status`.
2. If `get_context_pack` already gives enough code overview, inspect the repo locally and keep working.
3. If the context is still stale or missing, decide whether the workflow is explicitly trusted for indexing.
4. If the workflow is not explicitly trusted, stop and ask the human.
5. If the workflow is trusted, call `viberecall_index_repo`.
6. Wait for readiness.
7. Refresh with `viberecall_get_context_pack`.
8. For repo-local work, pair the refreshed pack with direct local repo inspection before editing code.

Do not:

- index on every task
- use indexing as a substitute for task scoping
- turn a missing detail into silent privilege expansion

## 4. When the task is entity-centric

Use this when:

- the task is about a named component, service, domain object, or canonical concept

Required sequence:

1. Call `viberecall_search_entities`.
2. Choose the correct entity.
3. Call `viberecall_get_neighbors` for bounded local context.
4. Call `viberecall_find_paths` only if the task depends on a relationship between known entities.

Do not:

- call graph tools before entity selection
- treat graph exploration as a default first step

## 5. When correcting stale knowledge

Use this when:

- a fact appears wrong
- a fact appears incomplete
- the agent wants to change canonical memory

Required sequence:

1. Call `viberecall_explain_fact`.
2. Review lineage and supporting episodes.
3. Confirm that this workflow is explicitly trusted for fact correction.
4. If not trusted, stop and ask the human.
5. If trusted and justified, call `viberecall_update_fact`.

Do not:

- correct facts on first suspicion
- skip provenance review
- blur read access into canonical correction without explicit approval

## 6. When the work depends on local unpublished code

Use this when:

- the task depends on uncommitted files
- the task depends on code that only exists on the agent's machine

Required sequence:

1. Decide whether the backend can reach a Git source directly.
2. If not, decide whether a workspace-bundle or local-backend path exists.
3. If no explicit path exists, stop and ask the human.
4. If a path exists and the workflow is trusted, use that path explicitly.
5. Only then call `viberecall_index_repo`.

Do not:

- assume the hosted MCP server can inspect a local path directly
- assume local unpublished code may leave the machine without explicit approval

See [Local Workspace Bridge](/agent-guides/local-workspace-bridge).

## 7. When project or environment scope is unclear

Use this when:

- the token may point at the wrong project
- the runtime health looks inconsistent with the task
- the environment may be wrong
- the trust boundary is no longer obvious

Required sequence:

1. Stop broad tool usage.
2. Re-run `viberecall_get_status`.
3. If scope is still unclear, stop and ask the human.

Do not continue by guessing.

## 8. After an important decision

Use this when:

- the task produces a durable decision
- the task uncovers a high-signal debugging fact
- the agent is about to hand off work

Required sequence:

1. Save one concise `viberecall_save_episode` note.
2. Include enough detail to reconnect the note to the task later.

This is the best time to capture signal without flooding memory.

## 9. Hard stop conditions

The agent must stop and ask the human when:

- project identity is unclear
- environment identity is unclear
- token scope is unclear
- the workflow may cross from read-only into privileged mutation
- local unpublished code may need to leave the machine
- a destructive tool appears necessary without explicit approval

## Anti-patterns

- Starting with indexing.
- Starting with graph traversal before entity selection.
- Saving every intermediate thought.
- Skipping `viberecall_explain_fact` before correction.
- Assuming hosted MCP can read local paths.
- Continuing after scope or trust becomes unclear.
- Treating prompts or resources as required for important workflows.
