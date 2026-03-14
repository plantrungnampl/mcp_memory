---
title: Agent Rules Overview
sidebar_position: 1
---

This section is for teams that want a strict, public-safe rules layer for coding agents that use VibeRecall over MCP.

The goal is not to sound sophisticated. The goal is to make agent behavior predictable, bounded, and easy to review.

## What these rules are for

Use these rules when you want an agent to:

- verify the active project before making memory changes
- retrieve context in small, explainable steps
- avoid overusing graph and indexing tools
- stop at trust boundaries instead of guessing
- preserve a clean separation between everyday coding work and privileged maintenance

Use these rules when you **do not** want an agent to:

- assume hidden prompts or resources exist
- treat every task as an indexing task
- silently cross from read workflows into destructive workflows
- assume a hosted MCP server can inspect a laptop's local filesystem

## The non-negotiable rule set

### 1. Start every meaningful task with runtime truth

The agent **must**:

- call `viberecall_get_status` first
- verify that the active project and runtime health match the task
- call `viberecall_get_context_pack` only after the status check succeeds

The agent **must not**:

- start with broad search spam
- assume the current MCP session still points to the correct project
- start writing memory before verifying runtime and project scope

This one rule prevents a large class of wrong-project and stale-session errors.

### 2. Treat `get_context_pack` as a starting point, not a license to index

The agent **must** inspect:

- `status`
- `context_mode`
- `index_status`
- `index_hint`
- any reported `gaps`

The agent **must not**:

- assume `memory_only` means failure
- assume `empty` means indexing is automatically allowed
- trigger `viberecall_index_repo` without an explicit trusted workflow

`viberecall_get_context_pack` is designed to tell the agent whether useful context already exists. It is not a blanket instruction to index the repository.

### 3. Use narrow retrieval before broad retrieval

Default retrieval order:

1. `viberecall_get_status`
2. `viberecall_get_context_pack`
3. `viberecall_search_memory` or `viberecall_get_fact` when a concrete memory detail is needed
4. `viberecall_search_entities` only when the task is clearly entity-centric
5. `viberecall_get_neighbors` or `viberecall_find_paths` only after the correct entity is known

The agent **must not**:

- call graph tools before it knows which entity matters
- repeat broad searches without refining the query
- call many MCP tools “just in case”

### 4. Save only durable signal

The agent **should** save:

- architecture decisions
- confirmed debugging discoveries
- trust-boundary or environment findings
- handoff notes worth reusing later

The agent **must not** save:

- repeated progress updates
- speculative thoughts
- every intermediate reading note
- long summaries that add no future retrieval value

`viberecall_save_episode` is for durable memory, not a live scratchpad dump.

### 5. Make local-workspace boundaries explicit

The agent **must not** assume:

- a hosted MCP server can read `/Users/alice/repo`
- a hosted MCP server can inspect uncommitted local files directly
- a local path shown to the agent is automatically reachable by the backend

If the task depends on local unpublished code, the agent **must** use one of these explicit paths:

- remote Git indexing that the backend can actually reach
- a workspace-bundle flow
- a local backend running close to the repository

If none of those paths exists, the agent **must stop and ask the human**.

See [Local Workspace Bridge](/agent-guides/local-workspace-bridge).

### 6. Keep privileged tools behind explicit approval

For normal coding workflows, the agent **must not** call these by default:

- `viberecall_index_repo`
- `viberecall_update_fact`
- `viberecall_merge_entities`
- `viberecall_split_entity`

The agent may use them **only if**:

- the workflow is explicitly trusted
- the token and environment are clearly correct
- the human has approved the capability for that task class

This rule exists because these tools change repository context, canonical memory, or canonical identity semantics.

### 7. Require provenance before correction

Before correcting canonical memory, the agent **must**:

1. call `viberecall_explain_fact`
2. inspect lineage and supporting episodes
3. confirm the workflow is trusted for fact correction

The agent **must not** call `viberecall_update_fact` on first suspicion.

### 8. Stop when the trust boundary becomes unclear

The agent **must stop and ask the human** when any of these are unclear:

- project identity
- environment identity
- token scope
- whether the workflow is trusted for indexing
- whether the workflow is trusted for canonical correction
- whether local unpublished code may leave the machine

The agent **must not** “try one call and see what happens” across a trust boundary.

### 9. Treat prompts and resources as optional

The agent **must** remain fully usable through tools alone.

The agent **must not**:

- hide critical workflows behind prompts only
- hide critical workflows behind resources only
- claim the platform is unusable just because optional capabilities are missing

## Bad rules to ban explicitly

Do not ship instruction files that tell agents to:

- call many tools before they have a task anchor
- index the repository at task start
- save every finding automatically
- guess when project scope is unclear
- use privileged tools as part of the default daily-driver profile
- assume a hosted MCP server can see local paths

## How the rules pages should work together

- [Codex Rules Template](/playbooks/codex-rules-template): copy-paste policy for Codex-style clients
- [Claude Rules Template](/playbooks/claude-rules-template): same policy adapted for Claude Code style integrations
- [Task Playbook](/playbooks/task-playbook): scenario-by-scenario operating sequence
- [Failure Recovery](/playbooks/failure-recovery): what to do after stale sessions, auth drift, or wrong-project mistakes
- [MCP Tool Surface](/mcp-reference/tool-surface): the public tool families and why most teams should start with a small allowlist
