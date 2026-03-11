---
title: Installation Profiles
sidebar_position: 4
---

Not every agent needs every VibeRecall tool. The safest way to operate is to install a profile that matches the real job.

## Profile A: Memory only

Use when:

- the agent mainly needs write and retrieval support
- you want the safest daily-driver profile
- code indexing and graph reasoning are not central to the workflow

Recommended tools:

- `viberecall_get_status`
- `viberecall_save_episode`
- `viberecall_search_memory`
- `viberecall_get_fact`
- `viberecall_get_facts`

## Profile B: Memory plus graph read

Use when:

- the agent needs deeper reasoning about entities and relationships
- root-cause analysis often depends on dependency neighborhoods

Recommended additions on top of Profile A:

- `viberecall_search_entities`
- `viberecall_get_neighbors`
- `viberecall_find_paths`
- `viberecall_explain_fact`
- `viberecall_resolve_reference`

## Profile C: Memory plus indexing

Use when:

- the agent often works on code-heavy refactors
- repository context changes materially between tasks
- the user explicitly trusts the agent to trigger indexing

Recommended additions on top of Profile B:

- `viberecall_get_index_status`
- `viberecall_get_context_pack`
- `viberecall_index_repo`

Operational note:

- `viberecall_index_repo` is powerful and useful, but it should not be enabled casually if the team is not ready for code-index maintenance workflows

## Profile D: Operator or admin

Use when:

- the user is maintaining the memory graph itself
- entity hygiene work is part of the job
- corrective operations are part of an owner-approved workflow

Potential additions:

- `viberecall_update_fact`
- `viberecall_pin_memory`
- `viberecall_working_memory_get`
- `viberecall_working_memory_patch`
- `viberecall_merge_entities`
- `viberecall_split_entity`
- `viberecall_delete_episode`

This profile should not be the default for a general coding assistant.

## Choosing the right profile

If you are unsure:

- start with Profile A or B
- add indexing only after you see a real need
- add admin maintenance tools only for trusted operator workflows

This keeps the blast radius small and makes agent behavior easier to review.

## Related reading

- [Agent Guides Overview](/agent-guides/overview)
- [Codex](/agent-guides/codex)
- [Claude Code](/agent-guides/claude-code)
- [Agent Rules Overview](/playbooks/agent-rules-overview)
