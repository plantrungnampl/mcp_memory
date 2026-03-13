---
title: Agent Rules Overview
sidebar_position: 1
---

This section is for teams that want copy-paste rules for an `AGENTS.md`, instruction file, or client-specific system prompt layer.

The goal is not to write a giant policy document. The goal is to create a few clear rules that keep the agent effective and predictable.

## What good rules should do

Good rules should:

- keep the workflow tool-first
- encourage small, bounded retrieval steps
- prevent tool spam
- make local dirty-worktree handling explicit
- keep privileged tools out of normal developer profiles

Good rules should not:

- hardcode secrets
- assume prompts or resources are always available
- imply the hosted MCP server can see local paths
- force the agent to call many tools before it has a concrete task anchor

## Recommended rule themes

### 1. Start with context, not with tool spam

Good default:

- call `viberecall_get_status` first to verify the active project and runtime health
- call `viberecall_get_context_pack` at the start of a meaningful task
- inspect `context_mode`, `index_status`, and `index_hint` before deciding indexing is necessary
- call `viberecall_search_entities` only when the task is entity-centric
- call `viberecall_get_neighbors` only after the right entity is known

### 2. Save meaningful observations only

Good default:

- save decisions, discoveries, and handoff notes
- do not save every speculative thought or repeated summary

### 3. Check index state before indexing

Good default:

- call `viberecall_get_index_status`
- only trigger `viberecall_index_repo` when code context is stale or missing and `get_context_pack` shows `memory_only` or `empty`
- keep indexing disabled for normal agents unless the workflow is explicitly trusted

### 4. Make the local workspace boundary explicit

Good default:

- do not assume the hosted MCP server can read a local repository path
- use Git indexing or a workspace-bundle flow instead

### 5. Keep optional capability optional

Good default:

- prompts and resources are accelerators, not prerequisites
- every important workflow should remain possible through tools

### 6. Add a stop-and-escalate rule

Good default:

- if the active project, environment, token scope, or trust boundary is unclear, stop and ask the human
- if the task appears to require privileged maintenance tools, stop and ask the human
- if the task depends on local unpublished code and no explicit bundle or bridge path exists, stop and ask the human

## Anti-patterns to ban explicitly

- Tool spam.
- Stale session reuse after reconnect.
- Assuming the hosted MCP server can see the local repo.
- Hiding critical flows behind prompts or resources only.
- Giving admin maintenance tools to every everyday coding agent.
- Continuing after project or environment scope becomes unclear.

## Copy-paste templates

- [Codex Rules Template](/playbooks/codex-rules-template)
- [Claude Rules Template](/playbooks/claude-rules-template)
- [Task Playbook](/playbooks/task-playbook)
- [Failure Recovery](/playbooks/failure-recovery)
