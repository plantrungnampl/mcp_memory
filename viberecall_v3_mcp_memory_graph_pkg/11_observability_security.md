---
title: Observability and Security
status: normative
version: 3.0
---
# 11 — Observability and Security

## 1. Observability baseline
Mỗi tool call và worker op MUST be traceable end-to-end.

Required correlation fields:
- `request_id`
- `project_id`
- `token_fingerprint`
- `operation_id`
- `episode_id` / `fact_version_id` / `entity_id` where relevant
- `index_run_id` for indexing

## 2. Metrics
Required metrics:
- request count/latency by tool
- error count by tool/error code
- operation duration by type/lane
- outbox backlog
- DLQ size
- resolution ambiguity rate
- extraction conflict rate
- context pack hit/truncation rate
- bundle upload size distribution
- graph projection lag
- search watermark lag

## 3. Logs
Structured logs MUST include:
- auth decisions
- rate limit decisions
- operation transitions
- retries
- projection rebuild progress
- token lifecycle events
- privileged actions (merge/split/delete/export)

Secret values MUST never appear in logs.

## 4. Audit logs
Immutable-enough audit needed for:
- token create/revoke
- fact update
- merge/split entity
- delete request
- export request
- budget override
- operator interventions

## 5. Threat model
### A. Token compromise
Mitigation:
- least privilege scopes
- expiry/rotation
- emergency revoke
- audit + anomaly detection

### B. Prompt injection from stored memory
Mitigation:
- trust classes
- content sanitization
- context pack separation between raw notes and canonical facts
- avoid blindly surfacing low-trust raw content

### C. Malicious workspace bundle
Mitigation:
- isolated sandbox
- path traversal rejection
- no device files
- content size limits
- no automatic execution of uploaded code

### D. Cross-project data leak
Mitigation:
- per-project token binding
- DB predicates and tests
- cache key scoping
- resource URI access checks

### E. Search/result poisoning
Mitigation:
- projection rebuild from canonical data
- no client-controlled rank features without validation
- sanitize stored searchable text

## 6. Secret handling
System SHOULD perform lightweight secret detection on ingested content.
On detection:
- redact from search docs
- mark episode metadata
- retain minimal audit-safe hashed evidence if needed

## 7. Output sanitization
Tool outputs MUST sanitize:
- raw secrets
- unsafe unescaped control content
- internal stack traces for public tokens
- object storage/internal credentials refs

## 8. Data protection
- TLS in transit
- provider encryption at rest
- separate secret stores/config
- limited operator access paths
- signed URLs with short TTL

## 9. Human review boundaries
For high-risk actions (merge/split/delete/export), production workflow SHOULD support operator or owner review, even if API technically allows scoped tokens.

## 10. Security invariants
1. No public tool may read arbitrary server filesystem path.
2. No resource URI may bypass project authz.
3. No privileged tool should appear in discovery for insufficient token scope.
4. No secret-like content should leak to logs/search projections unchanged.
