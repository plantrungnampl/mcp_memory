---
title: Codex
sidebar_position: 2
---

Codex works well with VibeRecall when you keep the setup boring:

- one hosted MCP server over HTTP
- one bearer token from the target project
- one small daily-driver tool subset
- one optional local bridge only if you need local dirty-worktree support

## What Codex is good at here

Codex is a strong fit when you want:

- a hosted memory service shared across environments
- project-scoped context retrieval over HTTP
- optional local stdio helpers for workspace-specific flows
- explicit tool allowlists rather than a giant default surface

## Recommended topology

### Required

- `viberecall-core` over remote HTTP

### Optional

- `viberecall-bridge` over local stdio for workspace bundle or local helper flows

The hosted core remains the source of truth for project memory. The bridge is only a helper for local workspace access patterns.

## Representative Codex config

Configuration details vary slightly by Codex release, but the shape should look like this:

```toml
[mcp_servers.viberecall]
url = "https://api.<your-domain>/p/<project_id>/mcp"
bearer_token_env_var = "VIBERECALL_TOKEN"
tool_timeout_sec = 45

[mcp_servers.viberecall_bridge]
command = "vr-bridge"
args = ["serve-mcp"]
enabled = true
```

If you do not need local bundle or workspace-helper flows, leave the bridge disabled.

## Recommended daily-driver tool subset

Enable these first:

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

Enable only when you explicitly need them:

- `viberecall_update_fact`
- `viberecall_index_repo`
- `viberecall_working_memory_get`
- `viberecall_working_memory_patch`

Keep disabled by default in normal developer profiles:

- `viberecall_merge_entities`
- `viberecall_split_entity`

## Safe workflow for everyday coding tasks

### Start of task

1. Call `viberecall_get_context_pack` with the task description.
2. If the task is entity-centric, call `viberecall_search_entities`.
3. Use `viberecall_get_neighbors` only after you know which entity matters.

### During investigation

- save meaningful findings with `viberecall_save_episode`
- avoid saving every intermediate thought
- prefer one refined context query over repeated broad searches

### Before a large refactor

1. Call `viberecall_get_index_status`.
2. If code context is stale, trigger `viberecall_index_repo` from a trusted workflow.
3. Wait for the index to become ready before assuming code context is accurate.

### When correcting a stale belief

1. Call `viberecall_explain_fact`.
2. Inspect lineage and supporting episodes.
3. Only then call `viberecall_update_fact` if correction is actually warranted.

## Common Codex mistakes

- Enabling the entire tool surface when only a handful of tools are needed.
- Spamming `search_memory` instead of starting with `get_context_pack`.
- Using graph tools before identifying the relevant entity.
- Reusing a dead session after the backend restarts.
- Assuming the hosted core can read the local repository directly.

## Local dirty workspace story

This is the most common design mistake in agent setups.

Hosted `viberecall-core` cannot read `/Users/alice/repo` or any other local path from your machine. If Codex is working on uncommitted local changes, you have two valid options:

1. Push the branch and index from `repo_source.type = "git"`.
2. Use a local helper or bridge that packages the workspace and then index from `repo_source.type = "workspace_bundle"`.

If you need that second path, read [Local Workspace Bridge](/agent-guides/local-workspace-bridge).

## Prompts and resources

If your Codex path or extension surfaces prompts or resources, treat them as optional convenience. The core integration should remain fully usable through tools only.

## Related reading

- [Installation Profiles](/agent-guides/installation-profiles)
- [Local Workspace Bridge](/agent-guides/local-workspace-bridge)
- [Codex Rules Template](/playbooks/codex-rules-template)
- [Failure Recovery](/playbooks/failure-recovery)
