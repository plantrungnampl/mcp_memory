---
title: Migration Plan
status: working
version: 3.0
---
# 14 — Migration Plan

## 1. Goal
Di chuyển từ thiết kế cũ sang v3 mà không phá clients hiện có nhiều hơn mức cần thiết.

## 2. Phase 0 — foundations
- create canonical tables for entities/facts/provenance if missing
- create operations/outbox framework
- add token scopes
- add projection watermark tables
- add latest READY head if absent

Exit criteria:
- no new async flow bypasses outbox
- scope-aware tool discovery ready

## 3. Phase 1 — unify search path
- create/repair `memory_search_docs`
- immediate observation doc on save
- remove runtime merge between graph/raw episode reads
- add `snapshot_token`

Exit criteria:
- search/read path canonicalized
- pagination drift tests passing

## 4. Phase 2 — fact correction hardening
- move `update_fact` to transactional CAS
- add unique constraint for single current version
- add lineage/provenance read

Exit criteria:
- concurrent update test passing

## 5. Phase 3 — code index source redesign
- deprecate raw `repo_path`
- implement `repo_source`
- ship workspace bundle helper
- migrate index runs to latest READY semantics if needed

Exit criteria:
- no production path depends on server-local repo path

## 6. Phase 4 — graph semantics
- relation catalog
- entity resolution tables
- neighbor/path/explain tools
- optional graph projection rebuild pipeline

Exit criteria:
- graph read path works from canonical data

## 7. Phase 5 — salience/compaction/evaluation
- salience fields
- retention jobs
- compaction summaries
- evaluation harness

Exit criteria:
- retrieval quality metrics available
- compaction never loses provenance

## 8. Phase 6 — resources/prompts
- optional resource URIs
- prompt templates
- client-specific docs

Exit criteria:
- tools remain sufficient without resources/prompts

## 9. Backfill strategy
Backfills SHOULD run in this order:
1. episodes metadata normalization
2. entity canonical rows
3. fact groups/versions
4. provenance links
5. search docs
6. graph projection

## 10. Rollback plan
- keep old search path behind flag during migration
- do not delete old projections until new path validated
- preserve previous READY code snapshot head
- keep compatibility wrappers for renamed tools if needed

## 11. Deprecations
Explicitly deprecate:
- raw `repo_path`
- search without snapshot token support
- update_fact accepted-async behavior
- scope-blind tool discovery
