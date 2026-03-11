---
title: Agent Guides Overview
sidebar_position: 1
---

This section is for teams using VibeRecall with AI coding agents rather than with a generic MCP client. The guidance is intentionally practical and conservative.

## The four rules that matter most

1. Use remote HTTP as the default connection path for hosted VibeRecall.
2. Treat tools as the required compatibility surface.
3. Keep the default tool set small.
4. Do not assume a hosted MCP server can see your local repository.

These rules exist because real clients differ. Some support both HTTP and stdio, some surface prompts and resources unevenly, and some handle reconnects or tool discovery more reliably than others.

## Start with the client-specific guide

- [Codex](/agent-guides/codex) if you want HTTP plus an optional local stdio bridge
- [Claude Code](/agent-guides/claude-code) if you want the remote HTTP-first path most Claude workflows expect

## Shared safe defaults

For most everyday work, the following subset is enough:

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

This gives the agent enough surface to:

- fetch broad task context
- narrow down to entities when needed
- inspect lineage before trusting a fact
- persist a meaningful observation
- check whether code context is ready

It does not hand the agent every privileged or potentially noisy tool by default.

## Optional capabilities are exactly that

Some clients or deployments may surface prompts or resources. That can be useful, but it is not the baseline.

Public-safe rule:

- if the tools work, the integration is already valid
- if prompts or resources are missing, do not treat that as a platform outage
- never hide a critical workflow behind prompts-only or resources-only assumptions

## Local dirty workspace reality

Hosted VibeRecall does not automatically see your local uncommitted repository state.

If your task depends on unpushed local changes:

- index from a reachable Git source, or
- use a local helper or bundle flow and call `viberecall_index_repo` with `repo_source.type = "workspace_bundle"`

The detailed pattern is documented in [Local Workspace Bridge](/agent-guides/local-workspace-bridge).

## Recommended reading order

1. [Installation Profiles](/agent-guides/installation-profiles)
2. [Codex](/agent-guides/codex) or [Claude Code](/agent-guides/claude-code)
3. [Task Playbook](/playbooks/task-playbook)
4. [Failure Recovery](/playbooks/failure-recovery)
