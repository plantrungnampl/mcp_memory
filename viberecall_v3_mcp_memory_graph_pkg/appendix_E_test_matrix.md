---
title: Test Matrix
status: normative
version: 3.0
---
# Appendix E — Test Matrix

## Core correctness
- save episode with idempotency duplicate
- save episode then relay publish fail
- save episode large payload when object store down
- search with snapshot token across projection churn
- update_fact concurrent same current version
- update_fact stale expected version

## Entity resolution
- file rename resolved as same canonical entity
- ambiguous symbol mention kept unresolved
- merge entities updates redirects and search views
- split entity repairs wrong merge

## Graph
- get_neighbors bounded depth/limit
- find_paths truncation and deterministic ordering
- explain_fact shows lineage and provenance
- graph projection unavailable fallback to SQL path

## Indexing
- git source clone success
- workspace bundle parse success
- corrupt bundle rejected
- build new snapshot fails; previous READY remains live
- two concurrent index runs rejected/serialized per policy

## Security
- token scope denied hides tools from tools/list
- project mismatch denied
- secret-like content redacted from search docs
- resource URI cannot cross project boundary
- raw repo path input rejected

## Operations
- stuck outbox reconciled
- duplicate worker delivery idempotent
- delete saga partial failure repair
- budget exceeded returns deterministic error
