---
title: Claude Code
description: Configure Claude Code as a remote HTTP-first VibeRecall client without depending on optional prompt or resource surfaces.
sidebar_position: 3
---

Claude Code should be treated as a remote HTTP-first client for VibeRecall. That keeps the setup aligned with the broadest supported hosted path and avoids depending on capability surfaces that may vary between Claude integrations.

## Recommended shape

Use:

- one remote HTTP MCP server
- one project-scoped bearer token
- one small tool subset for normal work

Do not design the core workflow around prompts or resources, even if a particular Claude integration happens to expose them.

## Representative setup

A representative command shape looks like this:

```bash
claude mcp add --transport http viberecall https://api.<your-domain>/p/<project_id>/mcp \
  --header "Authorization: Bearer $VIBERECALL_TOKEN"
```

If you also maintain a local helper:

```bash
claude mcp add viberecall-bridge -- vr-bridge serve-mcp
```

Treat the bridge as optional. The hosted memory service should remain usable without it.

## Recommended daily-driver subset

Start with:

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

Add only when the workflow needs them:

- `viberecall_update_fact`
- `viberecall_index_repo`
- `viberecall_working_memory_get`
- `viberecall_working_memory_patch`

Avoid broad daily-driver exposure for privileged maintenance tools such as entity merge or split.

## Safe Claude Code workflow

### Start of task

1. Call `viberecall_get_context_pack`.
2. Inspect `context_mode`, `index_status`, and any `gaps` or `index_hint`.
3. If the task revolves around a known component, service, or entity, call `viberecall_search_entities`.
4. Use `viberecall_get_neighbors` only once the task is anchored on the right entity.

### During work

- save meaningful observations with `viberecall_save_episode`
- use `viberecall_search_memory` for follow-up retrieval only when the task has shifted materially
- avoid flooding the runtime with repeated broad searches

### Before a code-heavy refactor

1. Check `viberecall_get_index_status`.
2. If `get_context_pack` is already `code_augmented` and the index is current, keep working.
3. If `get_context_pack` is `memory_only` and you need repo structure or code citations, trigger or request `viberecall_index_repo`.
4. Retry the task context retrieval after the index is ready.

## Prompts and resources policy

Some Claude integrations can surface prompts, resources, or both. Public-safe guidance is still:

- tools are the required baseline
- prompts and resources are optional and compatibility-dependent
- any valuable prompt workflow should still be achievable via direct tool calling

If tools work and prompts do not appear, the platform is still usable.

## Common Claude Code mistakes

- Assuming a prompt-based workflow is required before the tool path is valid.
- Treating missing resources as a server outage.
- Reusing a stale session after a restart.
- Over-enabling write or admin tools in a normal developer profile.
- Treating a `memory_only` context pack as a failed query instead of a fallback that may already be enough.
- Assuming the hosted server can inspect local uncommitted files directly.

## Local dirty workspace story

The same rule applies here as with Codex:

- a hosted MCP server cannot read your machine's local path directly
- index from Git when possible
- otherwise use a local helper or bundle flow and `repo_source.type = "workspace_bundle"`

See [Local Workspace Bridge](/agent-guides/local-workspace-bridge) for the supported pattern.

## Related reading

- [Installation Profiles](/agent-guides/installation-profiles)
- [Local Workspace Bridge](/agent-guides/local-workspace-bridge)
- [Claude Rules Template](/playbooks/claude-rules-template)
- [Failure Recovery](/playbooks/failure-recovery)
