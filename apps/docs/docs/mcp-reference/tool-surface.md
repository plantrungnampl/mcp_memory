---
title: MCP Tool Surface
description: The current 25-tool public VibeRecall MCP surface, grouped by practical workflow and privilege level.
sidebar_position: 2
---

The current public MCP surface exposes 25 `viberecall_*` tools.

## Why this page matters

This is the public-safe overview of the runtime contract. It is the page most operators and AI-agent users should treat as current truth when deciding which tools to enable.

The main operating rule is simple:

- use the smallest tool subset that can answer the task
- enable write or privileged tools only when the workflow genuinely needs them

## Tool families at a glance

The surface breaks down into five practical families:

1. canonical memory tools for saving, listing, searching, pinning, and correcting knowledge
2. runtime and operations tools for health, async operations, and working memory
3. indexing and context tools for repo indexing and bounded task context
4. graph and entity reasoning tools for canonical entities, neighborhoods, paths, and explanations
5. privileged maintenance tools for entity surgery and other operator workflows

This page describes the public-safe role of each family. It is not a promise that every team should enable every tool for every agent.

## Canonical memory tools

- `viberecall_save_episode`
- `viberecall_save`
- `viberecall_search_memory`
- `viberecall_search`
- `viberecall_get_fact`
- `viberecall_get_facts`
- `viberecall_update_fact`
- `viberecall_pin_memory`
- `viberecall_timeline`
- `viberecall_delete_episode`

What these are for:

- saving raw observations or structured handoff notes
- searching canonical memory and supporting episodes
- reading fact lineage
- applying fact corrections without overwriting history
- manually pinning or demoting important memory
- browsing timeline and episode history

Daily-driver note:

- `viberecall_save_episode`, `viberecall_search_memory`, `viberecall_get_fact`, and `viberecall_get_facts` cover most normal memory workflows
- `viberecall_save` and `viberecall_search` remain for compatibility with older clients

Recommended use:

- save stable observations that would help a future task
- search before re-deriving known architecture or operational facts
- explain or correct a fact rather than overwriting belief silently

Do not use these tools as a raw transcript dump of every thought. Memory quality matters more than memory volume.

## Runtime and operations tools

- `viberecall_get_status`
- `viberecall_get_operation`
- `viberecall_working_memory_get`
- `viberecall_working_memory_patch`

What these are for:

- checking runtime health for the current project
- polling asynchronous operations such as indexing or fact updates
- persisting lightweight task or session working memory when your workflow needs it

`viberecall_get_status` is the safest first call in almost every client.

Recommended use:

- start every new connection with `viberecall_get_status`
- poll long-running indexing or correction operations with `viberecall_get_operation`
- use working-memory APIs only when your workflow intentionally persists session-local structure

Many teams never need working memory for their first rollout. That is normal.

## Indexing and context tools

- `viberecall_index_repo`
- `viberecall_get_index_status`
- `viberecall_index_status`
- `viberecall_get_context_pack`

What these are for:

- queueing repository indexing when code context is stale
- checking whether an index is `READY`
- building a bounded context pack for a task without handcrafting many raw searches

Daily-driver note:

- `viberecall_get_context_pack` is the best default entry point for larger tasks
- `viberecall_index_repo` should usually be reserved for trusted workflows rather than enabled for every agent by default

Recommended use:

- call `viberecall_get_context_pack` when the task is broad and you want bounded context quickly
- check index status before triggering a new index
- reserve fresh indexing for cases where code context is missing, stale, or materially changed

Do not trigger indexing reflexively at the start of every task. That slows workflows and broadens permissions unnecessarily.

## Graph and entity reasoning tools

- `viberecall_search_entities`
- `viberecall_get_neighbors`
- `viberecall_find_paths`
- `viberecall_explain_fact`
- `viberecall_resolve_reference`
- `viberecall_merge_entities`
- `viberecall_split_entity`

What these are for:

- locating canonical entities that matter to the task
- exploring a bounded neighborhood around a known entity
- explaining why a fact exists and where it came from
- resolving ambiguous mentions against canonical entities
- performing privileged merge or split maintenance when explicitly allowed

Privilege note:

- `viberecall_merge_entities` and `viberecall_split_entity` are not everyday tools
- they belong in owner or operator workflows, not broad daily-driver profiles

Recommended use:

- use `viberecall_search_entities` when the task revolves around a known service, subsystem, or domain concept
- use `viberecall_get_neighbors` after you have the right entity
- use `viberecall_explain_fact` before deciding a fact is wrong
- use `viberecall_resolve_reference` when a mention is ambiguous and you want canonical alignment

Be conservative with merge and split operations. They change canonical identity semantics and should not live in generic agent profiles.

## Recommended daily-driver subset

For most Codex or Claude Code usage, start with:

- `viberecall_get_status`
- `viberecall_get_context_pack`
- `viberecall_search_memory`
- `viberecall_get_fact`
- `viberecall_get_facts`
- `viberecall_search_entities`
- `viberecall_get_neighbors`
- `viberecall_explain_fact`
- `viberecall_save_episode`
- `viberecall_get_index_status`

Enable the following only when needed:

- `viberecall_update_fact` when you are explicitly correcting stale knowledge
- `viberecall_index_repo` when repository context is stale or missing
- `viberecall_working_memory_patch` when you intentionally persist task-local state
- merge and split tools only for privileged entity maintenance

This subset supports a strong default workflow:

- fetch bounded context
- inspect known entities and facts
- save meaningful observations
- verify whether indexing is already ready

It avoids the most common early mistake, which is giving a general-purpose coding agent too much authority before its workflow is disciplined.

## Output contract

Tool responses use a text payload that contains JSON in a common envelope:

```json
{
  "output_version": "1.0",
  "ok": true,
  "result": {},
  "error": null,
  "request_id": "req_..."
}
```

When a tool fails:

- `ok` is `false`
- `result` is `null`
- `error` includes `code`, `message`, and optional `details`

Operator implication:

- parse the JSON envelope first
- branch on `ok`
- only inspect `result` deeply when `ok` is `true`

Do not treat free-form text before envelope parsing as the source of truth.

## Tool-selection rules

Prefer these patterns:

- start with `viberecall_get_context_pack` for broad task context
- use `viberecall_search_entities` and `viberecall_get_neighbors` when the task is entity-centric
- use `viberecall_explain_fact` before attempting to correct a fact
- use `viberecall_get_index_status` before triggering fresh indexing
- save meaningful observations, not every intermediate thought

Avoid these patterns:

- tool spam without changing the query or scope
- calling graph tools before you know the relevant entity
- triggering indexing on every task by default
- using privileged maintenance tools in a normal developer profile

## Safe profile mapping

If you are writing shared setup instructions, map tools to installation profiles:

- Profile A: memory write/read only
- Profile B: memory plus graph read
- Profile C: memory plus indexing for trusted developer workflows
- Profile D: owner or operator maintenance

The full profile guidance is in [Installation Profiles](/agent-guides/installation-profiles).

## Recommended smoke path

For first-time verification, use:

1. `viberecall_get_status`
2. `viberecall_save`
3. `viberecall_search`
4. `viberecall_get_facts`

This confirms transport initialization, write acceptance, retrieval, and canonical memory read paths without touching owner-only workflows.

## When to reach for which tool

Use this simple decision table:

| Situation | Start with |
| --- | --- |
| You need broad task context | `viberecall_get_context_pack` |
| You know the entity or subsystem name | `viberecall_search_entities` |
| You already have the entity and want local graph shape | `viberecall_get_neighbors` |
| You think a stored fact is stale or suspicious | `viberecall_explain_fact` |
| You need to correct a fact | `viberecall_update_fact` |
| You need to know if code indexing is usable | `viberecall_get_index_status` |
| You want to record something worth remembering | `viberecall_save_episode` |

If you still cannot decide, start with `viberecall_get_context_pack`. It is the most forgiving broad entry point for nontrivial work.

## Related reading

- [Connection](/mcp-reference/connection)
- [Agent Guides Overview](/agent-guides/overview)
- [Installation Profiles](/agent-guides/installation-profiles)
- [Task Playbook](/playbooks/task-playbook)
