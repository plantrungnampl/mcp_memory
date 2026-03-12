---
title: Connection
description: Endpoint, auth, and transport rules for connecting project-scoped MCP clients to VibeRecall.
sidebar_position: 1
---

VibeRecall is MCP-first. Coding agents connect directly to a project-bound MCP endpoint instead of a separate general-purpose REST surface.

## Endpoint pattern

Use the project-specific MCP endpoint:

```text
https://api.<your-domain>/p/<project_id>/mcp
```

This keeps project isolation explicit at the transport boundary.

The path matters. The server is not a single global endpoint with project selection hidden inside headers or request bodies. The project boundary is part of the URL itself.

## Authentication model

- Auth type: bearer project access token
- Token format: `vr_mcp_sk_...`
- Scope: one project per token

Example header:

```text
Authorization: Bearer vr_mcp_sk_...
```

Do not reuse tokens across unrelated projects or environments. A valid token is still the wrong credential if it belongs to another project.

## Transport model

The public recommendation is:

- use remote HTTP for hosted deployments
- let the MCP client negotiate the session lifecycle
- treat `initialize`, tool discovery, and tool calls as one coherent session

This design serves Codex, Claude Code, and future clients that handle remote MCP over HTTP.

Local stdio is useful for helper utilities and workspace-bridge patterns, but it is not the primary hosted memory path.

## Transport behavior

The MCP transport is stateful. Clients should:

1. initialize the session
2. list tools
3. call tools using the same active session

If a reconnect or backend restart invalidates the session, reinitialize instead of replaying stale session IDs.

Practical implication:

- a healthy token cannot rescue a dead session
- a healthy session cannot rescue the wrong project path
- successful discovery does not guarantee later writes if the backend dependencies are down

Treat session state, auth, and backend availability as separate layers when debugging.

## Recommended connection strategy

For hosted deployments:

- prefer remote HTTP for Codex and Claude Code
- keep bearer-token auth explicit
- treat tool invocation as the required compatibility baseline

If your client offers multiple transport modes, start with the simplest remote HTTP path unless you are debugging a client-specific transport issue.

Recommended first-pass shape:

- one remote MCP server
- one token
- one project endpoint
- one narrow tool subset
- no assumption that prompts or resources will be visible in the UI

That keeps failure analysis local and obvious.

## Connection sequence that fails fast

A good first connection sequence is:

1. connect the MCP server
2. confirm tool discovery works
3. call `viberecall_get_status`
4. call a low-risk read such as `viberecall_get_facts`
5. only then proceed to writes, indexing, or graph work

This isolates transport and auth problems before you start debugging memory content.

## Project scope and token scope

Project isolation is deliberate:

- one project gets one MCP endpoint path namespace
- one token is intended for one project access boundary
- one client session should behave as though it is operating inside that project alone

Do not blur staging and production or one customer project and another by sharing tokens or cached sessions across them.

## Ownership and scope model

The web control plane manages projects, token lifecycle, usage visibility, logs, exports, and graph workflows. The MCP client only needs the project endpoint and plaintext token.

Important consequences:

- the MCP server does not create projects for you
- the MCP server does not replace the control plane
- admin and owner operations should stay out of everyday agent profiles unless you are operating the platform

## Tools first, prompts and resources optional

VibeRecall is designed so the critical path works through tools only.

That means:

- `viberecall_get_context_pack`, `viberecall_search_memory`, and related tools should be enough for useful work
- prompts and resources, if enabled by a specific client or deployment, are optional accelerators
- you should never hide a required workflow behind prompts-only or resources-only assumptions

For public-safe operator guidance, assume the client may surface tools well and everything else unevenly.

If a client shows prompts or resources, treat that as additional UX, not as proof that the server contract depends on those surfaces.

## Local versus hosted connection patterns

### Hosted memory, recommended default

Use:

- `https://api.<your-domain>/p/<project_id>/mcp`
- a bearer token
- a remote MCP client configuration

Best for:

- everyday agent usage
- multi-machine continuity
- central auditability and rollout control

### Local runtime for debugging

Use:

- `http://localhost:8010/p/<project_id>/mcp`
- local backend env and services
- local health checks before agent testing

Best for:

- backend debugging
- end-to-end local verification
- reproducing environment-specific failures

### Hosted memory plus local workspace bridge

Use:

- hosted remote core server for memory
- optional local stdio helper for workspace packaging

Best for:

- dirty local worktrees
- local repos that are not yet pushed
- agents that need memory plus local code awareness

That bridge pattern is covered in [Local Workspace Bridge](/agent-guides/local-workspace-bridge).

## What is not part of this public contract

- unresolved-mention backlog workflows
- owner-only export lifecycle
- retention and purge maintenance actions
- internal rollout assertions between web and API

## Common connection mistakes

- Using the docs or web host instead of the API host.
- Copying the right token into the wrong environment.
- Reusing a dead session after a backend restart.
- Treating missing optional resources as proof that the server is broken.
- Letting a client auto-retry against a stale session without reconnecting.

## Safe defaults

If you are writing onboarding, templates, or shared instructions for a team, default to:

- remote HTTP
- bearer-token env vars
- `viberecall_get_status` as the first proof-of-life tool
- [Installation Profiles](/agent-guides/installation-profiles) rather than full-surface enablement
- [Task Playbook](/playbooks/task-playbook) rather than ad hoc agent behavior

These defaults produce fewer rollout surprises than broad, convenience-first setups.

## Related reading

- [Quickstart](/getting-started/quickstart)
- [MCP Tool Surface](/mcp-reference/tool-surface)
- [Agent Guides Overview](/agent-guides/overview)
- [Common Failures](/troubleshooting/common-failures)
