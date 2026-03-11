---
title: Local Workspace Bridge
sidebar_position: 5
---

This page exists because many agent integrations make the same wrong assumption:

> If the MCP server is hosted, it can probably read my local repository path somehow.

That assumption is false.

## The real problem

The hosted VibeRecall core service can only access repository sources it can actually reach. A local dirty worktree on your laptop is not reachable just because the agent can see it.

If you try to index local-only changes by passing a path like `/Users/alice/repo`, the hosted service will not suddenly gain access to that filesystem.

## Two valid patterns

### 1. Reachable Git source

Use this when:

- the changes are committed or pushed
- the hosted runtime can access the remote repository

Representative shape:

```json
{
  "repo_source": {
    "type": "git",
    "remote_url": "https://github.com/example/repo.git",
    "ref": "main",
    "repo_name": "repo"
  }
}
```

### 2. Workspace bundle

Use this when:

- the task depends on uncommitted local changes
- you have a local helper or bridge that can package the workspace
- the resulting bundle can be uploaded or made reachable to the hosted service

Representative shape:

```json
{
  "repo_source": {
    "type": "workspace_bundle",
    "bundle_ref": "bundle_01...",
    "repo_name": "repo"
  }
}
```

This is the safe answer to the local dirty-worktree problem.

## What the bridge should and should not do

The bridge is optional helper infrastructure. It should:

- package or describe local workspace state
- help the agent produce a reachable bundle reference
- stay separate from the hosted memory source of truth

It should not:

- replace the hosted memory runtime
- hide required workflows behind a local-only prompt
- imply that the core hosted server can inspect arbitrary local paths

## When to introduce the bridge

You probably need it when:

- your agent works heavily on uncommitted local code
- Git-based indexing alone is not enough
- you want a repeatable local bundle flow instead of ad hoc manual uploads

You probably do not need it when:

- you mainly index committed code from Git
- the agent only uses memory retrieval and not code indexing

## Anti-patterns

- Assuming the hosted core can read local files directly.
- Triggering indexing before you know which repository source the server can access.
- Hiding the bundle step inside a prompt or resource that not every client can see.
- Treating the bridge as required for normal hosted memory usage.

## Related reading

- [Codex](/agent-guides/codex)
- [Claude Code](/agent-guides/claude-code)
- [Task Playbook](/playbooks/task-playbook)
- [Failure Recovery](/playbooks/failure-recovery)
