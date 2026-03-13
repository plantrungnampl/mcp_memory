---
title: Task Playbook
sidebar_position: 4
---

Use this playbook when you want a repeatable operating pattern for coding agents. It is written to work with the current public tool surface and to avoid assumptions about optional prompts or resources.

## Start of task

Use this when a new task begins or the task direction changes materially.

1. Call `viberecall_get_status`.
2. Confirm the active project and runtime look correct.
3. Call `viberecall_get_context_pack` with a concise task description.
4. Inspect `context_mode`, `index_status`, and any `index_hint` or `gaps`.
5. If the task is about a specific service, component, or entity, call `viberecall_search_entities`.
6. If needed, call `viberecall_get_neighbors` for a bounded dependency view.

Why:

- this catches wrong-project, stale-session, or unhealthy-runtime issues early
- this gives the agent broad context without flooding the runtime
- it keeps graph exploration anchored on a known entity

## During investigation

Use this when the agent has identified a concrete finding.

1. Save a meaningful observation with `viberecall_save_episode`.
2. Use `viberecall_search_memory` only if the current context is missing a needed detail.

Good observations include:

- architecture notes
- debugging discoveries
- a confirmed dependency
- a handoff summary worth reusing later

Do not save:

- repeated status updates
- speculative thoughts with no signal
- every interim code-reading note

## Before a large refactor

Use this when the task depends on code structure, dependency maps, or recent repository changes.

1. Call `viberecall_get_index_status`.
2. If `get_context_pack` is already `code_augmented` and the index is current, keep working.
3. If `get_context_pack` is `memory_only` or `empty`, decide whether the current workflow is trusted to trigger indexing.
4. If not explicitly trusted, stop and ask the human.
5. If trusted, trigger `viberecall_index_repo`.
6. Wait until the index becomes ready.
7. Refresh task context with `viberecall_get_context_pack`.

This avoids starting a refactor with stale code context and avoids silent privilege expansion.

## When project or environment scope is unclear

Use this when:

- the token may belong to another project
- the endpoint may point at the wrong environment
- the runtime health looks inconsistent with the task

1. Stop broad tool usage.
2. Re-run `viberecall_get_status`.
3. If scope is still unclear, stop and ask the human.

Do not continue by guessing. Scope confusion creates bad memory and bad corrections quickly.

## When correcting stale knowledge

Use this when a stored fact appears wrong or incomplete.

1. Call `viberecall_explain_fact`.
2. Inspect supporting episodes and lineage.
3. Decide whether this workflow is explicitly trusted to correct canonical facts.
4. If not explicitly trusted, stop and ask the human.
5. If trusted and correction is justified, call `viberecall_update_fact`.

Do not skip the explanation step. Correcting facts without reviewing provenance is how memory quality drifts.

## When the task is entity-centric

Use this when the problem is tied to a specific component, service, or canonical concept.

1. Call `viberecall_search_entities`.
2. Pick the right entity.
3. Call `viberecall_get_neighbors` or `viberecall_find_paths` as needed.

Avoid calling graph tools before you know the relevant entity. That is a common source of noisy retrieval.

## When the work depends on local uncommitted code

Use this when the repository state only exists locally.

1. Decide whether Git-based indexing is possible.
2. If not, decide whether a workspace bundle or bridge path exists.
3. If no explicit path exists, stop and ask the human.
4. If a path exists, prepare the bundle or bridge flow.
5. Call `viberecall_index_repo` with `repo_source.type = "workspace_bundle"`.

Do not assume the hosted MCP server can inspect the local repository path directly.

## After an important decision

When the task produces a durable conclusion:

1. save a concise `viberecall_save_episode` note
2. include enough metadata to reconnect the note to the task later

This is the best moment to capture architecture decisions and debugging conclusions.

## Anti-patterns

- Tool spam instead of scoped retrieval.
- Indexing on every task by default.
- Saving every intermediate thought.
- Skipping `viberecall_explain_fact` before correction.
- Assuming the hosted memory service can see local files.
- Continuing when project, environment, or trust scope is unclear.
