---
title: Acceptance Checklist
status: normative
version: 3.0
---
# Appendix C — Acceptance Checklist

## Foundations
- [ ] Postgres canonical schema deployed
- [ ] unique current fact constraint enforced
- [ ] operations + outbox deployed
- [ ] reconciler exists
- [ ] idempotency keys supported

## MCP protocol
- [ ] tools/list scope-aware
- [ ] tool outputs have structuredContent
- [ ] search pagination pinned by snapshot token
- [ ] invalid arguments return deterministic errors

## Security
- [ ] no raw repo_path access
- [ ] tokens hashed and revocable
- [ ] privileged tools hidden for low-scope tokens
- [ ] secret redaction policy implemented
- [ ] bundle sandboxing tested

## Reliability
- [ ] duplicate worker delivery test passes
- [ ] DB commit + publish fail test passes
- [ ] concurrent fact correction test passes
- [ ] latest READY snapshot rollback candidate exists
- [ ] graph projection rebuild tested

## Retrieval quality
- [ ] context pack budget shaping works
- [ ] entity resolution ambiguity handled conservatively
- [ ] salience scoring exists
- [ ] conflict signals visible
- [ ] evaluation datasets and metrics exist

## Operability
- [ ] dashboards for queues/errors/latencies
- [ ] audit logs for privileged actions
- [ ] runbooks documented
- [ ] backup/restore exercise done
