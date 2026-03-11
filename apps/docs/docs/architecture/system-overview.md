---
title: System Overview
sidebar_position: 1
---

VibeRecall splits the product into a public control plane and a project-scoped MCP runtime.

## Runtime split

### Web control plane

The web app is a Next.js App Router control plane. It handles sign-in, project onboarding, token lifecycle, usage analytics, API logs, exports, and graph exploration.

### Control-plane and MCP API

The API app is built with FastAPI and FastMCP. It serves both the owner-scoped control-plane endpoints and the public MCP transport used by IDEs and coding agents.

### Data and background systems

- Postgres stores canonical relational state
- FalkorDB backs graph-oriented memory operations
- Redis acts as KV, queue broker, and task result backend
- Celery handles async work in production-shaped environments

This split matters because the agent is not talking to a simple stateless notes API. It is talking to a runtime that coordinates durable storage, canonical memory, graph retrieval, and asynchronous enrichment.

## Product model

VibeRecall is optimized for project isolation:

- one project-scoped MCP endpoint
- one token scope per project access token
- one isolated graph namespace per project
- one canonical memory surface for facts, episodes, provenance, and indexed context

The control plane and MCP runtime cooperate, but they are not the same thing:

- the control plane is where operators create and manage access
- the MCP endpoint is where agents actually perform memory work
- the backend data plane enforces project-scoped storage and retrieval boundaries

## Request and data flow

A simplified public-safe flow looks like this:

1. an operator creates a project in the control plane
2. the operator creates a token and hands the plaintext value to a trusted client
3. the client connects to `https://api.<your-domain>/p/<project_id>/mcp`
4. the runtime authenticates the token against the project scope
5. tool calls read or write canonical memory, graph state, working memory, or indexing workflows
6. asynchronous work is polled through operation and status tools when needed

That is why the docs keep control-plane guidance separate from MCP tool guidance. They are different responsibilities.

## Save and search behavior

The save path acknowledges quickly and defers enrichment asynchronously. Search reads from canonical memory and graph/index surfaces shaped for agent retrieval rather than human dashboard browsing.

Practical consequences:

- a save returning success does not mean every downstream enrichment has finished immediately
- the system is optimized for useful retrieval and provenance, not for dumping raw append-only logs back to the client
- graph-backed reasoning becomes more valuable as indexing and enrichment settle into a ready state

## Why the public contract is tool-first

Client support across coding agents is uneven for prompts and resources. The broadest compatibility surface remains tools over remote HTTP.

That leads to four public design rules:

- tools must be enough for useful memory workflows
- remote HTTP is the primary hosted path
- bearer-token auth is the default access model
- bounded outputs matter more than convenience-first blobs

The agent guides and playbooks in this docs site all inherit those rules.

## Non-goals of this public docs site

This section intentionally stops short of publishing internal schema sketches, capacity experiments, or roadmap-only backlog items. Those remain engineering material in the repository.
