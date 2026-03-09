---
title: Implementation Backlog
status: working
version: 3.0
---
# 17 — Implementation Backlog

## Epic 1 — Canonical data foundation
- migrations for entities/aliases/relation_types/fact_groups/fact_versions/provenance
- unique current fact constraints
- projection watermark table
- search docs v2/v3 schema
- repository layer + tests

## Epic 2 — Authz and tool discovery
- token scopes
- scope-aware tools list
- rate limit/budget middleware
- revoke generation checks
- audit logs

## Epic 3 — Outbox framework
- operations model
- outbox insert helpers
- relay publisher
- DLQ
- reconciler
- end-to-end tests for duplicate delivery and publish fail

## Epic 4 — Core MCP tools
- save_episode
- search_memory
- get_context_pack
- get_operation
- get_fact
- update_fact

## Epic 5 — Graph capabilities
- entity search
- neighbors
- explain_fact
- find_paths
- relation catalog enforcement
- resolution events

## Epic 6 — Extraction pipeline
- normalization
- entity extraction
- fact extraction
- rule-based parsers
- LLM extractor integration (flagged)
- provenance writes

## Epic 7 — Code indexing
- repo source model
- git clone sandbox
- workspace bundle ingestion
- snapshot builder
- latest READY head
- index status tool

## Epic 8 — Salience and compaction
- salience fields and scoring
- pin/demote tool
- retention policies
- compaction summaries
- archival jobs

## Epic 9 — Resources and prompts
- resources/list/read
- prompt definitions
- resource links from tool results
- client docs

## Epic 10 — Evaluation and hardening
- gold datasets
- extraction evaluation runner
- conflict dashboards
- chaos tests
- SLO dashboards

## Suggested milestone cuts
### Milestone A
Epics 1-4

### Milestone B
Epics 5-7

### Milestone C
Epics 8-10
