---
title: Open Questions and ADRs
status: working
version: 3.0
---
# 15 — Open Questions and ADRs

## ADR-001: Postgres is the source of truth
Accepted.

## ADR-002: Transactional outbox is mandatory
Accepted.

## ADR-003: Core compatibility is tool-first
Accepted.
Resources/prompts are optional enhancements.

## ADR-004: Raw server `repo_path` is forbidden
Accepted.

## ADR-005: Local workspace bridge is optional but recommended
Accepted.

## ADR-006: Fact correction is transactional CAS
Accepted.

## ADR-007: Graph backend is projection, not truth
Accepted.

## ADR-008: Token-scoped tool discovery
Accepted.

## ADR-009: Search pagination requires snapshot token
Accepted.

## ADR-010: Salience/retention are first-class concerns
Accepted.

## Open questions
### Q1. Có nên bật vector search ngay không?
Recommendation: optional feature flag only.

### Q2. Có nên để graph queries chạy trực tiếp trên graph backend khi available?
Recommendation: yes as accelerator, but canonical semantics and fallback required.

### Q3. Có nên support cross-project memory later?
Recommendation: maybe, but only with explicit product boundary and security redesign.

### Q4. Có cần explicit conflict review UI trước GA?
Recommendation: strongly yes for operator/owner workflows.

### Q5. Có nên cho agents merge/split entities tự động?
Recommendation: no by default; privileged/human-reviewed first.

### Q6. Có nên support OAuth for remote MCP install?
Recommendation: useful later, but bearer PAT is simpler and enough to start.

### Q7. Có cần `resources/subscribe` không?
Recommendation: no for v1.

### Q8. Có nên tạo separate admin MCP server?
Recommendation: maybe unnecessary if tool discovery is scope-aware; revisit if tool count becomes a UX problem.
