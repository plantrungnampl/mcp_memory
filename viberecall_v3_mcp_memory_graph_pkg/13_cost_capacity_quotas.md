---
title: Cost, Capacity and Quotas
status: normative
version: 3.0
---
# 13 — Cost, Capacity and Quotas

## 1. Capacity assumptions
Initial target:
- 1k+ projects
- vài trăm active projects
- vài trăm concurrent sessions
- burst tens of RPS
- episodes/project: thousands median
- facts/project: thousands to tens of thousands
- code files/project: hundreds to tens of thousands
- bundles sized within strict upper bounds

## 2. Main cost drivers
- Postgres storage/IO
- worker CPU for extraction and indexing
- object storage bytes + egress
- Redis capacity
- optional vector and graph projections

## 3. Hard quotas
MUST support:
- request rate per token/project
- concurrent write ops per token
- concurrent index runs per project
- daily uploaded bytes per project
- monthly worker compute budget per project
- max context pack size
- max graph query expansion size

## 4. Soft quotas
- warnings at 70/85/95%
- owner visibility
- budget forecast where possible

## 5. Cost-aware defaults
- graph projection off by default unless needed
- embeddings/vector optional
- latest READY + one rollback snapshot
- archive low-value raw episodes before touching canonical facts
- context packs default conservative size

## 6. Indexing-specific limits
- max files per bundle
- max bundle bytes
- max individual file bytes
- max index runtime
- parser language allowlist per plan if needed

## 7. Optimization order
1. tune SQL indexes/projections
2. tune extraction/indexing concurrency
3. compact/archive low-value data
4. cache read-heavy metadata
5. only then consider new infra like dedicated search cluster

## 8. Runtime budget enforcement
When over hard budget:
- reject new costly operations deterministically
- allow cheap reads if policy allows
- never silently continue expensive runs without billing/control story

## 9. Measurement requirements
Usage events SHOULD capture:
- bytes stored
- bytes indexed
- worker compute units
- number of extracted facts
- context pack size
- graph query node/edge counts
- export artifact size

## 10. Anti-patterns
- heuristic vanity token accounting without real cost telemetry
- unlimited index retries
- retaining all raw debug output in hot path forever
