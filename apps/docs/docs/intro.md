---
id: intro
title: VibeRecall Docs
sidebar_position: 1
slug: /
---

VibeRecall is a project-scoped MCP memory platform for coding agents. Each project gets its own MCP endpoint, bearer-token access path, persisted memory state, and control-plane visibility for usage, logs, and graph workflows.

This site is the public, operator-facing reference for:

- onboarding a project and connecting an MCP client
- understanding the current public `viberecall_*` tool surface
- running VibeRecall locally or in a hosted topology
- integrating Codex or Claude Code safely
- writing practical rules and playbooks for AI coding agents

## What VibeRecall is

Think of VibeRecall as three cooperating surfaces:

1. A control plane that creates projects, issues tokens, and shows usage and logs.
2. A project-scoped MCP endpoint at `https://api.<your-domain>/p/<project_id>/mcp`.
3. A memory runtime behind that endpoint that exposes a stable tool-first contract.

The public design priorities are intentional:

- remote HTTP is the primary deployment path
- bearer-token auth is the default access model
- tools are the required compatibility surface
- prompts and resources are optional accelerators, not required for correctness

If your client can connect, call `viberecall_get_status`, save one note, and read it back, the critical path is already working.

## Who these docs are for

These docs are written for technical users who are doing one of the following:

- connecting a coding agent such as Codex or Claude Code
- validating a hosted MCP endpoint before broader rollout
- operating the control-plane plus MCP runtime split
- writing repeatable agent instructions that make memory usage predictable

This is not a marketing site and it is not a full internal design notebook. The goal is to make the public contract operationally clear.

## Recommended reading paths

### New to VibeRecall

- Start with [Quickstart](/getting-started/quickstart)
- Then read [Connection](/mcp-reference/connection)
- Then review [MCP Tool Surface](/mcp-reference/tool-surface)

### Wiring an AI coding agent

- Start with [Agent Guides Overview](/agent-guides/overview)
- Then read [Codex](/agent-guides/codex) or [Claude Code](/agent-guides/claude-code)
- Finish with [Task Playbook](/playbooks/task-playbook)

### Running or deploying the platform

- Read [Local Development](/getting-started/local-development)
- Read [System Overview](/architecture/system-overview)
- Read [Deployment Topology](/architecture/deployment-topology)
- Keep [Common Failures](/troubleshooting/common-failures) nearby during rollout

## Public contract at a glance

This site documents the currently supported public contract:

- project-scoped MCP connectivity
- token handling expectations
- the current 25-tool public surface and safe usage patterns
- Codex and Claude Code integration guidance
- copy-paste rules and playbooks for agent workflows
- public-safe deployment and troubleshooting guidance

The intended mental model is:

- the control plane is where you create and manage projects
- the MCP endpoint is where the agent actually works
- the tool surface is the compatibility baseline
- optional prompts and resources should help, not gate core workflows

## What success looks like

You are in a good state when all of the following are true:

- your client connects to `https://api.<your-domain>/p/<project_id>/mcp`
- the token belongs to the same project
- tool discovery works
- `viberecall_get_status` returns a healthy response
- one write can be searched or explained again through the public memory surface

From there, you can safely move on to indexing, graph exploration, fact correction, and agent automation.

## What this site intentionally does not publish

This public site does not publish:

- internal quota and capacity planning details
- backlog and roadmap internals
- private control-plane implementation notes
- internal-only identifiers, credentials, or operational shortcuts

Those remain engineering source material inside the repository.
