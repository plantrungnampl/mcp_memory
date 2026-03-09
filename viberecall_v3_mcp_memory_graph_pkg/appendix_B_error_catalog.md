---
title: Error Catalog
status: normative
version: 3.0
---
# Appendix B — Error Catalog

## Common error codes
| Code | Meaning | Retryable |
|---|---|---|
| `AUTH_INVALID_TOKEN` | token invalid/missing | no |
| `AUTH_SCOPE_DENIED` | token lacks scope | no |
| `AUTH_PROJECT_MISMATCH` | token not bound to endpoint project | no |
| `RATE_LIMITED` | request rate exceeded | yes |
| `BUDGET_EXCEEDED` | hard budget exceeded | no until budget reset/override |
| `INVALID_ARGUMENT` | schema or business validation failure | no |
| `IDEMPOTENCY_CONFLICT` | same key different request fingerprint | no |
| `FACT_VERSION_MISMATCH` | CAS precondition failed | no |
| `ENTITY_RESOLUTION_AMBIGUOUS` | cannot safely auto-resolve | no |
| `PROJECTION_STALE` | requested snapshot token expired or invalid | yes with refresh |
| `GRAPH_BACKEND_UNAVAILABLE` | graph accelerator unavailable | yes/fallback |
| `OBJECT_STORAGE_UNAVAILABLE` | blob/bundle path unavailable | yes |
| `INDEX_BUNDLE_NOT_FOUND` | bundle ref invalid or expired | no |
| `INDEX_RUN_CONFLICT` | concurrent index policy violation | yes later |
| `DELETE_SAGA_IN_PROGRESS` | object pending deletion | yes later |
| `EXPORT_NOT_READY` | export still building | yes later |
| `INTERNAL_RETRYABLE` | internal transient failure | yes |
| `INTERNAL_TERMINAL` | internal unrecoverable failure | no |

## Error response shape
Tool execution error SHOULD include:
- `code`
- `message`
- `retryable`
- `details` optional and sanitized
