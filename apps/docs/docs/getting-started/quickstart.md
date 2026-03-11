---
title: Quickstart
sidebar_position: 1
---

This is the fastest path to connect a coding agent to VibeRecall and verify the end-to-end MCP loop:

1. authenticate
2. discover tools
3. write one observation
4. retrieve it again through the public memory surface

If you only read one page before trying the product, make it this one.

## Prerequisites

- Access to the VibeRecall control plane
- One project you can manage
- One plaintext MCP token copied at creation time
- The public API base URL for your environment
- One MCP-capable client such as Codex or Claude Code

You do not need:

- a local bridge for the first smoke test
- prompt support in the client
- resource support in the client
- graph admin privileges

## What you are proving

By the end of this quickstart, you should know that:

- your token is valid for the target project
- your client can negotiate the MCP transport correctly
- the runtime can accept a memory write
- the canonical memory read path can retrieve recent context
- you are using the public surface rather than a private control-plane route

## 1. Create or open a project

In the control plane:

1. Sign in to the control plane.
2. Create or open a project.
3. Confirm the `project_id` for the environment you want to test.

Every MCP endpoint is project-scoped. If you point a valid token at the wrong project path, the connection will still fail.

## 2. Mint a token and store it safely

Mint an MCP token and copy the plaintext value immediately. The control plane only shows the full token once.

Recommended local handling:

- store it in your shell secrets or password manager
- expose it to the client as `VIBERECALL_TOKEN`
- never commit the token to source control or screenshots
- rotate it when you move devices or workflows
- revoke and replace it if it leaks into terminal logs, screen recordings, or chat transcripts

Example:

```bash
export VIBERECALL_TOKEN='vr_mcp_sk_...'
```

## 3. Use the project-scoped MCP endpoint

Endpoint pattern:

```text
https://api.<your-domain>/p/<project_id>/mcp
```

Authentication:

```text
Authorization: Bearer vr_mcp_sk_...
```

If you are using a hosted deployment, use the public API origin. Do not point your client at the web app host or a browser-facing docs route.

## 4. Connect your MCP client

For a first smoke test, keep the setup minimal:

- one remote HTTP MCP server
- one bearer token
- no prompt-only workflow assumptions
- no optional local bridge yet unless you specifically need local dirty-worktree indexing

If you want client-specific setup details:

- [Codex guide](/agent-guides/codex)
- [Claude Code guide](/agent-guides/claude-code)

### Minimal connection goal

Do not over-configure the client before the first proof-of-life run. The correct first milestone is:

1. the server appears in the client
2. tools are discoverable
3. one safe read works
4. one safe write works

Only after that should you introduce richer rules, indexing, or local workspace bridge flows.

## 5. Run the first verification flow

After your MCP client connects and discovers tools, run these calls in order:

1. `viberecall_get_status`
2. `viberecall_save`
3. `viberecall_search`
4. `viberecall_get_facts`

### Suggested first write

Use a short, searchable observation:

```json
{
  "content": "Quickstart validation note: the auth proxy depends on Redis.",
  "metadata": {
    "source": "quickstart",
    "task": "docs-onboarding"
  }
}
```

### Why this order matters

- `viberecall_get_status` proves the runtime is reachable and bound to your project.
- `viberecall_save` proves the write path accepts input.
- `viberecall_search` proves recent retrieval works through the public memory surface.
- `viberecall_get_facts` proves canonical listing works without relying on a search-only view.

## Expected success signals

You are looking for the following outcomes:

- `viberecall_get_status` reports the current `project_id` and backend status
- the save call is accepted instead of rejected at auth or transport level
- the follow-up search returns your quickstart note or closely related context
- fact listing returns structured JSON rather than a transport or permission error

If one step fails, stop there and diagnose it. Do not assume a later tool result is meaningful if the session or auth layer is already wrong.

### Expected operator interpretation

Read the first smoke path like this:

- if discovery fails, the problem is transport or auth
- if status works but save fails, the problem is usually input shape, permissions, or a backend dependency
- if save works but search does not surface useful context, the problem is usually query choice or runtime backing services
- if fact listing works, you have validated the canonical read side rather than only a best-effort search

That sequence reduces debugging scope early.

## Session recovery and reconnect behavior

If your IDE starts returning `404 Session not found` after a backend reload or reconnect, reinitialize the MCP session. The transport is stateful, and stale session identifiers are rejected.

Typical causes:

- your client reused a dead session after a server restart
- you switched environments without reconnecting cleanly
- a local proxy or dev reload reset the server-side session registry

Recovery is simple:

1. remove the dead session if the client exposes that action
2. reconnect the MCP server
3. rerun `viberecall_get_status`

Do not keep retrying write tools against a dead session. That burns time and makes the failure look like a content bug when it is really a transport reset.

## Common quickstart mistakes

- Using the web app host instead of the API host.
- Testing the endpoint in a normal browser tab instead of an MCP client.
- Forgetting to copy the token plaintext at creation time.
- Reusing a token for the wrong project.
- Assuming prompts or resources must work before tools work.
- Treating a stale session as an auth failure.

## Token handling rules

- Store MCP tokens in secure local secrets storage
- Never commit tokens to source control
- Rotate when you move to a new device or tool
- Revoke immediately if a token leaks

Do not test the MCP endpoint in a normal browser tab. MCP clients must negotiate the transport and headers correctly.

## What to do after the first successful smoke test

After you have a clean first run:

1. read [Connection](/mcp-reference/connection) to understand transport and session boundaries
2. read [MCP Tool Surface](/mcp-reference/tool-surface) to choose a narrower daily-driver subset
3. choose an [Installation Profile](/agent-guides/installation-profiles) for your agent
4. add a rules template from [Playbooks & Rules](/playbooks/agent-rules-overview)
5. only then enable indexing or local workspace bridge patterns if your workflow truly needs them

That order keeps rollout reversible and easier to debug.

## Next steps

- Read [Connection](/mcp-reference/connection) for session and transport details.
- Read [MCP Tool Surface](/mcp-reference/tool-surface) for the current 25-tool contract.
- Read [Agent Guides Overview](/agent-guides/overview) if your main consumer is an AI coding agent.
- Read [Common Failures](/troubleshooting/common-failures) if the first connection did not work cleanly.
