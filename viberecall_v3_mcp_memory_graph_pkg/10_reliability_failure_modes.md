---
title: Reliability and Failure Modes
status: normative
version: 3.0
---
# 10 — Reliability and Failure Modes

## 1. Reliability goals
Hệ thống phải fail theo cách:
- detectable
- auditable
- recoverable
- không silent-corrupt truth

## 2. Dependency impact matrix
| Dependency | If down | Core impact |
|---|---|---|
| Postgres | service unavailable or read-only degraded | critical |
| Redis | session/rate-limit/queue impaired | major |
| Object storage | large payload/bundle/export paths impaired | partial |
| Graph projection backend | graph UI/acceleration unavailable | minor if degraded correctly |

## 3. Must-handle failures
- DB commit success + broker publish fail
- duplicate worker delivery
- concurrent fact correction
- bundle upload missing or corrupt
- latest READY snapshot corruption
- graph backend lag/down
- token revoked mid-session
- object store timeout during large save/index
- projection rebuild lag
- delete saga partial completion

## 4. Degraded mode rules
### Graph projection unavailable
- graph queries fall back to canonical SQL with stricter limits
- graph UI/resources may degrade
- core search/save/fact update remain available

### Object storage unavailable
- reject large payload/bundle paths explicitly
- small inline episode saves may continue if within size bounds

### Redis degraded
- if no safe fallback for session/rate-limit/queue, fail closed for writes
- avoid silently disabling rate limits in production

## 5. Delete saga
Delete is a saga, not a fake distributed transaction.
States:
- `DELETION_PENDING`
- `DELETE_CANONICAL_DONE`
- `DELETE_BLOBS_DONE`
- `DELETE_PROJECTIONS_DONE`
- `DELETED`
- `DELETE_FAILED_RETRYABLE`
- `DELETE_FAILED_TERMINAL`

## 6. Projection rebuild
System MUST support:
- rebuild `memory_search_docs`
- rebuild graph projection
- recompute salience
- reattach latest READY snapshot heads

## 7. Backup/restore
Minimum expectation:
- Postgres PITR-capable backups
- object storage versioning or retention for critical artifacts
- documented restore runbook
- validation of restored projection rebuild

## 8. Consistency guarantees
- raw save committed => episode durable
- fact correction committed => exactly one current version after transaction
- latest READY snapshot pointer changes atomically
- async projections eventually converge from canonical truth

## 9. Chaos / failure drills
Must test:
- kill worker during projection update
- duplicate outbox event
- graph projection wipe and rebuild
- revoke token while active client keeps calling tools
- corrupt bundle tar
- partial object store delete
- concurrent merge entities

## 10. Stop-ship conditions
Không được GA nếu:
- outbox loss bug known
- fact correction can produce double-current
- search pagination drifts without token
- delete saga can claim success while leaving canonical rows visible
- code index can replace READY head with incomplete snapshot
