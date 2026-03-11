---
title: Common Failures
sidebar_position: 1
---

These are the most common operator-facing failures when bringing up VibeRecall locally or in a hosted environment.

## `404 Session not found`

Cause:

- the client is sending a stale or expired `mcp-session-id`

Fix:

- reconnect or restart the MCP client so it performs `initialize` again

Why this happens:

- the MCP transport is stateful
- backend restarts invalidate server-side session state
- some clients keep retrying with dead session identifiers unless you reconnect cleanly

Fast recovery path:

1. remove or disconnect the dead MCP server entry if the client exposes that action
2. reconnect it
3. rerun `viberecall_get_status`

## Graph-backed tools fail locally

If graph-backed calls like `viberecall_save`, `viberecall_search`, `viberecall_get_facts`, or `viberecall_timeline` fail with FalkorDB connection errors:

1. start the local runtime dependencies with `docker compose -f ops/docker-compose.runtime.yml up -d`
2. verify `http://localhost:8010/healthz`
3. confirm your local env points at the expected FalkorDB and Redis hosts

Do not debug the client before you confirm the local backing services are actually running.

## Control-plane requests fail between web and API

If project pages cannot load control-plane data:

- make sure `CONTROL_PLANE_INTERNAL_SECRET` matches across web and API
- make sure `PUBLIC_WEB_URL` and `ALLOWED_ORIGINS` are configured consistently
- verify the API base URL exposed to the web app matches the public deployment

If browser pages fail but direct MCP calls still work, the problem is often in control-plane wiring rather than the MCP runtime itself.

## Docs links point at the wrong host

If the control plane opens stale or incorrect docs URLs:

- verify `NEXT_PUBLIC_DOCS_URL` before building `apps/web`
- rebuild the control plane after changing the value
- confirm the docs Vercel project is serving the expected `docs.<your-domain>` domain

Remember that `NEXT_PUBLIC_*` values are baked in at build time. Changing the env without rebuilding the web app will not fix already-built links.

## Token works in one project and fails in another

Cause:

- the token belongs to a different project
- the endpoint path points at the wrong `project_id`

Fix:

1. confirm the token was minted for the intended project
2. confirm the MCP endpoint path includes the same `project_id`
3. reconnect the client after correcting either side

Project scoping is explicit by design. A valid token is still the wrong credential if it is paired with the wrong project path.

## Hosted server cannot see local uncommitted code

Cause:

- the hosted MCP runtime cannot read your laptop filesystem
- the agent assumed remote indexing could inspect a dirty local worktree directly

Fix:

1. keep the hosted core server for memory
2. use a local packaging or bridge flow for local workspace material
3. submit a bundle or other explicit repo source instead of a raw local path

See [Local Workspace Bridge](/agent-guides/local-workspace-bridge) for the safe model.

## Optional prompts or resources do not appear

Cause:

- the client does not surface them
- the current integration path only exposes tools well
- the deployment intentionally treats those features as optional

Fix:

- continue with the tool-first workflow
- verify `viberecall_get_status`, search, context, and save flows first
- treat prompts and resources as optional UX, not as the core compatibility contract

This is expected more often than many teams assume.

## Tool spam produces noisy or unhelpful memory

Cause:

- the agent saves every intermediate thought
- the tool set is too broad for the current workflow
- instructions do not distinguish meaningful observations from scratch work

Fix:

1. narrow the installed tool subset
2. adopt a rules template from [Playbooks & Rules](/playbooks/agent-rules-overview)
3. save only stable findings, decisions, and evidence worth reuse

Memory quality problems are usually workflow problems before they are storage problems.
