---
title: Deployment and Operability
status: normative
version: 3.0
---
# 12 — Deployment and Operability
domain: app.viberecall.dev
## 1. Deploy units
Recommended initial units:
- web control plane
- control-plane API
- MCP runtime
- worker deployment(s)
- optional graph projection service
- optional local bridge distributed as binary/package, not hosted

## 2. Single-region first
V1 nên single-region managed deployment với:
- managed Postgres
- managed Redis
- object storage
- autoscaled API/worker services

Multi-region active-active là non-goal cho v1.

## 3. Environment parity
Dev/test MUST use production-shaped dependencies:
- Postgres
- Redis
- object storage emulator or real test bucket
- worker queue
- optional graph backend test instance if feature enabled

Không dùng local in-memory fake thay cho distributed semantics trong integration tests trọng yếu.

## 4. Startup validation
Services MUST validate:
- required env vars
- DB migrations compatibility
- queue connectivity
- object storage bucket existence
- feature flag consistency

## 5. Release strategy
- migrations forward-compatible first
- shadow/backfill where possible
- canary project rollout
- monitor error and queue lag
- enable new tool discovery only after server readiness

## 6. Runbooks
Must-have runbooks:
- outbox backlog spike
- stuck index runs
- projection rebuild
- token compromise
- object storage incident
- graph projection drift
- emergency write freeze

## 7. Feature flags
Good initial flags:
- graph projection enabled
- vector search enabled
- prompts enabled
- resources enabled
- workspace bundle indexing enabled
- advanced graph tools enabled

## 8. Migrations and backfills
Backfills MUST:
- be resumable
- be observable
- avoid long table locks
- write operation/audit records if they mutate canonical semantics

## 9. On-call minimums
Alerts for:
- error rate by tool
- queue lag
- DLQ growth
- projection watermark lag
- indexing failure spike
- revoke/auth anomalies
- search latency regression

## 10. Operability principle
Không thêm infra dependency mới trừ khi:
- bottleneck measured
- runbook exists
- ownership rõ ràng
- failure mode understood
