---
title: Failure Recovery
sidebar_position: 5
---

Use this page when an agent workflow fails mid-task and you need to recover without making the situation noisier.

## 1. Session failure

Symptom:

- `404 Session not found`

Recovery:

1. reconnect the MCP server
2. perform a fresh initialize in the client
3. rerun `viberecall_get_status`

Do not keep replaying tool calls against a dead session.

## 2. Auth or scope failure

Symptoms:

- `401`
- `403`
- the endpoint is reachable but every tool call is rejected

Recovery:

1. confirm the endpoint path uses the intended `<project_id>`
2. confirm the bearer token is current
3. reconnect so the client sends fresh auth state

## 3. Context retrieval feels wrong

Symptoms:

- retrieval is too broad
- graph results look noisy
- the agent keeps missing the same context

Recovery:

1. stop broad repeated searches
2. call `viberecall_get_context_pack`
3. if the task is entity-centric, identify the entity with `viberecall_search_entities`
4. only then call `viberecall_get_neighbors`

This is the recovery path for tool spam.

## 4. Code context is stale

Symptoms:

- repository details look outdated
- context retrieval does not reflect recent code changes

Recovery:

1. call `viberecall_get_index_status`
2. if stale, trigger `viberecall_index_repo` from a trusted workflow
3. wait for readiness
4. rerun `viberecall_get_context_pack`

## 5. Local repository is not visible to the hosted service

Symptoms:

- the agent references local uncommitted code
- the hosted server does not reflect those changes

Recovery:

1. decide whether Git indexing is possible
2. if not, use a workspace bundle flow
3. call `viberecall_index_repo` with a reachable source

Do not try to recover by pointing the hosted server at a local filesystem path.

## 6. Optional MCP features are missing

Symptoms:

- prompts do not appear
- resources are absent

Recovery:

1. confirm tool calls still work
2. continue with the tool-first workflow
3. treat prompts and resources as optional compatibility surfaces

If tools work, the core integration is still healthy.

## 7. Memory correction feels risky

Symptoms:

- a fact appears wrong
- the agent is tempted to update it immediately

Recovery:

1. call `viberecall_explain_fact`
2. review lineage and supporting evidence
3. only then call `viberecall_update_fact`

## 8. Stop condition

Stop and escalate to the human operator if:

- repeated reconnects still fail
- the wrong project or environment is unclear
- the task appears to require privileged maintenance tools
- the workflow depends on infrastructure that is not actually reachable

Recovery is supposed to reduce noise. If the agent is about to widen scope, stop.

## Related reading

- [Common Failures](/troubleshooting/common-failures)
- [Task Playbook](/playbooks/task-playbook)
- [Local Workspace Bridge](/agent-guides/local-workspace-bridge)
