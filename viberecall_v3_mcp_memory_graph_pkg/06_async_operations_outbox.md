---
title: Async Operations and Transactional Outbox
status: normative
version: 3.0
---
# 06 — Async Operations and Transactional Outbox

## 1. Principle
Không được dùng pattern “commit DB rồi best-effort publish queue”.
Mọi async workflow MUST dùng:
- `operations`
- `outbox_events`
- relay publisher
- worker idempotency

## 2. Operation types
Initial operation types:
- `EPISODE_INGEST`
- `SEARCH_REPROJECT`
- `GRAPH_REPROJECT`
- `INDEX_RUN`
- `EXPORT_BUILD`
- `ENTITY_RESOLUTION`
- `RETENTION_COMPACTION`
- `DELETE_SAGA`

## 3. Operation states
- `PENDING`
- `RUNNING`
- `SUCCEEDED`
- `FAILED_RETRYABLE`
- `FAILED_TERMINAL`
- `CANCEL_REQUESTED`
- `CANCELLED`

## 4. Transaction pattern
For any async workflow:
1. validate request
2. inside one transaction:
   - write domain rows
   - write operation row
   - write outbox row(s)
   - write idempotency record if needed
3. commit
4. relay publishes outbox rows
5. worker consumes and updates operation state

## 5. Queue lane model
| Lane | Examples | Priority |
|---|---|---|
| `ingest-high` | episode enrichment | highest |
| `projection-medium` | search/graph reproject | medium |
| `index-low` | code indexing | low |
| `export-low` | export build | low |
| `maintenance-low` | retention/reconciler | low |

Concurrency MUST tách theo lane để noisy neighbors không giết interactive path.

## 6. Idempotency
Có 3 lớp:
1. API idempotency keys
2. relay publish idempotency
3. worker execution idempotency

Worker MUST tolerate double delivery.

## 7. Outbox relay
Relay có thể là:
- dedicated background loop
- DB polling publisher
- trigger-based notifier + poll fallback

Bất kể implementation nào, semantics bắt buộc là:
- event không bị mất sau commit
- event có thể bị publish nhiều lần
- consumer phải idempotent

## 8. Retry policy
- exponential backoff + jitter
- terminal fail classification
- poison message => DLQ / quarantine state
- operator visibility cho stuck ops

## 9. Reconciler
Background reconciler MUST tồn tại để sửa:
- operation row không progress
- outbox row publish fail kéo dài
- object storage orphan
- projection drift
- delete saga half-complete

## 10. Sync vs async boundary
### Sync
- authz
- canonical write row creation
- immediate observation doc for `save_episode`
- transactional fact correction

### Async
- enrichment
- graph projection
- heavy reindex
- export builds
- compaction
- large deletion cleanup

## 11. Operation polling
`viberecall_get_operation` là generic read surface cho async workflows.
Response SHOULD include:
- status
- operation_type
- percent_hint optional
- current_step optional
- result summary if finished
- retryable flag if failed

## 12. Anti-patterns
- returning “done” when only queued
- mutating canonical truth only inside worker for operations requiring strong sync semantics
- no DLQ / no reconciler
- worker side effects without operation row linkage
